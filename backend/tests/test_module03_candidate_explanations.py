from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.schemas.integrity import IntegrityEventType, IntegrityEventCreate
from app.schemas.evaluation import AnswerEvaluationResponse, CriterionScores, CriterionScore
from app.schemas.interview import SubmitAnswerRequest
from app.services.session_service import (
    submit_answer,
    save_evaluation,
    record_integrity_event,
    complete_session,
    record_candidate_explanation,
    get_candidate_explanations,
)
from app.services.report_service import get_interview_report


def create_test_session(client: TestClient) -> str:
    """Helper to create an active test session for candidate explanation tests."""
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
                "role": "Distributed Systems Engineer",
                "focus_areas": "Concurrency, Storage",
                "question_count": 3,
            },
        )
        assert res.status_code == 201
        return res.json()["session_id"]


def test_submit_session_level_candidate_explanation_success(client: TestClient):
    """Test valid session-level explanation submission and retrieval."""
    session_id = create_test_session(client)

    response = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={
            "explanation": "I was using a dual-monitor setup and occasionally looked over to review API reference notes.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == session_id
    assert data["event_id"] is None
    assert "dual-monitor setup" in data["explanation"]
    assert data["status"] == "pending_review"
    assert data["reviewer_outcome"] is None
    assert data["is_verified_identity"] is False
    assert "unauthenticated" in data["identity_note"].lower()
    assert "explanation_id" in data
    assert "created_at" in data

    # Retrieve via GET endpoint
    get_res = client.get(f"/api/interviews/{session_id}/integrity-explanations")
    assert get_res.status_code == 200
    trail = get_res.json()
    assert len(trail) == 1
    assert trail[0]["explanation_id"] == data["explanation_id"]
    assert trail[0]["explanation"] == data["explanation"]


@pytest.mark.asyncio
async def test_submit_event_linked_candidate_explanation_success(client: TestClient):
    """Test candidate explanation explicitly linked to an observed integrity event."""
    session_id = create_test_session(client)

    # Record a tab_hidden event
    event = await record_integrity_event(
        session_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.TAB_HIDDEN,
            question_id="q_1",
            details={"reason": "browser_tab_switched"},
        ),
    )

    response = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={
            "event_id": event.event_id,
            "explanation": "A system calendar reminder popped up on screen which caused the tab to briefly lose focus.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == session_id
    assert data["event_id"] == event.event_id
    assert "calendar reminder" in data["explanation"]
    assert data["status"] == "pending_review"


def test_reject_nonexistent_session_id(client: TestClient):
    """Test HTTP 404 when session_id does not exist."""
    response = client.post(
        "/api/interviews/non-existent-session-uuid/integrity-explanations",
        json={"explanation": "Context note about non-existent session."},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    get_res = client.get("/api/interviews/non-existent-session-uuid/integrity-explanations")
    assert get_res.status_code == 404


def test_reject_unassociated_event_id(client: TestClient):
    """Test HTTP 400 when an event_id is supplied that does not exist in the session."""
    session_id = create_test_session(client)

    response = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={
            "event_id": "fake-event-uuid-not-in-session",
            "explanation": "Context note for an invalid event ID.",
        },
    )
    assert response.status_code == 400
    assert "fake-event-uuid-not-in-session" in response.json()["detail"]


def test_reject_blank_and_too_short_explanation(client: TestClient):
    """Test validation rejection (HTTP 422) for blank or < 5 characters explanation."""
    session_id = create_test_session(client)

    # Empty string
    r1 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": ""},
    )
    assert r1.status_code == 422

    # Whitespace only
    r2 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "    "},
    )
    assert r2.status_code == 422

    # Fewer than 5 non-whitespace characters
    r3 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": " hey "},
    )
    assert r3.status_code == 422


def test_reject_oversized_explanation(client: TestClient):
    """Test validation rejection (HTTP 422) for explanation > 2000 characters."""
    session_id = create_test_session(client)

    oversized = "A" * 2001
    response = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": oversized},
    )
    assert response.status_code == 422


def test_multiple_explanations_preserve_complete_history(client: TestClient):
    """Test multiple explanations preserve their full chronological history without overwriting."""
    session_id = create_test_session(client)

    r1 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "First explanation: incoming email notification."},
    )
    assert r1.status_code == 201
    id1 = r1.json()["explanation_id"]

    r2 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Second explanation: laptop charger was plugged in."},
    )
    assert r2.status_code == 201
    id2 = r2.json()["explanation_id"]

    assert id1 != id2

    # Verify both are present in order
    get_res = client.get(f"/api/interviews/{session_id}/integrity-explanations")
    assert get_res.status_code == 200
    trail = get_res.json()
    assert len(trail) == 2
    assert trail[0]["explanation_id"] == id1
    assert trail[1]["explanation_id"] == id2
    assert "First explanation" in trail[0]["explanation"]
    assert "Second explanation" in trail[1]["explanation"]


