from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.schemas.integrity import IntegrityEventType, IntegrityEventCreate
from app.schemas.evaluation import AnswerEvaluationResponse, CriterionScores, CriterionScore
from app.schemas.interview import SubmitAnswerRequest
from app.services.session_service import submit_answer, save_evaluation, record_integrity_event, complete_session


def create_test_session(client: TestClient) -> str:
    """Helper to create an active test session for human review tests."""
    valid_ai_json = """{
      "questions": [
        {
          "id": "q_1",
          "question_number": 1,
          "text": "How do you handle race conditions in multi-threaded programs?",
          "assessed_skill": "Concurrency",
          "difficulty": "Medium",
          "rubric": "Evaluates mutexes, atomic operations, and memory barriers."
        },
        {
          "id": "q_2",
          "question_number": 2,
          "text": "Explain memory compaction algorithms in garbage collection.",
          "assessed_skill": "Memory Management",
          "difficulty": "Hard",
          "rubric": "Evaluates mark-sweep-compact, copying collectors, and fragmentation."
        },
        {
          "id": "q_3",
          "question_number": 3,
          "text": "What are zero-copy I/O techniques in modern operating systems?",
          "assessed_skill": "Operating Systems",
          "difficulty": "Hard",
          "rubric": "Evaluates sendfile, splice, and direct memory access."
        }
      ]
    }"""
    mock_choice = MagicMock()
    mock_choice.message.content = valid_ai_json
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        res = client.post(
            "/api/interviews/setup",
            json={
                "role": "Systems Software Engineer",
                "focus_areas": "Concurrency, Memory, Systems",
                "question_count": 3,
            },
        )
        assert res.status_code == 201
        return res.json()["session_id"]


def test_submit_human_review_success_and_retrieval(client: TestClient):
    """Verify that a reviewer can submit contextual audit notes and retrieve them."""
    session_id = create_test_session(client)

    response = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={
            "reviewer_name": "Lead Evaluator Sarah",
            "review_notes": "Candidate switched tabs briefly to check documentation during question setup. Telemetry verified benign.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["reviewer_name"] == "Lead Evaluator Sarah"
    assert "Candidate switched tabs" in data["review_notes"]
    assert data["is_verified_identity"] is False
    assert "Self-declared reviewer identity" in data["identity_note"]
    assert "note_id" in data
    assert "created_at" in data

    # Retrieve audit trail
    get_res = client.get(f"/api/interviews/{session_id}/integrity-review")
    assert get_res.status_code == 200
    trail = get_res.json()
    assert len(trail) == 1
    assert trail[0]["note_id"] == data["note_id"]
    assert trail[0]["reviewer_name"] == "Lead Evaluator Sarah"


def test_submit_human_review_preserves_multiple_entries(client: TestClient):
    """Verify that multiple reviewer notes are preserved in chronological order."""
    session_id = create_test_session(client)

    res1 = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={
            "reviewer_name": "Reviewer A",
            "review_notes": "First observation: Candidate had external audio notification.",
        },
    )
    assert res1.status_code == 201

    res2 = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={
            "reviewer_name": "Reviewer B",
            "review_notes": "Second observation: Candidate clarified the notification verbally.",
        },
    )
    assert res2.status_code == 201

    get_res = client.get(f"/api/interviews/{session_id}/integrity-review")
    assert get_res.status_code == 200
    trail = get_res.json()
    assert len(trail) == 2
    assert trail[0]["reviewer_name"] == "Reviewer A"
    assert trail[1]["reviewer_name"] == "Reviewer B"


def test_submit_human_review_anonymous_fallback(client: TestClient):
    """Verify that omitting reviewer_name cleanly falls back to Anonymous Reviewer."""
    session_id = create_test_session(client)

    response = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={
            "review_notes": "General audit observation recorded without declared author.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["reviewer_name"] == "Anonymous Reviewer"
    assert data["is_verified_identity"] is False


def test_submit_human_review_validation_rejects_blank_notes(client: TestClient):
    """Verify that blank, whitespace-only, or too short review notes are rejected with 422."""
    session_id = create_test_session(client)

    # Empty string
    res_empty = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={"reviewer_name": "Auditor", "review_notes": ""},
    )
    assert res_empty.status_code == 422

    # Whitespace only
    res_ws = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={"reviewer_name": "Auditor", "review_notes": "     "},
    )
    assert res_ws.status_code == 422

    # Fewer than 5 non-whitespace chars
    res_short = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={"reviewer_name": "Auditor", "review_notes": "abc"},
    )
    assert res_short.status_code == 422


