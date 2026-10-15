import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.interview import InterviewSetupRequest, QuestionItem
from app.schemas.evaluation import AIEvaluationRaw, CriterionScores, CriterionScore
from app.schemas.integrity import IntegrityEventCreate, IntegrityEventType
from app.schemas.resume import (
    AIRawSkillGapOutput,
    SkillEvidenceCategory,
    SkillEvidenceItem,
    PersonalizedQuestionItem,
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    record_integrity_event,
)
from app.services.resume_service import store_resume_analysis
from app.schemas.interview import SubmitAnswerRequest

client = TestClient(app)


@pytest.fixture
def sample_questions():
    return [
        QuestionItem(
            id="q_1",
            question_number=1,
            text="Explain asynchronous programming in Python with asyncio.",
            assessed_skill="Python Async",
            difficulty="Medium",
            rubric="Explains event loop, coroutines, async/await syntax, and tasks.",
        ),
        QuestionItem(
            id="q_2",
            question_number=2,
            text="How do you index and optimize queries in PostgreSQL?",
            assessed_skill="PostgreSQL",
            difficulty="Medium",
            rubric="Discusses B-Tree indexes, EXPLAIN ANALYZE, and execution plans.",
        ),
        QuestionItem(
            id="q_3",
            question_number=3,
            text="Describe how you design a resilient retry mechanism with circuit breakers.",
            assessed_skill="System Architecture",
            difficulty="Hard",
            rubric="Mentions exponential backoff, jitter, failure thresholds, and half-open states.",
        ),
    ]


@pytest.fixture
def sample_evaluation_q1():
    return AIEvaluationRaw(
        overall_score=8,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Directly addresses asyncio."),
            technical_depth=CriterionScore(score=8, feedback="Covers event loop mechanics."),
            completeness=CriterionScore(score=8, feedback="Explains tasks and coroutines."),
            structure_flow=CriterionScore(score=8, feedback="Logical progression."),
            clarity_conciseness=CriterionScore(score=8, feedback="Clear technical vocabulary."),
        ),
        strengths=["Solid grasp of Python event loop", "Clear distinction between tasks and coroutines"],
        areas_for_improvement=["Discuss thread pool execution for blocking I/O"],
        actionable_suggestions=["Mention loop.run_in_executor for CPU-heavy tasks"],
        coaching_summary="Strong technical communication with structured explanations.",
    )


@pytest.fixture
def sample_evaluation_q2():
    return AIEvaluationRaw(
        overall_score=6,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=7, feedback="Discusses indexing basics."),
            technical_depth=CriterionScore(score=6, feedback="Basic mention of B-tree."),
            completeness=CriterionScore(score=6, feedback="Missed composite indexes."),
            structure_flow=CriterionScore(score=7, feedback="Good structure."),
            clarity_conciseness=CriterionScore(score=7, feedback="Concise answers."),
        ),
        strengths=["Understands index lookups"],
        areas_for_improvement=["Elaborate on EXPLAIN ANALYZE cost metrics"],
        actionable_suggestions=["Practice interpreting Postgres query plans"],
        coaching_summary="Good basic overview; deepen query execution plan analysis.",
    )


@pytest.mark.asyncio
async def test_report_insufficient_data_when_no_evaluations(sample_questions):
    """Verify that a session with 0 evaluated answers reports score as unavailable without zero-filling."""
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python, PostgreSQL",
        question_count=3,
    )
    session = await create_interview_session(setup=setup, questions=sample_questions)
    session_id = session.session_id

    response = client.get(f"/api/interviews/{session_id}/report")
    assert response.status_code == 200
    data = response.json()

    assert data["session_id"] == session_id
    assert data["total_questions"] == 3
    assert data["answered_questions"] == 0
    assert data["unanswered_questions"] == 3
    assert data["evaluated_questions"] == 0
    assert data["evaluation_coverage_pct"] == 0.0
    assert data["overall_score"] is None
    assert data["score_status"] == "insufficient_data"
    assert "cannot be calculated" in data["scoring_formula_explanation"].lower()
    assert data["has_resume_comparison"] is False
    assert data["saved_to_db"] is False
    assert data["db_status"] == "unconfigured"


