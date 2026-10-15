import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token, ROLE_CANDIDATE
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    QuestionType,
    SubmitAnswerRequest,
)
from app.schemas.evaluation import (
    AIEvaluationRaw,
    CriterionScores,
    CriterionScore,
)
from app.services.session_service import (
    create_interview_session,
    get_session,
    submit_answer,
)

client = TestClient(app)


@pytest.fixture
def sample_evaluation():
    return AIEvaluationRaw(
        overall_score=82,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=8, feedback="Direct and relevant"),
            technical_depth=CriterionScore(score=8, feedback="Strong architectural grasp"),
            completeness=CriterionScore(score=8, feedback="Comprehensive coverage"),
            structure_flow=CriterionScore(score=9, feedback="Well organized"),
            clarity_conciseness=CriterionScore(score=8, feedback="Crisp and clear"),
        ),
        strengths=["Clear architectural explanation"],
        areas_for_improvement=["Could elaborate on cache invalidation"],
        actionable_suggestions=["Discuss Redis vs Memcached"],
        coaching_summary="Well structured technical answer.",
    )


@pytest.mark.asyncio
async def test_session_creation_initializes_active_question_id():
    """Verify that starting an interview session initializes active_question_id to the first question."""
    req = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        focus_areas="FastAPI, PostgreSQL",
    )
    questions = [
        QuestionItem(
            id="q_active_1",
            question_number=1,
            text="How do you structure database connection pooling in FastAPI?",
            assessed_skill="PostgreSQL",
            difficulty="Medium",
            rubric="Demonstrates connection lifecycle and async engines in depth.",
            question_type="coding",
        )
    ]
    session = await create_interview_session(req, questions=questions, owner_id="candidate_123")
    assert session.active_question_id == "q_active_1"
    assert len(session.questions) == 1
    assert session.questions[0].question_type == QuestionType.CODING.value


@pytest.mark.asyncio
async def test_reject_unissued_question_submission():
    """The backend must reject answers for questions that were never issued to the session."""
    req = InterviewSetupRequest(
        role="Frontend Engineer",
        experience_level="Senior",
        focus_areas="React, TypeScript",
    )
    questions = [
        QuestionItem(
            id="q_issued_1",
            question_number=1,
            text="Explain the React reconciliation algorithm and Fiber architecture.",
            assessed_skill="React",
            difficulty="Hard",
            rubric="Deep understanding of Fiber trees and concurrent rendering.",
            question_type="verbal",
        )
    ]
    session = await create_interview_session(req, questions=questions, owner_id="candidate_456")

    # Attempt to answer an unissued question (e.g. skipping forward)
    answer_req = SubmitAnswerRequest(
        question_id="q_future_unissued_999",
        answer_text="Skipping forward to future question",
    )

    with pytest.raises(Exception) as exc_info:
        await submit_answer(session.session_id, answer_req)
    err = str(exc_info.value).lower()
    assert "not found in this session" in err or "unissued" in err or "400" in err


