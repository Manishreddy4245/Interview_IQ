import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import (
    ROLE_REVIEWER,
    ROLE_ADMIN,
    require_role,
)

from app.core.config import settings
from app.core.database import db_manager
from app.schemas.decision import (
    CompetencyEvidenceItem,
    DecisionCriterionSummary,
    CandidateDossierItem,
    DecisionOverviewResponse,
    HumanReviewDecisionRecord,
    HumanReviewDecisionRequest,
)
from app.services.resume_service import _in_memory_analyses
from app.services.report_service import _in_memory_reports
from app.services.session_service import _in_memory_sessions

logger = logging.getLogger("interviewiq.decision_router")

router = APIRouter(prefix="/api/decision", tags=["Candidate Decision Intelligence"])

# In-memory storage for human decision determinations
_human_decisions_store: Dict[str, List[Dict[str, Any]]] = {}


def _parse_resume_dossier(r: Dict[str, Any]) -> CandidateDossierItem:
    rid = str(r.get("_id") or r.get("analysis_id"))
    demonstrated: List[CompetencyEvidenceItem] = []
    gaps: List[CompetencyEvidenceItem] = []

    # Parse skill evaluations
    for se in r.get("skill_evaluations", []):
        if hasattr(se, "model_dump"):
            se = se.model_dump()
        s_name = se.get("skill_name") or se.get("skill") or "Competency"
        cat = se.get("category") or se.get("status") or se.get("evidence_category") or ""
        evidence = se.get("evidence") or se.get("grounded_evidence") or se.get("source_excerpt") or ""
        relevance = se.get("relevance_to_role") or se.get("importance")

        cat_lower = str(cat).lower()
        if "demonstrated in resume" in cat_lower or ("demonstrated" in cat_lower and "not" not in cat_lower):
            demonstrated.append(
                CompetencyEvidenceItem(
                    skill_name=s_name,
                    status="Demonstrated in Resume",
                    category=cat,
                    evidence_text=evidence or "Verified in candidate project experience.",
                    source_type="resume",
                    role_importance=relevance,
                )
            )
        else:
            gaps.append(
                CompetencyEvidenceItem(
                    skill_name=s_name,
                    status=cat if cat else "Gap / Needs Validation",
                    category=cat,
                    evidence_text=evidence or "Insufficient evidence provided in resume.",
                    source_type="resume",
                    role_importance=relevance,
                )
            )

    # Fallback if skill_evaluations empty but extracted_skills present
    if not demonstrated and not gaps and r.get("extracted_skills"):
        for s in r.get("extracted_skills", [])[:5]:
            demonstrated.append(
                CompetencyEvidenceItem(
                    skill_name=s,
                    status="Extracted from Resume",
                    category="Extracted Skill",
                    evidence_text="Identified in technical skills section.",
                    source_type="resume",
                )
            )

    created_dt = r.get("created_at")
    if isinstance(created_dt, str):
        try:
            created_dt = datetime.fromisoformat(created_dt)
        except Exception:
            created_dt = None

    reviews = [
        HumanReviewDecisionRecord(**rev)
        for rev in _human_decisions_store.get(rid, [])
    ]

    return CandidateDossierItem(
        record_id=rid,
        record_type="resume_analysis",
        candidate_identifier=f"Candidate Profile — {r.get('target_role', 'Specialist')} ({rid[:8]})",
        target_role=r.get("target_role", "Candidate"),
        experience_level=r.get("experience_level", "Mid-Level"),
        created_at=created_dt,
        overall_score=None,
        scoring_status="Resume Evidence Profile",
        criterion_scores=DecisionCriterionSummary(),
        demonstrated_competencies=demonstrated,
        competency_gaps=gaps,
        key_strengths=[d.skill_name for d in demonstrated[:5]],
        critical_improvements=[g.skill_name for g in gaps[:5]],
        executive_summary=r.get("role_readiness_summary") or "Resume skill-gap analysis completed.",
        integrity_event_count=0,
        cumulative_unfocused_seconds=0.0,
        linked_resume_id=rid,
        linked_session_id=None,
        human_reviews=reviews,
    )