@pytest.mark.asyncio
async def test_completed_session_permits_candidate_explanations(client: TestClient):
    """
    Test explicitly defined completed-session policy:
    Candidate explanations ARE permitted on completed sessions to allow post-interview context/disputes.
    """
    session_id = create_test_session(client)
    await complete_session(session_id)

    response = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Post-interview explanation regarding momentary screen blur during setup."},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == session_id
    assert "Post-interview explanation" in data["explanation"]


def test_persistence_transparency_in_memory_and_fallback(client: TestClient):
    """Verify accurate persistence status reported when MongoDB is unconfigured or unreachable."""
    session_id = create_test_session(client)

    # In unconfigured environment (MONGODB_URI is None)
    with patch("app.core.config.settings.MONGODB_URI", None):
        res = client.post(
            f"/api/interviews/{session_id}/integrity-explanations",
            json={"explanation": "Testing in-memory persistence metadata."},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["saved_to_db"] is False
        assert data["db_status"] == "unconfigured"

    # In unreachable environment (MONGODB_URI is set but database throws)
    with patch("app.core.config.settings.MONGODB_URI", "mongodb://localhost:27017"), \
         patch("app.core.database.db_manager.get_database", side_effect=RuntimeError("Connection refused")):
        res2 = client.post(
            f"/api/interviews/{session_id}/integrity-explanations",
            json={"explanation": "Testing unreachable database fallback metadata."},
        )
        assert res2.status_code == 201
        data2 = res2.json()
        assert data2["saved_to_db"] is False
        assert data2["db_status"] == "unreachable"


@pytest.mark.asyncio
async def test_score_isolation_strictly_preserved(client: TestClient):
    """
    Verify that submitting candidate explanations does NOT modify:
    - overall_score
    - criterion_averages
    - question evaluations
    - hiring recommendations
    """
    session_id = create_test_session(client)

    # Submit and evaluate an answer
    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(
            question_id="q_1",
            answer_text="We use atomic CAS operations, fine-grained mutexes, and thread synchronization primitives.",
        ),
    )
    eval_resp = AnswerEvaluationResponse(
        session_id=session_id,
        question_id="q_1",
        overall_score=85.0,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Direct and accurate concurrency answer."),
            technical_depth=CriterionScore(score=8, feedback="Solid atomic primitives discussion."),
            completeness=CriterionScore(score=8, feedback="Covers core sync requirements."),
            structure_flow=CriterionScore(score=9, feedback="Well organized technical response."),
            clarity_conciseness=CriterionScore(score=9, feedback="Concise and articulate."),
            star_structure=CriterionScore(score=8, feedback="Logical progression."),
        ),
        strengths=["Clear atomic primitive distinction"],
        areas_for_improvement=["Expand on memory model barriers"],
        actionable_suggestions=["Add acquire-release semantics"],
        coaching_summary="High technical grasp.",
        evaluated_at=datetime.now(timezone.utc),
        saved_to_db=False,
        db_status="unconfigured",
    )
    await save_evaluation(session_id, "q_1", eval_resp)

    # Generate initial report before explanation
    with patch("app.core.config.settings.GROQ_API_KEY", None):
        report_before = client.post(f"/api/interviews/{session_id}/report").json()

    score_before = report_before["overall_score"]
    crit_before = report_before["criterion_averages"]
    eval_count_before = report_before["evaluated_questions"]
    status_before = report_before["score_status"]
    recs_before = report_before["recommended_next_steps"]

    assert score_before == 85.0
    assert eval_count_before == 1

    # Submit candidate explanation
    exp_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={
            "explanation": "Context note submitted by candidate regarding dual monitor mouse drift.",
        },
    )
    assert exp_res.status_code == 201

    # Fetch report after explanation
    report_after = client.get(f"/api/interviews/{session_id}/report").json()

    # Assert strict score isolation
    assert report_after["overall_score"] == score_before
    assert report_after["criterion_averages"] == crit_before
    assert report_after["evaluated_questions"] == eval_count_before
    assert report_after["score_status"] == status_before
    assert report_after["recommended_next_steps"] == recs_before

    # Assert explanation is rendered in integrity_summary
    exps = report_after["integrity_summary"]["candidate_explanations"]
    assert len(exps) == 1
    assert exps[0]["explanation_id"] == exp_res.json()["explanation_id"]
    assert "dual monitor mouse drift" in exps[0]["explanation"]
