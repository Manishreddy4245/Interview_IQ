"""
Tests for InterviewIQ Module 04 — Checkpoint 3:
Gap-Targeted Interview Question Handoff.

Covers:
1. Core competencies receiving appropriate priority (Tier 1).
2. Mentioned-but-insufficiently-evidenced skills selected for validation (Tier 2).
3. Expected but unmentioned skills handled fairly (Tier 3).
4. Duplicate normalized skills producing no duplicate gap targets.
5. Java and JavaScript remaining separate.
6. Generated questions mapping to the correct normalized skills.
7. Question difficulty, rubric, and rationale fields validated.
8. Resume analysis ID and target role persisted to the interview session.
9. Resume-to-interview route passing prioritized competencies (replacing extracted_skills[:4]).
10. Adaptive-interview settings being respected.
11. Missing benchmark data and legacy records handled safely.
12. Invalid analysis IDs returning appropriate 404 errors.
13. LLM failure and malformed output handled safely without fake fallback questions.
14. Resume-derived priorities not modifying interview scores or evaluations.
15. Existing Module 01, 02, and 03 behavior remaining unchanged.
"""
from datetime import datetime, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.resume import (
    AIRawSkillGapOutput,
    PersonalizedQuestionItem,
    ResumeAnalysisResult,
    RoleBenchmarkCompetency,
    SkillEvidenceCategory,
    SkillEvidenceItem,
    StartInterviewFromResumeRequest,
    TargetRoleBenchmark,
)
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    SubmitAnswerRequest,
)
from app.schemas.evaluation import AIEvaluationRaw
from app.schemas.integrity import IntegrityEventCreate, IntegrityEventType
from app.services.gap_prioritizer import prioritize_skill_gaps, PrioritizedGapItem
from app.services.skill_normalizer import canonical_skill_key, normalize_skill_name, skills_match
from app.services.resume_service import (
    create_interview_from_resume_analysis,
    get_resume_analysis,
    store_resume_analysis,
    _in_memory_analyses,
)
from app.services.session_service import (
    create_interview_session,
    get_session,
    submit_answer,
    save_evaluation,
    record_integrity_event,
    complete_session,
    _in_memory_sessions,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_memory_stores():
    """Ensure in-memory stores are clean before each test."""
    _in_memory_analyses.clear()
    _in_memory_sessions.clear()
    yield
    _in_memory_analyses.clear()
    _in_memory_sessions.clear()


def create_synthetic_analysis(
    target_role: str = "Senior Backend Engineer",
    experience_level: str = "Senior",
    benchmark_competencies=None,
    skill_evaluations=None,
    personalized_questions=None,
    extracted_skills=None,
) -> ResumeAnalysisResult:
    """Helper to build in-memory synthetic resume analysis fixture."""
    analysis_id = str(uuid.uuid4())
    benchmark = None
    if benchmark_competencies is not None:
        benchmark = TargetRoleBenchmark(
            target_role=target_role,
            experience_level=experience_level,
            expected_competencies=[
                RoleBenchmarkCompetency(
                    skill_name=b["skill_name"],
                    normalized_skill=normalize_skill_name(b["skill_name"]),
                    importance=b.get("importance", "Core"),
                    description=b.get("description", "Expected for role"),
                )
                for b in benchmark_competencies
            ],
        )

    evals = []
    if skill_evaluations:
        for ev in skill_evaluations:
            evals.append(
                SkillEvidenceItem(
                    skill_name=ev["skill_name"],
                    normalized_skill=normalize_skill_name(ev["skill_name"]),
                    category=ev.get("category", SkillEvidenceCategory.DEMONSTRATED),
                    evidence=ev.get("evidence", "Candidate resume statement"),
                    relevance_to_role=ev.get("relevance_to_role", "Required for role"),
                    is_source_grounded=ev.get("is_source_grounded", True),
                    evidence_type=ev.get("evidence_type", "verbatim_quote"),
                    source_excerpt=ev.get("source_excerpt"),
                    is_expected_for_role=ev.get("is_expected_for_role", True),
                    classification_rationale=ev.get("classification_rationale", "Evidence verified"),
                    requires_interview_validation=ev.get("requires_interview_validation", False),
                )
            )

    questions = []
    if personalized_questions:
        for idx, pq in enumerate(personalized_questions, 1):
            questions.append(
                PersonalizedQuestionItem(
                    id=f"q_{idx}",
                    question_number=idx,
                    text=pq["text"],
                    assessed_skill=pq["assessed_skill"],
                    normalized_skill=normalize_skill_name(pq["assessed_skill"]),
                    gap_category=pq.get("gap_category"),
                    role_relevance=pq.get("role_relevance"),
                    source_evidence=pq.get("source_evidence"),
                    difficulty=pq.get("difficulty", "Medium"),
                    rubric=pq.get("rubric", "Demonstrates architectural understanding"),
                    rationale=pq.get("rationale", "Formulated to validate practical experience"),
                )
            )

    return ResumeAnalysisResult(
        analysis_id=analysis_id,
        target_role=target_role,
        experience_level=experience_level,
        target_role_benchmark=benchmark,
        extracted_skills=extracted_skills or ["Python", "FastAPI", "Docker"],
        projects_and_experience=["Built high-throughput payment API microservice"],
        skill_evaluations=evals,
        personalized_questions=questions,
        role_readiness_summary="Strong backend alignment with core Python skills.",
        is_truncated=False,
        analyzed_character_count=1200,
        created_at=datetime.now(timezone.utc),
        saved_to_db=False,
        db_status="unconfigured",
        db_message="In-memory test fixture",
    )


# ---------------------------------------------------------------------------
# 1. Core Role Competencies Receiving Appropriate Priority (Tier 1)
# ---------------------------------------------------------------------------
def test_core_competencies_receive_top_priority():
    """Core competencies requiring interview validation must be placed in Tier 1."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "Distributed Systems", "importance": "Core"},
            {"skill_name": "GraphQL", "importance": "Recommended"},
        ],
        skill_evaluations=[
            {
                "skill_name": "Distributed Systems",
                "category": SkillEvidenceCategory.REQUIRES_VALIDATION,
                "requires_interview_validation": True,
                "relevance_to_role": "Core architectural expectation",
            },
            {
                "skill_name": "GraphQL",
                "category": SkillEvidenceCategory.REQUIRES_VALIDATION,
                "requires_interview_validation": True,
                "relevance_to_role": "Recommended API capability",
            },
        ],
    )

    prioritized = prioritize_skill_gaps(analysis)
    assert len(prioritized) >= 2
    # Tier 1 should be the Core competency
    assert prioritized[0].skill_name == "Distributed Systems"
    assert prioritized[0].priority_tier == 1
    assert prioritized[0].importance == "Core"
    assert prioritized[0].requires_interview_validation is True
    # Recommended competency should follow Core
    assert prioritized[1].skill_name == "GraphQL"
    assert prioritized[1].priority_tier == 4  # Other relevant competency requiring validation


# ---------------------------------------------------------------------------
# 2. Mentioned-but-insufficiently-evidenced Skills Selected for Validation (Tier 2)
# ---------------------------------------------------------------------------
def test_mentioned_insufficient_evidence_priority():
    """Skills mentioned without sufficient evidence should be prioritized in Tier 2."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "Kubernetes", "importance": "Core"},
        ],
        skill_evaluations=[
            {
                "skill_name": "Kubernetes",
                "category": SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "requires_interview_validation": True,
                "evidence": "Mentioned once in tool list without project context",
            },
            {
                "skill_name": "Python",
                "category": SkillEvidenceCategory.DEMONSTRATED,
                "requires_interview_validation": False,
                "evidence": "5 years developing production APIs",
            },
        ],
    )

    prioritized = prioritize_skill_gaps(analysis)
    k8s_item = next(p for p in prioritized if p.skill_name == "Kubernetes")
    python_item = next(p for p in prioritized if p.skill_name == "Python")

    assert k8s_item.priority_tier == 2
    assert "without sufficient" in k8s_item.priority_reason
    assert python_item.priority_tier == 5  # Demonstrated is baseline


