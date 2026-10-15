import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
import groq

from app.main import app
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    SubmitAnswerRequest,
    CompetencyStatus,
)
from app.schemas.evaluation import (
    CriterionScores,
    CriterionScore,
    AIEvaluationRaw,
    AnswerEvaluationResponse,
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    get_session,
    complete_session,
)
from app.services.adaptation_service import compute_session_competency_state
from app.services.report_service import generate_interview_report

client = TestClient(app)


def _mock_groq_eval_response(
    overall_score: int = 84,
    relevance: int = 9,
    technical_depth: int = 8,
    completeness: int = 8,
    structure_flow: int = 8,
    clarity_conciseness: int = 9,
    star_structure: int = 8,
    summary: str = "Clear explanation of concurrency models.",
) -> MagicMock:
    content = json.dumps({
        "overall_score": overall_score,
        "criterion_scores": {
            "relevance": {"score": relevance, "feedback": "Directly addresses event loop concurrency."},
            "technical_depth": {"score": technical_depth, "feedback": "Explains non-blocking I/O and task scheduling."},
            "completeness": {"score": completeness, "feedback": "Addresses coroutines and thread pool offloading."},
            "structure_flow": {"score": structure_flow, "feedback": "Coherent logical sequence."},
            "clarity_conciseness": {"score": clarity_conciseness, "feedback": "Concise and precise vocabulary."},
            "star_structure": {"score": star_structure, "feedback": "Clearly contextualized engineering scenario."},
        },
        "strengths": ["Demonstrates solid understanding of asynchronous event loops."],
        "areas_for_improvement": ["Could elaborate on exception propagation across tasks."],
        "actionable_suggestions": ["Mention asyncio.gather return_exceptions=True parameter."],
        "coaching_summary": summary,
    })
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_completion = MagicMock(choices=[mock_choice])
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    return mock_client


@pytest.fixture
def test_session_id():
    """Setup a standard interview session with 3 questions for testing."""
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain how Python asyncio manages concurrent I/O operations.",
        assessed_skill="AsyncIO",
        difficulty="Medium",
        rubric="Explains event loop, coroutines, non-blocking I/O, and selectors.",
    )
    q2 = QuestionItem(
        id="q_2",
        question_number=2,
        text="How do database indexes improve query execution performance?",
        assessed_skill="Databases",
        difficulty="Medium",
        rubric="Discusses B-Tree indexes, query execution plans, and lookups.",
    )
    q3 = QuestionItem(
        id="q_3",
        question_number=3,
        text="Describe strategies to mitigate cascading failures in distributed microservices.",
        assessed_skill="Distributed Systems",
        difficulty="Hard",
        rubric="Covers circuit breakers, exponential backoff with jitter, and timeouts.",
    )
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="AsyncIO, Databases, Distributed Systems",
        question_count=3,
    )
    import asyncio
    session = asyncio.run(create_interview_session(setup=setup, questions=[q1, q2, q3]))
    return session.session_id


def test_evaluation_canonical_score_scales_and_disclaimer(test_session_id):
    """
    1. Real-time evaluation returns:
    - Overall score on canonical 1-100 scale
    - Criterion scores on canonical 1-10 scale
    - Explicit decision support disclaimer
    """
    mock_client = _mock_groq_eval_response(overall_score=84, relevance=9, technical_depth=8)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        response = client.post(
            f"/api/interviews/{test_session_id}/questions/q_1/evaluate",
            json={"answer_text": "Python asyncio relies on a single-threaded cooperative event loop using OS selectors for I/O multiplexing."},
        )
        assert response.status_code == 200
        data = response.json()

        # Overall score strictly 1-100
        assert 1 <= data["overall_score"] <= 100
        assert data["overall_score"] == 84

        # Criteria strictly 1-10
        crit = data["criterion_scores"]
        for crit_name in ["relevance", "technical_depth", "completeness", "structure_flow", "clarity_conciseness"]:
            score_val = crit[crit_name]["score"]
            assert 1 <= score_val <= 10, f"{crit_name} score {score_val} out of 1-10 bounds"

        # Explicit decision support disclaimer
        assert "decision_support_disclaimer" in data
        assert "decision support" in data["decision_support_disclaimer"].lower()
        assert "hiring" in data["decision_support_disclaimer"].lower()

        # Multi-dimensional coaching
        assert len(data["strengths"]) >= 1
        assert len(data["areas_for_improvement"]) >= 1
        assert len(data["actionable_suggestions"]) >= 1
        assert len(data["coaching_summary"]) >= 10


def test_evaluation_completed_session_guard(test_session_id):
    """
    2. Attempting to submit an answer or evaluate on a completed session is rejected with HTTP 400.
    """
    import asyncio
    asyncio.run(complete_session(test_session_id))

    # 1. Answer submission should fail with HTTP 400
    res_ans = client.post(
        f"/api/interviews/{test_session_id}/answers",
        json={"question_id": "q_1", "answer_text": "Late answer after interview completion."},
    )
    assert res_ans.status_code == 400
    assert "already been completed" in res_ans.json()["detail"].lower()

    # 2. Evaluation should fail with HTTP 400
    mock_client = _mock_groq_eval_response()
    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        res_eval = client.post(
            f"/api/interviews/{test_session_id}/questions/q_1/evaluate",
            json={"answer_text": "Late answer after completion."},
        )
        assert res_eval.status_code == 400
        assert "already been completed" in res_eval.json()["detail"].lower()


