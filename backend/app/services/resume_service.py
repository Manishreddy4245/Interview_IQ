import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.core.database import db_manager
from app.schemas.resume import (
    AIRawSkillGapOutput,
    ResumeAnalysisResult,
    StartInterviewFromResumeResponse,
    SkillEvidenceCategory,
    SkillEvidenceItem,
)
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    InterviewSessionResponse,
)
from app.services.session_service import create_interview_session
from app.services.gap_prioritizer import prioritize_skill_gaps
from app.services.skill_normalizer import normalize_skill_name, skills_match
from app.services.question_generator import generate_initial_adaptive_question

logger = logging.getLogger("interviewiq.resume_service")

# In-memory storage for active session analyses when MongoDB Atlas is unconfigured
_in_memory_analyses: Dict[str, Dict[str, Any]] = {}


async def store_resume_analysis(
    target_role: str,
    experience_level: str,
    ai_output: AIRawSkillGapOutput,
    owner_id: Optional[str] = None,
    raw_resume_text: Optional[str] = None,
) -> ResumeAnalysisResult:
    """
    Store resume analysis result.
    Persists to MongoDB Atlas if configured; falls back cleanly to in-memory store.
    """
    analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    analysis_doc = {
        "analysis_id": analysis_id,
        "owner_id": owner_id,
        "target_role": target_role,
        "experience_level": experience_level,
        "target_role_benchmark": ai_output.target_role_benchmark.model_dump() if ai_output.target_role_benchmark else None,
        "extracted_skills": ai_output.extracted_skills,
        "projects_and_experience": ai_output.projects_and_experience,
        "education": getattr(ai_output, "education", []),
        "work_experience": getattr(ai_output, "work_experience", []),
        "certifications": getattr(ai_output, "certifications", []),
        "raw_resume_text": raw_resume_text,
        "skill_evaluations": [s.model_dump() for s in ai_output.skill_evaluations],
        "personalized_questions": [q.model_dump() for q in ai_output.personalized_questions],
        "role_readiness_summary": ai_output.role_readiness_summary,
        "is_truncated": ai_output.is_truncated,
        "analyzed_character_count": ai_output.analyzed_character_count,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    saved_to_db = False
    db_status = "unconfigured"
    db_message = "MongoDB Atlas is not configured. Resume analysis is active in memory only."

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["resume_analyses"].insert_one({**analysis_doc, "_id": analysis_id})
            saved_to_db = True
            db_status = "persisted"
            db_message = "Resume analysis persisted to MongoDB Atlas."
            logger.info("Resume analysis %s persisted to MongoDB Atlas.", analysis_id)
        except Exception as exc:
            db_status = "unreachable"
            db_message = f"MongoDB Atlas write failed: {type(exc).__name__}. Storing in memory only."
            logger.warning("Failed to persist resume analysis %s to MongoDB: %s", analysis_id, type(exc).__name__)

    # Keep in-memory cache for session continuity
    _in_memory_analyses[analysis_id] = analysis_doc

    return ResumeAnalysisResult(
        analysis_id=analysis_id,
        owner_id=owner_id,
        target_role=target_role,
        experience_level=experience_level,
        target_role_benchmark=ai_output.target_role_benchmark,
        extracted_skills=ai_output.extracted_skills,
        projects_and_experience=ai_output.projects_and_experience,
        education=getattr(ai_output, "education", []),
        work_experience=getattr(ai_output, "work_experience", []),
        certifications=getattr(ai_output, "certifications", []),
        skill_evaluations=ai_output.skill_evaluations,
        personalized_questions=ai_output.personalized_questions,
        role_readiness_summary=ai_output.role_readiness_summary,
        is_truncated=ai_output.is_truncated,
        analyzed_character_count=ai_output.analyzed_character_count,
        created_at=now,
        saved_to_db=saved_to_db,
        db_status=db_status,
        db_message=db_message,
    )


async def get_resume_analysis(analysis_id: str) -> Optional[ResumeAnalysisResult]:
    """
    Retrieve resume analysis by analysis_id from MongoDB Atlas or active in-memory store.
    """
    # 1. Check database if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            doc = await db["resume_analyses"].find_one({"_id": analysis_id})
            if doc:
                return ResumeAnalysisResult(
                    analysis_id=doc["analysis_id"],
                    owner_id=doc.get("owner_id"),
                    target_role=doc["target_role"],
                    experience_level=doc.get("experience_level", "Mid-Level"),
                    target_role_benchmark=doc.get("target_role_benchmark"),
                    extracted_skills=doc["extracted_skills"],
                    projects_and_experience=doc["projects_and_experience"],
                    education=doc.get("education", []),
                    work_experience=doc.get("work_experience", []),
                    certifications=doc.get("certifications", []),
                    skill_evaluations=doc["skill_evaluations"],
                    personalized_questions=doc["personalized_questions"],
                    role_readiness_summary=doc.get("role_readiness_summary", ""),
                    is_truncated=doc.get("is_truncated", False),
                    analyzed_character_count=doc.get("analyzed_character_count"),
                    created_at=datetime.fromisoformat(doc["created_at"]),
                    saved_to_db=True,
                    db_status="persisted",
                    db_message="Retrieved from MongoDB Atlas.",
                )
        except Exception as exc:
            logger.warning("Error fetching resume analysis %s from MongoDB: %s", analysis_id, type(exc).__name__)

    # 2. Check in-memory store
    doc = _in_memory_analyses.get(analysis_id)
    if not doc:
        return None

    if isinstance(doc, ResumeAnalysisResult):
        return doc

    return ResumeAnalysisResult(
        analysis_id=doc["analysis_id"],
        owner_id=doc.get("owner_id"),
        target_role=doc["target_role"],
        experience_level=doc.get("experience_level", "Mid-Level"),
        target_role_benchmark=doc.get("target_role_benchmark"),
        extracted_skills=doc["extracted_skills"],
        projects_and_experience=doc["projects_and_experience"],
        education=doc.get("education", []),
        work_experience=doc.get("work_experience", []),
        certifications=doc.get("certifications", []),
        skill_evaluations=doc["skill_evaluations"],
        personalized_questions=doc["personalized_questions"],
        role_readiness_summary=doc.get("role_readiness_summary", ""),
        is_truncated=doc.get("is_truncated", False),
        analyzed_character_count=doc.get("analyzed_character_count"),
        created_at=datetime.fromisoformat(doc["created_at"]),
        saved_to_db=False,
        db_status="unconfigured",
        db_message="Active in server memory.",
    )


async def get_student_latest_resume_analysis(user_id: str) -> Optional[ResumeAnalysisResult]:
    """Retrieve the latest resume analysis belonging to the specified student."""
    if not user_id:
        return None

    # Check MongoDB Atlas
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            cursor = db["resume_analyses"].find({"owner_id": user_id}).sort("created_at", -1).limit(1)
            docs = await cursor.to_list(1)
            if docs:
                doc = docs[0]
                return ResumeAnalysisResult(
                    analysis_id=doc["analysis_id"],
                    owner_id=doc.get("owner_id"),
                    target_role=doc["target_role"],
                    experience_level=doc.get("experience_level", "Mid-Level"),
                    target_role_benchmark=doc.get("target_role_benchmark"),
                    extracted_skills=doc["extracted_skills"],
                    projects_and_experience=doc["projects_and_experience"],
                    education=doc.get("education", []),
                    work_experience=doc.get("work_experience", []),
                    certifications=doc.get("certifications", []),
                    skill_evaluations=doc["skill_evaluations"],
                    personalized_questions=doc["personalized_questions"],
                    role_readiness_summary=doc.get("role_readiness_summary", ""),
                    is_truncated=doc.get("is_truncated", False),
                    analyzed_character_count=doc.get("analyzed_character_count"),
                    created_at=datetime.fromisoformat(doc["created_at"]),
                    saved_to_db=True,
                    db_status="persisted",
                    db_message="Retrieved from MongoDB Atlas.",
                )
        except Exception as exc:
            logger.warning("MongoDB lookup error for student %s resume: %s", user_id, type(exc).__name__)

    # Check in-memory
    matching = [doc for doc in _in_memory_analyses.values() if doc.get("owner_id") == user_id]
    if matching:
        latest_doc = sorted(matching, key=lambda d: d.get("created_at", ""), reverse=True)[0]
        return await get_resume_analysis(latest_doc["analysis_id"])

    return None


async def create_interview_from_resume_analysis(
    analysis_id: str,
    adaptive: bool = False,
    difficulty: Optional[str] = None,
    question_count: Optional[int] = None,
    owner_id: Optional[str] = None,
    interview_mode: Optional[str] = "VERBAL",
) -> Optional[InterviewSessionResponse]:
    """
    Convert personalized questions or prioritized gaps from a resume analysis into an interview session,
    enabling candidate practice in the Interview Room with Phase 3 evaluation support.
    Prioritizes competencies requiring clarification or practical validation over generic selection.
    """
    analysis = await get_resume_analysis(analysis_id)
    if not analysis:
        return None

    effective_owner = owner_id or analysis.owner_id
    effective_mode = (interview_mode or "VERBAL").strip().upper()
    if effective_mode not in ("CODING", "VERBAL"):
        effective_mode = "VERBAL"

    # Deterministically prioritize skill gaps using 4-tier model & benchmark importance
    prioritized_gaps = prioritize_skill_gaps(analysis)
    prioritized_competency_names = [g.skill_name for g in prioritized_gaps]

    # Focus areas: prioritize top competencies requiring validation instead of unconditional extracted_skills[:4]
    if prioritized_gaps:
        focus_areas = ", ".join([g.skill_name for g in prioritized_gaps[:4]])
    elif analysis.extracted_skills:
        focus_areas = ", ".join(analysis.extracted_skills[:4])
    else:
        focus_areas = "Role Competencies"

    chosen_difficulty = difficulty or "Medium"

    if adaptive:
        # Dynamic adaptive question generation: start with Question 1 targeting #1 prioritized competency
        target_count = question_count if (question_count and 3 <= question_count <= 5) else 5
        setup = InterviewSetupRequest(
            role=analysis.target_role,
            experience_level=analysis.experience_level,
            difficulty=chosen_difficulty,
            focus_areas=focus_areas,
            question_count=target_count,
            adaptive=True,
            interview_mode=effective_mode,
        )
        questions = await generate_initial_adaptive_question(setup)
        if questions and prioritized_gaps:
            top_gap = prioritized_gaps[0]
            questions[0].normalized_skill = top_gap.normalized_skill
            questions[0].gap_category = top_gap.category
            questions[0].role_relevance = top_gap.relevance_to_role
            questions[0].source_evidence = top_gap.source_excerpt or top_gap.evidence
            if top_gap.priority_reason:
                questions[0].selection_rationale = (
                    f"Selected for validation: {top_gap.priority_reason}. "
                    f"{questions[0].selection_rationale or ''}"
                ).strip()

        session_response = await create_interview_session(
            setup=setup,
            questions=questions,
            resume_analysis_id=analysis_id,
            is_adaptive=True,
            target_question_count=target_count,
            prioritized_competencies=prioritized_competency_names,
            owner_id=effective_owner,
        )
        return session_response

    # Static question generation from analyzed personalized questions enriched with prioritized gap context
    question_items: List[QuestionItem] = []
    for idx, pq in enumerate(analysis.personalized_questions):
        matching_gap = next(
            (g for g in prioritized_gaps if skills_match(g.skill_name, pq.assessed_skill)),
            None,
        )

        norm_skill = (
            matching_gap.normalized_skill
            if matching_gap
            else (pq.normalized_skill or normalize_skill_name(pq.assessed_skill))
        )
        gap_cat = matching_gap.category if matching_gap else pq.gap_category
        role_rel = matching_gap.relevance_to_role if matching_gap else pq.role_relevance
        source_ev = (
            (matching_gap.source_excerpt or matching_gap.evidence)
            if matching_gap
            else pq.source_evidence
        )
        rationale_text = (
            f"Prioritized for validation: {matching_gap.priority_reason}. {pq.rationale}"
            if matching_gap
            else pq.rationale
        )

        question_items.append(
            QuestionItem(
                id=f"q_{idx + 1}",
                question_number=idx + 1,
                text=pq.text,
                assessed_skill=pq.assessed_skill,
                normalized_skill=norm_skill,
                difficulty=pq.difficulty or chosen_difficulty,
                rubric=f"{pq.rubric} [Rationale: {pq.rationale}]",
                selection_rationale=rationale_text,
                gap_category=gap_cat,
                role_relevance=role_rel,
                source_evidence=source_ev,
            )
        )

    if question_count and question_count > 0:
        question_items = question_items[:question_count]

    q_len = len(question_items)
    setup_count = max(3, min(5, q_len)) if q_len > 0 else 5

    setup = InterviewSetupRequest(
        role=analysis.target_role,
        experience_level=analysis.experience_level,
        difficulty=chosen_difficulty,
        focus_areas=focus_areas,
        question_count=setup_count,
        adaptive=False,
        interview_mode=effective_mode,
    )

    session_response = await create_interview_session(
        setup=setup,
        questions=question_items,
        resume_analysis_id=analysis_id,
        is_adaptive=False,
        target_question_count=q_len,
        prioritized_competencies=prioritized_competency_names,
        owner_id=effective_owner,
    )
    return session_response


async def update_resume_skills(
    analysis_id: str,
    new_skills: List[str],
    user_id: Optional[str] = None,
) -> ResumeAnalysisResult:
    """Allow candidate to manually correct and curate extracted skills before proceeding."""
    analysis = await get_resume_analysis(analysis_id)
    if not analysis:
        raise ValueError(f"Resume analysis '{analysis_id}' not found.")
    if user_id and analysis.owner_id and analysis.owner_id != user_id:
        raise PermissionError("Access forbidden: You do not own this resume.")

    clean_skills = [s.strip() for s in new_skills if s and s.strip() and len(s.strip()) >= 2]
    if not clean_skills:
        raise ValueError("Skills list cannot be empty.")

    # Re-evaluate skills against target role benchmark if present
    benchmark = analysis.target_role_benchmark
    updated_evaluations: List[SkillEvidenceItem] = []

    if benchmark and benchmark.expected_competencies:
        for comp in benchmark.expected_competencies:
            matched_skill = next((s for s in clean_skills if skills_match(s, comp.skill_name)), None)
            if matched_skill:
                cat = SkillEvidenceCategory.DEMONSTRATED
                ev = f"Verified by candidate: {matched_skill} (satisfies {comp.skill_name})."
                rat = "Verified and confirmed by candidate in technical preparation profile."
                needs_val = False
            else:
                cat = SkillEvidenceCategory.NOT_DEMONSTRATED
                ev = f"Expected for {analysis.target_role}, but absent from verified skills list."
                rat = "Expected competency for target role, but not evidenced in candidate profile. (Absence does not imply lack of ability)."
                needs_val = True

            updated_evaluations.append(
                SkillEvidenceItem(
                    skill_name=comp.skill_name,
                    normalized_skill=normalize_skill_name(comp.skill_name),
                    category=cat,
                    evidence=ev,
                    relevance_to_role=comp.description or "Core role competency",
                    is_source_grounded=matched_skill is not None,
                    evidence_type="verbatim_quote" if matched_skill else "inferred_summary",
                    is_expected_for_role=True,
                    classification_rationale=rat,
                    requires_interview_validation=needs_val,
                )
            )
    else:
        updated_evaluations = analysis.skill_evaluations

    now = datetime.now(timezone.utc)
    if analysis_id in _in_memory_analyses:
        _in_memory_analyses[analysis_id]["extracted_skills"] = clean_skills
        _in_memory_analyses[analysis_id]["skill_evaluations"] = [e.model_dump() for e in updated_evaluations]
        _in_memory_analyses[analysis_id]["updated_at"] = now.isoformat()

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["resume_analyses"].update_one(
                {"_id": analysis_id},
                {
                    "$set": {
                        "extracted_skills": clean_skills,
                        "skill_evaluations": [e.model_dump() for e in updated_evaluations],
                        "updated_at": now.isoformat(),
                    }
                },
            )
        except Exception as exc:
            logger.warning("MongoDB update failed for resume %s: %s", analysis_id, type(exc).__name__)

    refreshed = await get_resume_analysis(analysis_id)
    return refreshed or analysis


async def update_resume_target_role(
    analysis_id: str,
    target_role: str,
    experience_level: str = "Mid-Level",
    user_id: Optional[str] = None,
) -> ResumeAnalysisResult:
    """Update target job role on candidate's resume analysis and compute standardized initial skill gap analysis."""
    analysis = await get_resume_analysis(analysis_id)
    if not analysis:
        raise ValueError(f"Resume analysis '{analysis_id}' not found.")
    if user_id and analysis.owner_id and analysis.owner_id != user_id:
        raise PermissionError("Access forbidden: You do not own this resume.")

    clean_role = target_role.strip()
    if not clean_role:
        raise ValueError("Target role cannot be empty.")

    from app.core.role_catalog import get_role_definition
    from app.schemas.resume import TargetRoleBenchmark, RoleBenchmarkCompetency

    role_def = get_role_definition(clean_role)
    if not role_def:
        raise ValueError(
            f"Role '{clean_role}' is not in the supported catalogue. "
            "Supported roles: Full Stack Engineer, Frontend Specialist, Backend Systems, AI/ML Engineer, DevOps & Cloud."
        )

    benchmark_competencies = [
        RoleBenchmarkCompetency(
            skill_name=c.skill_name,
            normalized_skill=c.normalized_skill,
            importance=c.importance,
            expected_proficiency=c.expected_proficiency,
            description=c.description,
        )
        for c in role_def.competencies
    ]
    benchmark = TargetRoleBenchmark(
        target_role=role_def.role_name,
        experience_level=experience_level,
        expected_competencies=benchmark_competencies,
        benchmark_source="InterviewIQ Standardized Role Competency Catalogue",
        disclaimer=(
            "This competency benchmark is drawn from InterviewIQ standardized role requirements "
            "as an indicative baseline for student assessment planning."
        ),
    )

    new_evaluations: List[SkillEvidenceItem] = []
    candidate_skills = analysis.extracted_skills or []

    for comp in benchmark_competencies:
        matched_skill = next((s for s in candidate_skills if skills_match(s, comp.skill_name)), None)
        if matched_skill:
            cat = SkillEvidenceCategory.DEMONSTRATED
            ev = f"Identified in resume: {matched_skill} (matches {comp.skill_name})."
            rat = "Supported by verifiable source evidence extracted from resume text."
            needs_val = False
        else:
            cat = SkillEvidenceCategory.NOT_DEMONSTRATED
            ev = f"Expected for {role_def.role_name} ({experience_level}), but not identified in resume."
            rat = "Expected competency for target role, but not evidenced in resume. (Absence does not imply lack of ability)."
            needs_val = True

        new_evaluations.append(
            SkillEvidenceItem(
                skill_name=comp.skill_name,
                normalized_skill=normalize_skill_name(comp.skill_name),
                category=cat,
                evidence=ev,
                relevance_to_role=comp.description or "Core role competency",
                is_source_grounded=matched_skill is not None,
                evidence_type="verbatim_quote" if matched_skill else "inferred_summary",
                is_expected_for_role=True,
                classification_rationale=rat,
                requires_interview_validation=needs_val,
            )
        )

    now = datetime.now(timezone.utc)
    if analysis_id in _in_memory_analyses:
        _in_memory_analyses[analysis_id]["target_role"] = role_def.role_name
        _in_memory_analyses[analysis_id]["experience_level"] = experience_level
        _in_memory_analyses[analysis_id]["target_role_benchmark"] = benchmark.model_dump()
        _in_memory_analyses[analysis_id]["skill_evaluations"] = [e.model_dump() for e in new_evaluations]
        _in_memory_analyses[analysis_id]["updated_at"] = now.isoformat()

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["resume_analyses"].update_one(
                {"_id": analysis_id},
                {
                    "$set": {
                        "target_role": role_def.role_name,
                        "experience_level": experience_level,
                        "target_role_benchmark": benchmark.model_dump(),
                        "skill_evaluations": [e.model_dump() for e in new_evaluations],
                        "updated_at": now.isoformat(),
                    }
                },
            )
        except Exception as exc:
            logger.warning("MongoDB update failed for resume %s: %s", analysis_id, type(exc).__name__)

    refreshed = await get_resume_analysis(analysis_id)
    return refreshed or analysis