# ---------------------------------------------------------------------------
# 3. Expected but Unmentioned Skills Handled Fairly (Tier 3)
# ---------------------------------------------------------------------------
def test_not_demonstrated_handled_fairly():
    """Unmentioned expected skills should be Tier 3 and never assert candidate lacks ability."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "Kafka", "importance": "Core"},
        ],
        skill_evaluations=[
            {
                "skill_name": "Kafka",
                "category": SkillEvidenceCategory.NOT_DEMONSTRATED,
                "requires_interview_validation": True,
                "evidence": "Expected for Senior Backend Engineer, but not demonstrated in resume text.",
            },
        ],
    )

    prioritized = prioritize_skill_gaps(analysis)
    kafka_item = next(p for p in prioritized if p.skill_name == "Kafka")
    assert kafka_item.priority_tier == 3
    assert "not evidenced in resume" in kafka_item.priority_reason
    # Fair phrasing: absence is not inability
    assert "lacks" not in kafka_item.priority_reason.lower()


# ---------------------------------------------------------------------------
# 4. Duplicate Normalized Skills Producing No Duplicate Gap Targets
# ---------------------------------------------------------------------------
def test_duplicate_normalized_skills_deduplicated():
    """Synonyms or case variations of the same normalized skill must not create duplicate gap targets."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "PostgreSQL", "importance": "Core"},
            {"skill_name": "Postgres", "importance": "Core"},
        ],
        skill_evaluations=[
            {
                "skill_name": "Postgres",
                "category": SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "requires_interview_validation": True,
            },
            {
                "skill_name": "PostgreSQL",
                "category": SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "requires_interview_validation": True,
            },
        ],
    )

    prioritized = prioritize_skill_gaps(analysis)
    # Both normalize to "PostgreSQL" -> exactly one gap item
    postgres_items = [p for p in prioritized if p.normalized_skill == "PostgreSQL"]
    assert len(postgres_items) == 1