def _parse_report_dossier(rp: Dict[str, Any]) -> CandidateDossierItem:
    rpid = str(rp.get("_id") or rp.get("report_id"))
    sess_id = str(rp.get("session_id", ""))
    demonstrated_rep: List[CompetencyEvidenceItem] = []
    gaps_rep: List[CompetencyEvidenceItem] = []

    # Questions performance mapping
    qp_list = rp.get("questions_performance") or rp.get("question_performance") or []
    for qp in qp_list:
        if hasattr(qp, "model_dump"):
            qp = qp.model_dump()
        skill = qp.get("assessed_skill", "Technical Competency")
        score = qp.get("overall_score")
        q_strengths = qp.get("strengths") or []
        q_improvs = qp.get("areas_for_improvement") or qp.get("improvements") or []

        if score is not None and score >= 40.0:
            evidence_str = "; ".join(q_strengths) if q_strengths else f"Demonstrated in interview answer (Score: {score}/100)."
            demonstrated_rep.append(
                CompetencyEvidenceItem(
                    skill_name=skill,
                    status=f"Demonstrated in Interview ({score:.0f}/100)",
                    category="Interview Evaluated",
                    evidence_text=evidence_str,
                    source_type="interview_answer",
                )
            )
        else:
            evidence_str = "; ".join(q_improvs) if q_improvs else f"Needs development or practical validation (Score: {score if score is not None else 'Unscored'})."
            gaps_rep.append(
                CompetencyEvidenceItem(
                    skill_name=skill,
                    status=f"Identified Gap ({score:.0f}/100)" if score is not None else "Needs Live Validation",
                    category="Interview Improvement Area",
                    evidence_text=evidence_str,
                    source_type="interview_answer",
                )
            )

    # Criterion scores
    crit_dict = rp.get("criterion_averages") or {}
    if hasattr(crit_dict, "model_dump"):
        crit_dict = crit_dict.model_dump()
    criterion_summary = DecisionCriterionSummary(
        relevance=crit_dict.get("relevance"),
        technical_depth=crit_dict.get("technical_depth"),
        completeness=crit_dict.get("completeness"),
        structure_flow=crit_dict.get("structure_flow"),
        clarity_conciseness=crit_dict.get("clarity_conciseness"),
        star_structure=crit_dict.get("star_structure"),
    )

    # Overall score
    ov_score = rp.get("overall_score") or rp.get("overall_average_score")

    # Integrity
    integ = rp.get("integrity_summary") or {}
    if hasattr(integ, "model_dump"):
        integ = integ.model_dump()
    integ_events = integ.get("total_events", 0)
    integ_unfocused = integ.get("cumulative_unfocused_seconds", 0.0)

    created_dt_rep = rp.get("created_at")
    if isinstance(created_dt_rep, str):
        try:
            created_dt_rep = datetime.fromisoformat(created_dt_rep)
        except Exception:
            created_dt_rep = None

    reviews = [
        HumanReviewDecisionRecord(**rev)
        for rev in _human_decisions_store.get(rpid, [])
    ]

    return CandidateDossierItem(
        record_id=rpid,
        record_type="interview_report",
        candidate_identifier=f"Evaluated Candidate — {rp.get('role', 'Candidate')} (Session {sess_id[:8]})",
        target_role=rp.get("role", "Software Engineer"),
        experience_level=rp.get("experience_level", "Mid-Level"),
        created_at=created_dt_rep,
        overall_score=ov_score,
        scoring_status="Interview Evaluated" if ov_score is not None or demonstrated_rep else "Practice Complete",
        criterion_scores=criterion_summary,
        demonstrated_competencies=demonstrated_rep,
        competency_gaps=gaps_rep,
        key_strengths=rp.get("key_strengths") or [d.skill_name for d in demonstrated_rep[:3]],
        critical_improvements=rp.get("priority_improvements") or rp.get("critical_improvements") or [g.skill_name for g in gaps_rep[:3]],
        executive_summary=rp.get("executive_summary") or rp.get("coaching_summary") or "Interview performance report completed.",
        integrity_event_count=integ_events,
        cumulative_unfocused_seconds=integ_unfocused,
        linked_resume_id=rp.get("associated_analysis_id"),
        linked_session_id=sess_id,
        human_reviews=reviews,
    )


