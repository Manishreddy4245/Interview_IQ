from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient


def create_test_session(client: TestClient) -> str:
    """Helper to create a session in memory for evaluation tests with valid 3-question count."""
    valid_ai_json = """{
      "questions": [
        {
          "id": "q_1",
          "question_number": 1,
          "text": "How do you optimize React component rendering performance?",
          "assessed_skill": "React Optimization",
          "difficulty": "Medium",
          "rubric": "Evaluates memoization, virtual DOM awareness, and render profiling."
        },
        {
          "id": "q_2",
          "question_number": 2,
          "text": "Explain the difference between useEffect and useLayoutEffect.",
          "assessed_skill": "React Lifecycle",
          "difficulty": "Medium",
          "rubric": "Evaluates paint lifecycle and DOM mutation timing."
        },
        {
          "id": "q_3",
          "question_number": 3,
          "text": "How do you manage complex asynchronous state in a frontend app?",
          "assessed_skill": "State Management",
          "difficulty": "Hard",
          "rubric": "Evaluates caching, invalidation, race conditions, and error boundaries."
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
                "role": "Frontend Engineer",
                "focus_areas": "React Performance",
                "question_count": 3,
            },
        )
        assert res.status_code == 201
        return res.json()["session_id"]


def test_evaluate_missing_groq_credentials(client: TestClient):
    """Test that evaluation endpoint returns 503 when GROQ_API_KEY is not set."""
    session_id = create_test_session(client)

    # First submit an answer
    client.post(
        f"/api/interviews/{session_id}/answers",
        json={"question_id": "q_1", "answer_text": "I use useMemo and React.memo."},
    )

    with patch("app.core.config.settings.GROQ_API_KEY", None):
        response = client.post(
            f"/api/interviews/{session_id}/questions/q_1/evaluate",
            json={},
        )
        assert response.status_code == 503
        assert "Groq API key is not configured" in response.json()["detail"]


def test_evaluate_missing_answer(client: TestClient):
    """Test rejection when attempting to evaluate a question that has no answer."""
    session_id = create_test_session(client)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"):
        response = client.post(
            f"/api/interviews/{session_id}/questions/q_1/evaluate",
            json={},
        )
        assert response.status_code == 400
        assert "No answer has been submitted" in response.json()["detail"]


def test_evaluate_invalid_question_id(client: TestClient):
    """Test rejection when question_id does not belong to session."""
    session_id = create_test_session(client)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"):
        response = client.post(
            f"/api/interviews/{session_id}/questions/q_999/evaluate",
            json={"answer_text": "Some text"},
        )
        assert response.status_code == 400
        assert "not found in session" in response.json()["detail"]


def test_evaluate_malformed_model_output(client: TestClient):
    """Test 502 handling when model returns non-JSON content."""
    session_id = create_test_session(client)

    mock_choice = MagicMock()
    mock_choice.message.content = "Not a json object"
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        response = client.post(
            f"/api/interviews/{session_id}/questions/q_1/evaluate",
            json={"answer_text": "I use useMemo and React.memo to prevent unnecessary re-renders."},
        )
        assert response.status_code == 502
        assert "invalid JSON" in response.json()["detail"]


def test_evaluate_score_boundary_validation(client: TestClient):
    """Test 502 rejection when model returns score exceeding 100."""
    session_id = create_test_session(client)

    # overall_score 150 violates ge=1, le=100
    invalid_eval_json = """{
      "overall_score": 150,
      "criterion_scores": {
        "relevance": {"score": 8, "feedback": "Good answer."},
        "technical_depth": {"score": 8, "feedback": "Good answer."},
        "completeness": {"score": 8, "feedback": "Good answer."},
        "structure_flow": {"score": 8, "feedback": "Good answer."},
        "clarity_conciseness": {"score": 8, "feedback": "Good answer."}
      },
      "strengths": ["Clear answer."],
      "areas_for_improvement": ["Could add details."],
      "actionable_suggestions": ["Mention Profiler."],
      "coaching_summary": "Solid foundation with concise phrasing."
    }"""

    mock_choice = MagicMock()
    mock_choice.message.content = invalid_eval_json
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        response = client.post(
            f"/api/interviews/{session_id}/questions/q_1/evaluate",
            json={"answer_text": "I use useMemo and React.memo to prevent unnecessary re-renders."},
        )
        assert response.status_code == 502
        assert "did not match the expected schema" in response.json()["detail"]


def test_evaluate_success_and_db_unconfigured(client: TestClient):
    """
    Test successful evaluation workflow:
    - Returns valid scores, strengths, improvement areas, and communication coaching.
    - Accurately reports saved_to_db: False when MongoDB Atlas is unconfigured.
    """
    session_id = create_test_session(client)

    valid_eval_json = """{
      "overall_score": 85,
      "criterion_scores": {
        "relevance": {"score": 9, "feedback": "Directly explains React component render optimization."},
        "technical_depth": {"score": 8, "feedback": "Accurately references useMemo and virtualization techniques."},
        "completeness": {"score": 8, "feedback": "Covers both state architecture and rendering tools."},
        "structure_flow": {"score": 9, "feedback": "Logical sequence from identification to profiling to optimization."},
        "clarity_conciseness": {"score": 8, "feedback": "Concise phrasing without conversational filler."}
      },
      "strengths": [
        "Accurately cited React.memo for pure functional components.",
        "Demonstrated understanding of virtual DOM reconciliation bottlenecks."
      ],
      "areas_for_improvement": [
        "Did not discuss React DevTools Profiler to verify real render savings."
      ],
      "actionable_suggestions": [
        "Quantify render improvements with flamegraph profiling evidence."
      ],
      "coaching_summary": "Strong technical clarity. Strengthen answers by referencing measurement tools before applying optimizations."
    }"""

    mock_choice = MagicMock()
    mock_choice.message.content = valid_eval_json
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        response = client.post(
            f"/api/interviews/{session_id}/questions/q_1/evaluate",
            json={"answer_text": "I optimize renders by identifying unnecessary re-renders with React Profiler, applying React.memo to leaf components, and virtualizing large lists with tanstack-virtual."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["question_id"] == "q_1"
        assert data["overall_score"] == 85
        assert data["criterion_scores"]["relevance"]["score"] == 9
        assert len(data["strengths"]) == 2
        assert len(data["areas_for_improvement"]) == 1
        assert len(data["actionable_suggestions"]) == 1
        assert "Strong technical clarity" in data["coaching_summary"]
        assert data["saved_to_db"] is False
        assert data["db_status"] == "unconfigured"
        assert "MongoDB Atlas is not configured" in data["db_message"]

        # Verify evaluation was stored in the active session
        get_res = client.get(f"/api/interviews/{session_id}")
        assert get_res.status_code == 200
        session_doc = get_res.json()
        assert "evaluation" in session_doc["answers"]["q_1"]
        assert session_doc["answers"]["q_1"]["evaluation"]["overall_score"] == 85