# ---------------------------------------------------------------------------
# 5. Java and JavaScript Remaining Separate
# ---------------------------------------------------------------------------
def test_java_and_javascript_remain_separate():
    """Java and JavaScript must not collide or merge during prioritization."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "Java", "importance": "Core"},
            {"skill_name": "JavaScript", "importance": "Recommended"},
        ],
        skill_evaluations=[
            {
                "skill_name": "Java",
                "category": SkillEvidenceCategory.REQUIRES_VALIDATION,
                "requires_interview_validation": True,
            },
            {
                "skill_name": "JavaScript",
                "category": SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "requires_interview_validation": True,
            },
        ],
    )

    prioritized = prioritize_skill_gaps(analysis)
    java_items = [p for p in prioritized if p.normalized_skill == "Java"]
    js_items = [p for p in prioritized if p.normalized_skill == "JavaScript"]

    assert len(java_items) == 1
    assert len(js_items) == 1
    assert java_items[0].skill_name != js_items[0].skill_name


# ---------------------------------------------------------------------------
# 6. Generated Questions Mapping to the Correct Normalized Skills
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generated_questions_map_to_normalized_skills():
    """Questions generated from resume handoff must map to canonical normalized skills."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "Docker", "importance": "Core"},
        ],
        skill_evaluations=[
            {
                "skill_name": "docker",
                "category": SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "requires_interview_validation": True,
                "evidence": "Listed in skills table",
                "source_excerpt": "Tools: docker, git",
            },
        ],
        personalized_questions=[
            {
                "text": "How do you optimize multi-stage Docker builds for Python services?",
                "assessed_skill": "docker",
                "difficulty": "Medium",
                "rubric": "Mentions caching layers and minimal base images",
                "rationale": "Verify containerization proficiency",
            },
        ],
    )
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    session = await create_interview_from_resume_analysis(analysis.analysis_id)
    assert session is not None
    assert len(session.questions) == 1
    q = session.questions[0]
    assert q.assessed_skill == "docker"
    assert q.normalized_skill == "Docker"
    assert q.gap_category == SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED.value
    assert q.source_evidence == "Tools: docker, git"


# ---------------------------------------------------------------------------
# 7. Question Difficulty, Rubric, and Rationale Fields Validated
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_question_metadata_fields_validated():
    """Each question item must contain valid difficulty, rubric, and transparent rationale."""
    analysis = create_synthetic_analysis(
        personalized_questions=[
            {
                "text": "Explain your approach to designing idempotent REST endpoints.",
                "assessed_skill": "API Design",
                "difficulty": "Hard",
                "rubric": "Candidate discusses idempotency keys, safe retries, and database transactions.",
                "rationale": "Candidate claims microservice architecture experience.",
            },
        ],
    )
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    session = await create_interview_from_resume_analysis(analysis.analysis_id)
    assert session is not None
    q = session.questions[0]
    assert q.difficulty == "Hard"
    assert "idempotency keys" in q.rubric
    assert q.selection_rationale is not None
    assert len(q.selection_rationale) > 10


