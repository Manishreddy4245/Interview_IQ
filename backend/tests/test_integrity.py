from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


def create_test_session_for_integrity(client: TestClient) -> str:
    """Helper to create an active test session for integrity tests."""
    valid_ai_json = """{
      "questions": [
        {
          "id": "q_1",
          "question_number": 1,
          "text": "How do you handle security vulnerabilities in an API?",
          "assessed_skill": "API Security",
          "difficulty": "Medium",
          "rubric": "Evaluates authentication, sanitization, and rate limiting."
        },
        {
          "id": "q_2",
          "question_number": 2,
          "text": "Explain HTTPS and TLS handshake protocols.",
          "assessed_skill": "Network Security",
          "difficulty": "Hard",
          "rubric": "Evaluates asymmetric and symmetric key exchange understanding."
        },
        {
          "id": "q_3",
          "question_number": 3,
          "text": "Describe your approach to protecting sensitive credentials in CI/CD.",
          "assessed_skill": "DevOps Security",
          "difficulty": "Medium",
          "rubric": "Evaluates secret managers, environment isolation, and access policies."
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
                "role": "Security Engineer",
                "focus_areas": "AppSec, Cryptography",
                "question_count": 3,
            },
        )
        assert res.status_code == 201
        return res.json()["session_id"]


def test_record_integrity_event_success(client: TestClient):
    """Test recording a valid observable integrity event."""
    session_id = create_test_session_for_integrity(client)

    response = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={
            "event_type": "tab_hidden",
            "details": {"context": "Candidate switched focus away from interview tab"},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == session_id
    assert data["event_type"] == "tab_hidden"
    assert "event_id" in data
    assert "timestamp" in data
    assert data["details"]["context"] == "Candidate switched focus away from interview tab"
    assert data["saved_to_db"] is False
    assert data["db_status"] == "unconfigured"


def test_record_invalid_event_type(client: TestClient):
    """Test 422 rejection when an invalid or unapproved event type is sent."""
    session_id = create_test_session_for_integrity(client)

    response = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={
            "event_type": "unapproved_custom_spy_action",
        },
    )
    assert response.status_code == 422


def test_record_integrity_event_missing_session(client: TestClient):
    """Test 404 rejection when session_id does not exist."""
    response = client.post(
        "/api/interviews/00000000-0000-0000-0000-000000000000/integrity-events",
        json={"event_type": "tab_visible"},
    )
    assert response.status_code == 404


def test_get_integrity_timeline(client: TestClient):
    """Test recording and retrieving the chronological integrity timeline."""
    session_id = create_test_session_for_integrity(client)

    # 1. Log camera permission granted
    client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "camera_mic_granted", "details": {"video": True, "audio": True}},
    )

    # 2. Log practice started
    client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "practice_started"},
    )

    # 3. Log tab hidden
    client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "tab_hidden"},
    )

    # 4. Log tab visible
    client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "tab_visible"},
    )

    # Retrieve timeline
    timeline_res = client.get(f"/api/interviews/{session_id}/integrity-events")
    assert timeline_res.status_code == 200
    timeline = timeline_res.json()
    assert timeline["session_id"] == session_id
    assert timeline["total_events"] == 4
    assert timeline["events"][0]["event_type"] == "camera_mic_granted"
    assert timeline["events"][1]["event_type"] == "practice_started"
    assert timeline["events"][2]["event_type"] == "tab_hidden"
    assert timeline["events"][3]["event_type"] == "tab_visible"
    assert timeline["saved_to_db"] is False
    assert timeline["db_status"] == "unconfigured"


def test_get_integrity_timeline_missing_session(client: TestClient):
    """Test 404 rejection when retrieving timeline for missing session."""
    response = client.get(
        "/api/interviews/00000000-0000-0000-0000-000000000000/integrity-events"
    )
    assert response.status_code == 404


def test_record_integrity_event_with_question_id(client: TestClient):
    """Checkpoint 1: Test associating integrity event with a valid question_id."""
    session_id = create_test_session_for_integrity(client)

    res = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={
            "event_type": "tab_hidden",
            "question_id": "q_1",
            "details": {"context": "Candidate switched focus while reading Q1"},
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["question_id"] == "q_1"
    assert data["event_type"] == "tab_hidden"

    # Verify timeline reflects question_id
    timeline_res = client.get(f"/api/interviews/{session_id}/integrity-events")
    assert timeline_res.status_code == 200
    timeline = timeline_res.json()
    assert timeline["events"][0]["question_id"] == "q_1"


def test_record_integrity_event_invalid_question_id(client: TestClient):
    """Checkpoint 1: Test 400 rejection when question_id does not belong to session."""
    session_id = create_test_session_for_integrity(client)

    res = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={
            "event_type": "tab_hidden",
            "question_id": "q_999",
        },
    )
    assert res.status_code == 400
    assert "does not belong to session" in res.json()["detail"].lower()


def test_record_integrity_event_completed_session_rejected(client: TestClient):
    """Checkpoint 1: Test backend rejection with HTTP 400 when session is completed."""
    session_id = create_test_session_for_integrity(client)

    # Mark session completed
    import asyncio
    from app.services.session_service import complete_session
    asyncio.run(complete_session(session_id))

    res = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={
            "event_type": "tab_hidden",
            "question_id": "q_1",
        },
    )
    assert res.status_code == 400
    assert "already been completed" in res.json()["detail"].lower()


def test_record_integrity_event_backward_compatible_no_question_id(client: TestClient):
    """Checkpoint 1: Events without question_id remain valid with question_id=None."""
    session_id = create_test_session_for_integrity(client)

    res = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "camera_mic_granted"},
    )
    assert res.status_code == 201
    assert res.json()["question_id"] is None


def test_record_distinct_window_blur_and_focus_events(client: TestClient):
    """Checkpoint 1: window_blur and window_focus are accepted as distinct signal types."""
    session_id = create_test_session_for_integrity(client)

    res_blur = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "window_blur", "question_id": "q_2"},
    )
    assert res_blur.status_code == 201
    assert res_blur.json()["event_type"] == "window_blur"
    assert res_blur.json()["question_id"] == "q_2"

    res_focus = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "window_focus", "question_id": "q_2"},
    )
    assert res_focus.status_code == 201
    assert res_focus.json()["event_type"] == "window_focus"
    assert res_focus.json()["question_id"] == "q_2"