def test_cross_candidate_answer_submission_forbidden():
    """Verify that candidate A cannot submit an answer to candidate B's session."""
    token_a = create_access_token(user_id="user_a_id", role=ROLE_CANDIDATE, name="Candidate A")
    token_b = create_access_token(user_id="user_b_id", role=ROLE_CANDIDATE, name="Candidate B")

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "id": "q_session_a",
        "question_number": 1,
        "text": "Describe how you optimize React bundle sizes.",
        "assessed_skill": "React",
        "difficulty": "Medium",
        "rubric": "Mentions code splitting and tree shaking clearly.",
        "question_type": "verbal",
        "selection_rationale": "Initial React question.",
    })
    mock_completion = MagicMock(choices=[mock_choice])
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    # Candidate A creates session
    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        res_create = client.post(
            "/api/interviews/setup",
            json={"role": "Frontend", "experience_level": "Mid-Level", "focus_areas": "React", "adaptive": True},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res_create.status_code == 201
        session_id = res_create.json()["session_id"]

    created_session = res_create.json()
    active_q = created_session.get("active_question_id") or created_session["questions"][0]["id"]

    # Candidate B attempts to submit answer to Candidate A's session -> must receive 403 Forbidden
    res_b_submit = client.post(
        f"/api/interviews/{session_id}/answer",
        json={"question_id": active_q, "answer_text": "Unauthorized answer from candidate B"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b_submit.status_code == 403
    assert "forbidden" in res_b_submit.json()["detail"].lower()


def test_atomic_submit_and_adapt_lifecycle():
    """Test the atomic submit-and-adapt endpoint updates competency and returns next question."""
    token = create_access_token(user_id="adaptive_candidate", role=ROLE_CANDIDATE, name="Adaptive Candidate")
    headers = {"Authorization": f"Bearer {token}"}

    mock_choice_init = MagicMock()
    mock_choice_init.message.content = json.dumps({
        "id": "q_1",
        "question_number": 1,
        "text": "Two Sum problem: return indices of numbers summing to target.",
        "assessed_skill": "Data Structures",
        "difficulty": "Easy",
        "rubric": "Hash map O(N) solution with clear time complexity.",
        "question_type": "coding",
        "selection_rationale": "Initial baseline problem.",
    })
    mock_comp_init = MagicMock(choices=[mock_choice_init])
    mock_client_init = MagicMock()
    mock_client_init.chat.completions.create = AsyncMock(return_value=mock_comp_init)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client_init):
        create_res = client.post(
            "/api/interviews/setup",
            json={"role": "Software Engineer", "experience_level": "Mid-Level", "focus_areas": "DSA", "target_question_count": 3, "adaptive": True},
            headers=headers,
        )
        assert create_res.status_code == 201
        session_data = create_res.json()
        session_id = session_data["session_id"]
        q_id = session_data.get("active_question_id") or session_data["questions"][0]["id"]

    # Mock evaluate and adaptive generation
    eval_json = {
        "overall_score": 85,
        "criterion_scores": {
            "relevance": {"score": 9, "feedback": "Direct solution"},
            "technical_depth": {"score": 8, "feedback": "Good time complexity"},
            "completeness": {"score": 8, "feedback": "Handles all constraints"},
            "structure_flow": {"score": 9, "feedback": "Clean code"},
            "clarity_conciseness": {"score": 9, "feedback": "Concise"},
        },
        "strengths": ["Clean hash map logic"],
        "areas_for_improvement": ["Consider space complexity optimization"],
        "actionable_suggestions": ["Test with negative numbers"],
        "coaching_summary": "Great problem solving.",
    }
    next_q_json = {
        "id": "q_step_2",
        "question_number": 2,
        "text": "Longest Substring Without Repeating Characters.",
        "assessed_skill": "Sliding Window",
        "difficulty": "Medium",
        "rubric": "Sliding window with set or map in O(N) time.",
        "question_type": "coding",
        "selection_rationale": "Strong performance on Two Sum leads to sliding window.",
    }

    mock_client_adapt = MagicMock()
    mock_choice_eval = MagicMock()
    mock_choice_eval.message.content = json.dumps(eval_json)
    mock_choice_next = MagicMock()
    mock_choice_next.message.content = json.dumps(next_q_json)

    # First call evaluates, second call adapts
    mock_client_adapt.chat.completions.create = AsyncMock(side_effect=[
        MagicMock(choices=[mock_choice_eval]),
        MagicMock(choices=[mock_choice_next]),
    ])

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client_adapt):
        submit_adapt_res = client.post(
            f"/api/interviews/{session_id}/submit-and-adapt",
            json={
                "question_id": q_id,
                "code": "def twoSum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen: return [seen[target-n], i]\n        seen[n] = i",
                "language": "python",
                "answer_text": "[DSA Python Solution - All Tests Passed]",
            },
            headers=headers,
        )
        assert submit_adapt_res.status_code == 200
        data = submit_adapt_res.json()
        assert data["session_id"] == session_id
        assert data["question_id"] == q_id
        assert data["evaluation"]["overall_score"] == 85
        assert data["next_question"]["id"] == "q_2"
        assert data["active_question_id"] == "q_2"
        assert data["is_last_question"] is False


def test_question_type_canonical_normalization():
    """Verify that question types normalize legacy and diverse values safely."""
    q_coding = QuestionItem(
        id="q_1",
        question_number=1,
        text="Coding question",
        assessed_skill="Python",
        difficulty="Easy",
        rubric="Comprehensive evaluation of code correctness and runtime.",
        question_type="coding_dsa",
    )
    assert q_coding.question_type == QuestionType.CODING.value

    q_sql = QuestionItem(
        id="q_2",
        question_number=2,
        text="SQL question",
        assessed_skill="SQL",
        difficulty="Medium",
        rubric="Comprehensive evaluation of SQL schema relations.",
        question_type="sql",
    )
    assert q_sql.question_type == QuestionType.SQL.value

    q_sys = QuestionItem(
        id="q_3",
        question_number=3,
        text="Design a distributed cache",
        assessed_skill="System Design",
        difficulty="Hard",
        rubric="Comprehensive architectural evaluation of scale and bottlenecks.",
        question_type="system_design",
    )
    assert q_sys.question_type == QuestionType.SYSTEM_DESIGN.value