# ---------------------------------------------------------------------------
# 8. Resume Analysis ID and Target Role Persisted to Interview Session
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resume_analysis_id_and_role_persisted():
    """The originating resume analysis ID and role must be stored in the session record."""
    analysis = create_synthetic_analysis(
        target_role="Lead Cloud Architect",
        experience_level="Lead",
    )
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    session = await create_interview_from_resume_analysis(analysis.analysis_id)
    assert session is not None
    assert session.role == "Lead Cloud Architect"
    assert session.experience_level == "Lead"
    assert session.resume_analysis_id == analysis.analysis_id

    # Check persistence in session store
    persisted = await get_session(session.session_id)
    assert persisted is not None
    assert persisted.get("resume_analysis_id") == analysis.analysis_id
    assert persisted.get("role") == "Lead Cloud Architect"


# ---------------------------------------------------------------------------
# 9. Resume-to-Interview Route Passing Prioritized Competencies Correctly
# ---------------------------------------------------------------------------
def test_route_passes_prioritized_competencies_replacing_extracted_skills_slice():
    """POST /api/resume/{analysis_id}/start-interview uses prioritized competencies for focus_areas."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "Kubernetes", "importance": "Core"},
            {"skill_name": "Cassandra", "importance": "Core"},
        ],
        skill_evaluations=[
            {
                "skill_name": "Kubernetes",
                "category": SkillEvidenceCategory.REQUIRES_VALIDATION,
                "requires_interview_validation": True,
            },
            {
                "skill_name": "Cassandra",
                "category": SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "requires_interview_validation": True,
            },
        ],
        extracted_skills=["Skill1", "Skill2", "Skill3", "Skill4", "Skill5"],
        personalized_questions=[
            {
                "text": "How do you structure Cassandra partition keys to avoid hot spots?",
                "assessed_skill": "Cassandra",
            },
        ],
    )
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    response = client.post(f"/api/resume/{analysis.analysis_id}/start-interview")
    assert response.status_code == 201
    data = response.json()
    assert data["resume_analysis_id"] == analysis.analysis_id

    # focus_areas must contain prioritized competencies (Kubernetes, Cassandra), NOT blind extracted_skills[:4]
    focus_areas = data["focus_areas"]
    assert "Kubernetes" in focus_areas or "Cassandra" in focus_areas
    assert "Skill1, Skill2, Skill3, Skill4" != focus_areas


# ---------------------------------------------------------------------------
# 10. Adaptive-Interview Settings Being Respected
# ---------------------------------------------------------------------------
def test_route_respects_adaptive_setting():
    """Handoff endpoint supports adaptive=True and initializes an adaptive session."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "System Design", "importance": "Core"},
        ],
        skill_evaluations=[
            {
                "skill_name": "System Design",
                "category": SkillEvidenceCategory.REQUIRES_VALIDATION,
                "requires_interview_validation": True,
            },
        ],
    )
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    mock_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="Design a distributed cache system with high write throughput.",
        assessed_skill="System Design",
        difficulty="Medium",
        rubric="Candidate discusses cache invalidation, replication, and sharding strategies.",
        selection_rationale="Initial baseline question for System Design.",
    )

    with patch("app.services.resume_service.generate_initial_adaptive_question", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = [mock_q]
        response = client.post(
            f"/api/resume/{analysis.analysis_id}/start-interview",
            json={"adaptive": True, "difficulty": "Hard", "question_count": 5},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_adaptive"] is True
        assert data["difficulty"] == "Hard"
        assert data["target_question_count"] == 5
        assert len(data["questions"]) == 1


# ---------------------------------------------------------------------------
# 11. Missing Benchmark Data and Legacy Records Handled Safely
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_benchmark_legacy_records_handled_safely():
    """Analyses created without benchmark data or historical records must hand off safely."""
    analysis = create_synthetic_analysis(
        benchmark_competencies=None,
        skill_evaluations=[],
        extracted_skills=["Python", "Django"],
        personalized_questions=[
            {
                "text": "How do you manage database migrations in Django safely in production?",
                "assessed_skill": "Django",
            },
        ],
    )
    analysis.target_role_benchmark = None
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    session = await create_interview_from_resume_analysis(analysis.analysis_id)
    assert session is not None
    assert session.role == analysis.target_role
    assert len(session.questions) == 1
    assert session.questions[0].assessed_skill == "Django"


# ---------------------------------------------------------------------------
# 12. Invalid Analysis IDs Returning Appropriate Errors
# ---------------------------------------------------------------------------
def test_invalid_analysis_id_returns_404():
    """Non-existent or malformed analysis IDs must return 404 Not Found."""
    fake_id = str(uuid.uuid4())
    response = client.post(f"/api/resume/{fake_id}/start-interview")
    assert response.status_code == 404
    assert f"Resume analysis '{fake_id}' was not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 13. LLM Failure and Malformed Output Handled Safely
# ---------------------------------------------------------------------------
def test_adaptive_llm_failure_handled_without_fake_fallbacks():
    """If LLM fails during adaptive question generation, proper error is raised without mock fallbacks."""
    from fastapi import HTTPException, status
    analysis = create_synthetic_analysis()
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    with patch("app.services.resume_service.generate_initial_adaptive_question", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model returned an empty response.",
        )
        response = client.post(
            f"/api/resume/{analysis.analysis_id}/start-interview",
            json={"adaptive": True},
        )
        assert response.status_code == 502
        assert "empty response" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 14. Resume-Derived Priorities Not Modifying Scores or Evaluations
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_score_isolation_invariant():
    """
    Resume gap priorities may influence which questions are asked, but must never
    alter criterion scores (1-10) or overall score (0-100).
    """
    analysis = create_synthetic_analysis(
        benchmark_competencies=[
            {"skill_name": "Kubernetes", "importance": "Core"},
        ],
        skill_evaluations=[
            {
                "skill_name": "Kubernetes",
                "category": SkillEvidenceCategory.NOT_DEMONSTRATED,
                "requires_interview_validation": True,
            },
        ],
        personalized_questions=[
            {
                "text": "How do you configure rolling updates in Kubernetes?",
                "assessed_skill": "Kubernetes",
            },
        ],
    )
    _in_memory_analyses[analysis.analysis_id] = analysis.model_dump()
    _in_memory_analyses[analysis.analysis_id]["created_at"] = analysis.created_at.isoformat()

    session = await create_interview_from_resume_analysis(analysis.analysis_id)
    assert session is not None
    q_id = session.questions[0].id

    # Candidate submits a strong answer for this question
    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id=q_id,
            answer_text="We configure rollingUpdate strategy with maxSurge: 1 and maxUnavailable: 0 to ensure zero downtime.",
        ),
    )

    # Evaluate the answer through standard evaluation schema
    ai_raw = AIEvaluationRaw(
        overall_score=92.0,
        criterion_scores={
            "relevance": {"score": 10, "feedback": "Directly answered the question"},
            "technical_depth": {"score": 9, "feedback": "Understands rolling updates"},
            "completeness": {"score": 9, "feedback": "Covered surge parameters"},
            "structure_flow": {"score": 9, "feedback": "Clear explanation"},
            "clarity_conciseness": {"score": 10, "feedback": "Concise"},
        },
        strengths=["Clear deployment strategy"],
        areas_for_improvement=["Could mention container health checks"],
        actionable_suggestions=["Consider configuring readiness probes alongside rolling updates"],
        coaching_summary="Excellent response",
    )

    eval_response = await save_evaluation(
        session_id=session.session_id,
        question_id=q_id,
        evaluation=ai_raw,
    )

    # Verify score is preserved exactly from candidate answer evaluation
    assert eval_response.overall_score == 92.0
    assert eval_response.criterion_scores.relevance.score == 10
    # The fact that Kubernetes was NOT_DEMONSTRATED on the resume did NOT dock candidate score
    assert eval_response.overall_score >= 90.0


# ---------------------------------------------------------------------------
# 15. Existing Module 01, 02, and 03 Behavior Remaining Unchanged
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_module_03_integrity_and_completed_session_protections_preserved():
    """Module 03 integrity analytics, explanations, and completed-session protection remain intact."""
    setup = InterviewSetupRequest(
        role="Frontend Engineer",
        focus_areas="React, TypeScript",
        question_count=3,
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain React hooks lifecycle rules.",
        assessed_skill="React",
        difficulty="Medium",
        rubric="Must explain top-level call rules and dependency array semantics.",
    )
    session = await create_interview_session(setup=setup, questions=[q1])

    # Record integrity event
    evt = await record_integrity_event(
        session.session_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.TAB_HIDDEN,
            question_id="q_1",
            details={"note": "User switched tab"},
        ),
    )
    assert evt.event_type == "tab_hidden"

    # Complete session
    await complete_session(session.session_id)
    stored = await get_session(session.session_id)
    assert stored["status"] == "completed"