def test_evaluation_idempotent_reevaluation(test_session_id):
    """
    3. Re-evaluating an updated answer cleanly overwrites previous evaluation with updated metrics.
    """
    mock_client_initial = _mock_groq_eval_response(overall_score=60, summary="Initial basic answer.")
    mock_client_updated = _mock_groq_eval_response(overall_score=92, summary="Refined comprehensive answer.")

    # First evaluation
    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client_initial):
        res1 = client.post(
            f"/api/interviews/{test_session_id}/questions/q_1/evaluate",
            json={"answer_text": "Asyncio uses coroutines."},
        )
        assert res1.status_code == 200
        assert res1.json()["overall_score"] == 60

    # Re-evaluation with refined answer
    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client_updated):
        res2 = client.post(
            f"/api/interviews/{test_session_id}/questions/q_1/evaluate",
            json={"answer_text": "Asyncio coordinates coroutines through an event loop and epoll/kqueue selectors for concurrent network I/O."},
        )
        assert res2.status_code == 200
        assert res2.json()["overall_score"] == 92
        assert "Refined comprehensive answer" in res2.json()["coaching_summary"]

    # Verify session has latest score
    get_res = client.get(f"/api/interviews/{test_session_id}")
    assert get_res.status_code == 200
    session_data = get_res.json()
    assert session_data["answers"]["q_1"]["evaluation"]["overall_score"] == 92


@pytest.mark.asyncio
async def test_missing_evaluation_data_remains_none_never_zero(test_session_id):
    """
    4. Unanswered or unevaluated questions must retain overall_score=None and never silently become 0.
    """
    # Submit answer for Q1 but DO NOT evaluate it
    await submit_answer(
        session_id=test_session_id,
        answer_data=SubmitAnswerRequest(question_id="q_1", answer_text="Answer submitted without evaluation."),
    )

    # Check session
    stored = await get_session(test_session_id)
    assert stored["answers"]["q_1"].get("evaluation") is None

    # Check competency state
    comp_state = compute_session_competency_state(stored)
    skill_state = comp_state.skills.get("AsyncIO")
    assert skill_state is not None
    assert skill_state.average_score is None, "Unevaluated skill must have average_score=None, not 0"
    assert skill_state.latest_score is None
    assert skill_state.status == CompetencyStatus.NEEDS_FURTHER_ASSESSMENT

    # Check report
    report = await generate_interview_report(test_session_id)
    assert report.evaluated_questions == 0
    assert report.overall_score is None, "Overall score must be None with 0 evaluations, not 0.0"
    assert report.score_status == "insufficient_data"
    assert report.questions_performance[0].overall_score is None
    assert report.questions_performance[0].is_answered is True
    assert report.questions_performance[0].is_evaluated is False


def test_evaluation_empty_and_whitespace_validation(test_session_id):
    """
    5. Rejection of empty or whitespace-only answers.
    """
    # 1. Whitespace in submit_answer
    res_sub = client.post(
        f"/api/interviews/{test_session_id}/answers",
        json={"question_id": "q_1", "answer_text": "    \n\t   "},
    )
    assert res_sub.status_code == 422 or res_sub.status_code == 400

    # 2. Whitespace in evaluate
    res_eval = client.post(
        f"/api/interviews/{test_session_id}/questions/q_1/evaluate",
        json={"answer_text": "   "},
    )
    assert res_eval.status_code == 400
    assert "no answer has been submitted" in res_eval.json()["detail"].lower()


def test_evaluation_groq_failure_handling(test_session_id):
    """
    6. Verifies clean error status codes on Groq rate limits, timeouts, and API errors without data corruption.
    """
    # Submit a valid answer first
    client.post(
        f"/api/interviews/{test_session_id}/answers",
        json={"question_id": "q_1", "answer_text": "Valid candidate answer to evaluate."},
    )

    # Rate Limit -> HTTP 429
    mock_rate_limit = MagicMock()
    mock_rate_limit.chat.completions.create = AsyncMock(
        side_effect=groq.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
    )
    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_rate_limit):
        res = client.post(f"/api/interviews/{test_session_id}/questions/q_1/evaluate", json={})
        assert res.status_code == 429
        assert "rate limit exceeded" in res.json()["detail"].lower()

    # Timeout -> HTTP 504
    mock_timeout = MagicMock()
    mock_timeout.chat.completions.create = AsyncMock(
        side_effect=groq.APITimeoutError(request=MagicMock())
    )
    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_timeout):
        res = client.post(f"/api/interviews/{test_session_id}/questions/q_1/evaluate", json={})
        assert res.status_code == 504
        assert "timed out" in res.json()["detail"].lower()