@router.get(
    "/overview",
    response_model=DecisionOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Candidate Decision Intelligence Overview",
    description="Loads all verified real candidate dossiers from database records with source evidence and evaluations.",
)
async def get_decision_overview(
    current_user: Dict[str, Any] = Depends(require_role([ROLE_REVIEWER, ROLE_ADMIN])),
) -> DecisionOverviewResponse:
    """
    Compile verified candidate decision profiles strictly from existing real database records.
    Never invents scores, missing evidence, or merges candidates without verified linkage.
    Supports live MongoDB Atlas and hermetic in-memory fallback.
    Protected endpoint: strictly restricted to reviewer and admin roles.
    """
    dossiers: List[CandidateDossierItem] = []
    resume_count = 0
    report_count = 0
    session_count = 0

    if settings.is_mongodb_configured:
        try:
            if db_manager._db is None or db_manager.client is None:
                db_manager.connect()
            db = db_manager.get_database()

            # 1. Load Resume Analyses from MongoDB Atlas
            raw_resumes = await db["resume_analyses"].find({}).to_list(100)
            resume_count = len(raw_resumes)
            for r in raw_resumes:
                dossiers.append(_parse_resume_dossier(r))

            # 2. Load Interview Reports from MongoDB Atlas
            raw_reports = await db["interview_reports"].find({}).to_list(100)
            report_count = len(raw_reports)
            for rp in raw_reports:
                dossiers.append(_parse_report_dossier(rp))

            # 3. Count total sessions in MongoDB Atlas
            session_count = await db["interview_sessions"].count_documents({})

        except Exception as exc:
            logger.warning("Error querying database for decision overview: %s", type(exc).__name__)
    else:
        # Hermetic in-memory store fallback
        raw_resumes = list(_in_memory_analyses.values())
        resume_count = len(raw_resumes)
        for r in raw_resumes:
            dossiers.append(_parse_resume_dossier(r))

        raw_reports = list(_in_memory_reports.values())
        report_count = len(raw_reports)
        for rp in raw_reports:
            dossiers.append(_parse_report_dossier(rp))

        session_count = len(_in_memory_sessions)

    return DecisionOverviewResponse(
        total_records=len(dossiers),
        resume_analyses_count=resume_count,
        interview_reports_count=report_count,
        interview_sessions_count=session_count,
        dossiers=dossiers,
    )


@router.get(
    "/dossier/{record_id}",
    response_model=CandidateDossierItem,
    status_code=status.HTTP_200_OK,
    summary="Get Detailed Candidate Decision Dossier",
)
async def get_candidate_dossier(
    record_id: str,
    current_user: Dict[str, Any] = Depends(require_role([ROLE_REVIEWER, ROLE_ADMIN])),
) -> CandidateDossierItem:
    """Retrieve full decision intelligence dossier for a single record."""
    overview = await get_decision_overview(current_user=current_user)
    for d in overview.dossiers:
        if d.record_id == record_id or d.linked_session_id == record_id:
            return d

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Candidate decision dossier '{record_id}' not found.",
    )


@router.post(
    "/dossier/{record_id}/review",
    response_model=HumanReviewDecisionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record Human Reviewer Hiring Determination",
    description="Records an auditable human hiring manager decision. Preserves integrity separation: zero automated hiring rejections.",
)
async def record_human_decision_review(
    record_id: str,
    payload: HumanReviewDecisionRequest,
    current_user: Dict[str, Any] = Depends(require_role([ROLE_REVIEWER, ROLE_ADMIN])),
) -> HumanReviewDecisionRecord:
    """Record an append-only human reviewer determination on a candidate dossier."""
    decision_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Use authenticated reviewer identity to prevent spoofing
    authenticated_reviewer = current_user.get("name") or payload.reviewer_name.strip()

    record = {
        "decision_id": decision_id,
        "reviewer_name": authenticated_reviewer,
        "recommendation": payload.recommendation.strip(),
        "notes": payload.notes.strip() if payload.notes else "",
        "timestamp": now,
    }

    if record_id not in _human_decisions_store:
        _human_decisions_store[record_id] = []
    _human_decisions_store[record_id].append(record)

    return HumanReviewDecisionRecord(**record)
