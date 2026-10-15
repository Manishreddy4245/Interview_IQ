from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


def test_setup_invalid_inputs(client: TestClient):
    """Test validation rejection for invalid setup parameters."""
    # 1. Missing / too short role
    response = client.post(
        "/api/interviews/setup",
        json={"role": "A", "focus_areas": "Python"},
    )
    assert response.status_code == 422

    # 2. Empty whitespace role
    response = client.post(
        "/api/interviews/setup",
        json={"role": "   ", "focus_areas": "Python"},
    )
    assert response.status_code == 422

    # 3. Invalid question count (< 3)
    response = client.post(
        "/api/interviews/setup",
        json={
            "role": "Frontend Engineer",
            "focus_areas": "React",
            "question_count": 2,
        },
    )
    assert response.status_code == 422

    # 4. Invalid question count (> 5)
    response = client.post(
        "/api/interviews/setup",
        json={
            "role": "Frontend Engineer",
            "focus_areas": "React",
            "question_count": 6,
        },
    )
    assert response.status_code == 422


def test_setup_missing_groq_credentials(client: TestClient):
    """
    Test that setup endpoint clearly returns 503 when GROQ_API_KEY is not configured,
    without returning fake or fallback questions.
    """
    with patch("app.core.config.settings.GROQ_API_KEY", None):
        response = client.post(
            "/api/interviews/setup",
            json={
                "role": "Backend Engineer",
                "experience_level": "Mid-Level",
                "difficulty": "Medium",
                "focus_areas": "FastAPI, PostgreSQL",
                "question_count": 3,
            },
        )
        assert response.status_code == 503
        data = response.json()
        assert "Groq API key is not configured" in data["detail"]


def test_setup_malformed_ai_output(client: TestClient):
    """Test that malformed JSON from the AI service is rejected with 502."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Not a valid json response"
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        response = client.post(
            "/api/interviews/setup",
            json={
                "role": "Backend Engineer",
                "focus_areas": "Python, Algorithms",
                "question_count": 3,
            },
        )
        assert response.status_code == 502
        assert "could not be parsed" in response.json()["detail"]


def test_setup_schema_mismatch_ai_output(client: TestClient):
    """Test that valid JSON that fails question schema is rejected with 502."""
    mock_choice = MagicMock()
    # Missing required 'rubric' and 'difficulty' fields
    mock_choice.message.content = '{"questions": [{"id": "q_1", "question_number": 1, "text": "Too short"}]}'
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        response = client.post(
            "/api/interviews/setup",
            json={
                "role": "Backend Engineer",
                "focus_areas": "Python, Algorithms",
                "question_count": 3,
            },
        )
        assert response.status_code == 502
        assert "schema" in response.json()["detail"]


def test_setup_success_and_answer_workflow(client: TestClient):
    """
    Test successful question generation (with mocked Groq client) and subsequent
    answer submission when MongoDB is unconfigured.
    Verifies that saved_to_db accurately reflects unconfigured state without pretending.
    """
    valid_ai_json = """{
      "questions": [
        {
          "id": "q_1",
          "question_number": 1,
          "text": "Explain how you handle race conditions in distributed systems.",
          "assessed_skill": "Distributed Systems",
          "difficulty": "Hard",
          "rubric": "Look for mentions of distributed locks, idempotency keys, and optimistic locking."
        },
        {
          "id": "q_2",
          "question_number": 2,
          "text": "How do you design RESTful APIs for backward compatibility?",
          "assessed_skill": "API Design",
          "difficulty": "Medium",
          "rubric": "Candidate discusses versioning strategies and non-breaking contract changes."
        },
        {
          "id": "q_3",
          "question_number": 3,
          "text": "Describe a challenging bug you debugged in production.",
          "assessed_skill": "Troubleshooting",
          "difficulty": "Medium",
          "rubric": "Evaluates structured debugging methodology and post-incident RCA."
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
        # 1. Create session
        setup_res = client.post(
            "/api/interviews/setup",
            json={
                "role": "Staff Engineer",
                "experience_level": "Senior",
                "difficulty": "Hard",
                "focus_areas": "Distributed Systems, Architecture",
                "question_count": 3,
            },
        )
        assert setup_res.status_code == 201
        session_data = setup_res.json()
        assert session_data["role"] == "Staff Engineer"
        assert len(session_data["questions"]) == 3
        assert session_data["saved_to_db"] is False
        assert session_data["db_status"] == "unconfigured"
        session_id = session_data["session_id"]

        # 2. Submit answer to question 1
        answer_res = client.post(
            f"/api/interviews/{session_id}/answers",
            json={
                "question_id": "q_1",
                "answer_text": "I implement idempotency keys with Redis distributed locks with TTL.",
            },
        )
        assert answer_res.status_code == 200
        answer_data = answer_res.json()
        assert answer_data["question_id"] == "q_1"
        assert answer_data["saved_to_db"] is False
        assert answer_data["db_status"] == "unconfigured"

        # 3. Reject answer for non-existent question in session
        invalid_q_res = client.post(
            f"/api/interviews/{session_id}/answers",
            json={
                "question_id": "q_999",
                "answer_text": "Invalid question answer",
            },
        )
        assert invalid_q_res.status_code == 400

        # 4. Reject answer for non-existent session
        missing_session_res = client.post(
            "/api/interviews/00000000-0000-0000-0000-000000000000/answers",
            json={
                "question_id": "q_1",
                "answer_text": "Some answer",
            },
        )
        assert missing_session_res.status_code == 404

        # 5. Retrieve session and verify answer stored in active memory
        get_res = client.get(f"/api/interviews/{session_id}")
        assert get_res.status_code == 200
        retrieved = get_res.json()
        assert "q_1" in retrieved["answers"]
        assert retrieved["answers"]["q_1"]["answer_text"] == "I implement idempotency keys with Redis distributed locks with TTL."