def test_submit_human_review_validation_rejects_oversized_notes(client: TestClient):
    """Verify that notes exceeding 2000 characters are rejected with 422."""
    session_id = create_test_session(client)

    oversized = "x" * 2001
    response = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={"reviewer_name": "Auditor", "review_notes": oversized},
    )
    assert response.status_code == 422


def test_submit_human_review_unknown_session_returns_404(client: TestClient):
    """Verify that submitting review for a non-existent session returns 404."""
    response = client.post(
        "/api/interviews/non-existent-session-1234/integrity-review",
        json={"reviewer_name": "Auditor", "review_notes": "Valid review note content here."},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_human_review_permitted_on_completed_session(client: TestClient):
    """
    Verify that human reviewers CAN record audit notes on completed interview sessions
    (evaluating the final session report), while candidate events remain rejected.
    """
    session_id = create_test_session(client)

    # Complete the session
    await complete_session(session_id)

    # Candidate integrity events must be rejected on completed session
    candidate_res = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "tab_hidden"},
    )
    assert candidate_res.status_code == 400

    # Human review MUST be permitted on completed sessions
    review_res = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={
            "reviewer_name": "Post-Interview Reviewer",
            "review_notes": "Final post-session audit note: telemetry indicates normal single-screen workspace.",
        },
    )
    assert review_res.status_code == 201
    data = review_res.json()
    assert data["reviewer_name"] == "Post-Interview Reviewer"


@pytest.mark.asyncio
async def test_strict_score_isolation_after_human_review(client: TestClient):
    """
    Verify that adding human review notes does NOT modify overall score, criterion scores,
    or report evaluation findings.
    """
    session_id = create_test_session(client)

    # Submit and evaluate an answer
    eval_q1 = AnswerEvaluationResponse(
        session_id=session_id,
        question_id="q_1",
        overall_score=85.0,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Direct and accurate description of mutex locks."),
            technical_depth=CriterionScore(score=8, feedback="Covers memory barriers and atomic compare-and-swap."),
            completeness=CriterionScore(score=9, feedback="Explains both deadlocks and livelocks."),
            structure_flow=CriterionScore(score=8, feedback="Clear logical progression."),
            clarity_conciseness=CriterionScore(score=9, feedback="Concise explanation without filler."),
        ),
        strengths=["Mutex understanding"],
        areas_for_improvement=["Could mention spinlocks"],
        actionable_suggestions=["Review spinlocks"],
        coaching_summary="Strong technical communication",
        evaluated_at=datetime.now(timezone.utc),
        saved_to_db=False,
        db_status="unconfigured",
    )

    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(question_id="q_1", answer_text="Mutexes ensure mutual exclusion."),
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=eval_q1)

    # Add a candidate integrity event
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(
            event_type=IntegrityEventType.TAB_HIDDEN,
            question_id="q_1",
        ),
    )

    # 1. Fetch initial report
    initial_rep = client.get(f"/api/interviews/{session_id}/report")
    assert initial_rep.status_code == 200
    initial_data = initial_rep.json()
    assert initial_data["overall_score"] == 85.0
    assert initial_data["criterion_averages"]["relevance"] == 9.0

    # 2. Add human review note
    review_res = client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={
            "reviewer_name": "Audit Lead",
            "review_notes": "Candidate tab switch was transient and correlated with question transition.",
        },
    )
    assert review_res.status_code == 201

    # 3. Fetch report again and verify strict score isolation
    post_rep = client.get(f"/api/interviews/{session_id}/report")
    assert post_rep.status_code == 200
    post_data = post_rep.json()

    # Scores must remain 100% unchanged
    assert post_data["overall_score"] == initial_data["overall_score"]
    assert post_data["score_status"] == initial_data["score_status"]
    assert post_data["criterion_averages"] == initial_data["criterion_averages"]

    # Human reviews must be included in report integrity summary
    reviews = post_data["integrity_summary"]["human_reviews"]
    assert len(reviews) == 1
    assert reviews[0]["reviewer_name"] == "Audit Lead"
    assert "Candidate tab switch was transient" in reviews[0]["review_notes"]