@pytest.mark.asyncio
async def test_report_score_aggregation_and_integrity_isolation(
    sample_questions, sample_evaluation_q1, sample_evaluation_q2
):
    """
    Verify deterministic score aggregation across evaluated answers only:
    - Q1: score 8
    - Q2: score 6
    - Q3: unanswered (must NOT be treated as zero)
    - Mean score: (8 + 6) / 2 = 7.0
    - Coverage: 2 / 3 = 66.7%
    - Integrity events are recorded neutrally and strictly excluded from scoring.
    """
    setup = InterviewSetupRequest(
        role="Senior Backend Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Python, PostgreSQL, Architecture",
        question_count=3,
    )
    session = await create_interview_session(setup=setup, questions=sample_questions)
    session_id = session.session_id

    # Submit and evaluate Q1
    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(
            question_id="q_1",
            answer_text="Asyncio utilizes an event loop to schedule cooperative coroutines.",
        ),
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=sample_evaluation_q1)

    # Submit and evaluate Q2
    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(
            question_id="q_2",
            answer_text="I create B-Tree indexes on foreign keys and use EXPLAIN to check scans.",
        ),
    )
    await save_evaluation(session_id=session_id, question_id="q_2", evaluation=sample_evaluation_q2)

    # Record integrity events (tab switch + camera granted)
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(event_type=IntegrityEventType.TAB_HIDDEN),
    )
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(event_type=IntegrityEventType.TAB_VISIBLE),
    )

    # Fetch report
    response = client.get(f"/api/interviews/{session_id}/report")
    assert response.status_code == 200
    data = response.json()

    assert data["total_questions"] == 3
    assert data["answered_questions"] == 2
    assert data["unanswered_questions"] == 1
    assert data["evaluated_questions"] == 2
    assert data["evaluation_coverage_pct"] == 66.7

    # Aggregated score: (8 + 6) / 2 = 7.0
    assert data["overall_score"] == 7.0
    assert data["score_status"] == "calculated"

    # Criterion averages: relevance = (9 + 7)/2 = 8.0, tech_depth = (8 + 6)/2 = 7.0
    crit = data["criterion_averages"]
    assert crit["relevance"] == 8.0
    assert crit["technical_depth"] == 7.0

    # Integrity verification
    integ = data["integrity_summary"]
    assert integ["total_events"] == 2
    assert integ["events_summary"]["tab_hidden"] == 1
    assert integ["events_summary"]["tab_visible"] == 1
    assert "excluded from" in integ["score_impact"].lower()

    # Per question breakdown
    perf = data["questions_performance"]
    assert len(perf) == 3
    assert perf[0]["is_evaluated"] is True
    assert perf[0]["overall_score"] == 8.0
    assert perf[2]["is_answered"] is False
    assert perf[2]["is_evaluated"] is False
    assert perf[2]["overall_score"] is None


@pytest.mark.asyncio
async def test_report_with_associated_resume_analysis(sample_questions, sample_evaluation_q1):
    """Verify that sessions originating from a resume analysis correlate resume claims with interview performance."""
    # 1. Create resume analysis
    raw_ai_output = AIRawSkillGapOutput(
        extracted_skills=["Python Async", "Docker"],
        projects_and_experience=["Async backend service"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="Python Async",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Built async pipeline.",
                relevance_to_role="Core requirement.",
            ),
            SkillEvidenceItem(
                skill_name="Docker",
                category=SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                evidence="Brief keyword mention.",
                relevance_to_role="Containerization.",
            ),
        ],
        personalized_questions=[
            PersonalizedQuestionItem(
                id="q_1",
                question_number=1,
                text="Explain asynchronous programming in Python with asyncio.",
                assessed_skill="Python Async",
                difficulty="Medium",
                rubric="Event loop and tasks.",
                rationale="Validates async pipeline project.",
            )
        ],
        role_readiness_summary="Promising backend candidate.",
    )
    analysis = await store_resume_analysis(
        target_role="Async Python Developer",
        experience_level="Mid-Level",
        ai_output=raw_ai_output,
    )
    analysis_id = analysis.analysis_id

    # 2. Create session linked to this resume analysis
    setup = InterviewSetupRequest(
        role="Async Python Developer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python Async",
        question_count=3,
    )
    session = await create_interview_session(
        setup=setup,
        questions=sample_questions,
        resume_analysis_id=analysis_id,
    )
    session_id = session.session_id

    # 3. Submit and evaluate Q1
    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(
            question_id="q_1",
            answer_text="Asyncio schedules tasks on a single-threaded cooperative event loop.",
        ),
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=sample_evaluation_q1)

    # 4. Generate report
    response = client.post(f"/api/interviews/{session_id}/report")
    assert response.status_code == 200
    data = response.json()

    assert data["has_resume_comparison"] is True
    assert data["resume_comparison"] is not None
    assert data["resume_comparison"]["associated_analysis_id"] == analysis_id

    skills_comp = data["resume_comparison"]["skills_comparison"]
    assert len(skills_comp) == 2

    # Python Async was evaluated with score 8 -> "Demonstrated in Interview"
    python_item = next(i for i in skills_comp if i["skill_name"] == "Python Async")
    assert python_item["interview_status"] == "Demonstrated in Interview"

    # Docker was not tested -> "Claimed in Resume (Not Evaluated in Session)"
    docker_item = next(i for i in skills_comp if i["skill_name"] == "Docker")
    assert docker_item["interview_status"] == "Claimed in Resume (Not Evaluated in Session)"


def test_report_unknown_session_returns_404():
    """Verify that requesting a report for a non-existent session returns HTTP 404."""
    response = client.get("/api/interviews/non-existent-session-id/report")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_report_groq_failure_graceful_fallback(sample_questions, sample_evaluation_q1):
    """Verify that if Groq fails or times out during qualitative synthesis, the report falls back deterministically."""
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python",
        question_count=3,
    )
    session = await create_interview_session(setup=setup, questions=sample_questions)
    session_id = session.session_id

    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(question_id="q_1", answer_text="Answer text"),
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=sample_evaluation_q1)

    # Patch groq client to raise an exception
    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", side_effect=Exception("Groq API Timeout")):
        response = client.get(f"/api/interviews/{session_id}/report")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_score"] == 8.0
        assert "Backend Engineer" in data["executive_summary"]
        assert len(data["recommended_next_steps"]) > 0
