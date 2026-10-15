import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    SubmitAnswerRequest,
    NextQuestionRequest,
    CompetencyStatus,
    SessionCompetencyState,
    CompetencySkillState,
)
from app.schemas.evaluation import (
    CriterionScores,
    CriterionScore,
    AIEvaluationRaw,
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    get_session,
    compute_session_time_status,
    _in_memory_sessions,
)
from app.services.adaptation_service import (
    generate_next_adaptive_question,
    compute_session_competency_state,
    determine_adaptive_difficulty,
    select_target_competency,
    is_duplicate_question,
    generate_time_aware_fallback_question,
)
from app.main import app


@pytest.fixture
def base_question():
    return QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain how you design scalable REST APIs using FastAPI and async handlers.",
        assessed_skill="FastAPI",
        difficulty="Medium",
        rubric="Demonstrates understanding of async route handlers, dependency injection, and Pydantic validation.",
        selection_rationale="Initial baseline question assessing FastAPI.",
        time_band="comprehensive",
    )


# --------------------------------------------------------------------------
# 1. Authoritative Timing & Boundary Value Tests
# --------------------------------------------------------------------------

def test_timing_calculation_and_client_hint_clamping():
    """Verify authoritative server timing calculation and client hint validation."""
    now = datetime.now(timezone.utc)
    # Session created 10 minutes ago with 30m total duration -> 20m (1200s) remaining
    session_doc = {
        "session_id": "test_time_1",
        "duration_minutes": 30,
        "created_at": (now - timedelta(minutes=10)).isoformat(),
    }

    # 1. Authoritative server time without client hint
    status = compute_session_time_status(session_doc)
    assert not status["is_expired"]
    assert 1190 <= status["server_remaining_seconds"] <= 1205
    assert status["time_band"] == "comprehensive"

    # 2. Client provides valid hint slightly below server remaining (e.g. 1195s)
    status_hint = compute_session_time_status(session_doc, client_hint_seconds=1195)
    assert status_hint["effective_remaining_seconds"] == 1195
    assert status_hint["time_band"] == "comprehensive"

    # 3. Client attempts to inflate time (claims 2500s when server says ~1200s) -> clamped to server authority
    status_spoof = compute_session_time_status(session_doc, client_hint_seconds=2500)
    assert status_spoof["effective_remaining_seconds"] == status["server_remaining_seconds"]
    assert status_spoof["effective_remaining_seconds"] <= 1205


def test_time_band_boundaries_10m_5m_0m():
    """Test exact boundary transitions between time bands: 601s, 600s, 300s, 299s, 1s, 0s."""
    now = datetime.now(timezone.utc)

    def make_session(remaining_seconds: int, duration_minutes: int = 30):
        total_seconds = duration_minutes * 60
        elapsed_seconds = total_seconds - remaining_seconds
        created_dt = now - timedelta(seconds=elapsed_seconds)
        return {
            "session_id": f"sess_bound_{remaining_seconds}",
            "duration_minutes": duration_minutes,
            "created_at": created_dt.isoformat(),
        }

    # Boundary > 10 min (> 600s): Comprehensive
    s_601 = compute_session_time_status(make_session(601))
    assert s_601["time_band"] == "comprehensive"
    assert not s_601["is_expired"]

    # Boundary == 10 min (600s): Focused
    s_600 = compute_session_time_status(make_session(600))
    assert s_600["time_band"] == "focused"
    assert not s_600["is_expired"]

    # Mid Focused (450s): Focused
    s_450 = compute_session_time_status(make_session(450))
    assert s_450["time_band"] == "focused"
    assert not s_450["is_expired"]

    # Boundary == 5 min (300s): Focused
    s_300 = compute_session_time_status(make_session(300))
    assert s_300["time_band"] == "focused"
    assert not s_300["is_expired"]

    # Boundary < 5 min (299s): Concise
    s_299 = compute_session_time_status(make_session(299))
    assert s_299["time_band"] == "concise"
    assert not s_299["is_expired"]

    # Last seconds (1s): Concise
    s_1 = compute_session_time_status(make_session(1))
    assert s_1["time_band"] == "concise"
    assert not s_1["is_expired"]

    # Zero seconds (0s): Expired
    s_0 = compute_session_time_status(make_session(0))
    assert s_0["time_band"] == "expired"
    assert s_0["is_expired"] is True
    assert s_0["effective_remaining_seconds"] == 0

    # Negative / past duration (e.g. elapsed 40 min in a 30m session): Expired
    s_past = compute_session_time_status(make_session(-120))
    assert s_past["time_band"] == "expired"
    assert s_past["is_expired"] is True
    assert s_past["effective_remaining_seconds"] == 0


def test_expired_session_anti_cheat():
    """Verify client cannot inflate or un-expire an expired session."""
    now = datetime.now(timezone.utc)
    expired_sess = {
        "session_id": "expired_cheat",
        "duration_minutes": 15,
        "created_at": (now - timedelta(minutes=20)).isoformat(),
    }
    # Client claims 900 seconds remaining
    status = compute_session_time_status(expired_sess, client_hint_seconds=900)
    assert status["is_expired"] is True
    assert status["effective_remaining_seconds"] == 0
    assert status["time_band"] == "expired"


# --------------------------------------------------------------------------
# 2. Time-Aware Question Generation Across Bands
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_question_generation_time_bands(base_question):
    """Verify question generation injects appropriate time band constraints and returns correct time metadata."""
    setup = InterviewSetupRequest(
        role="Full Stack Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="FastAPI, React, System Design",
        question_count=4,
        adaptive=True,
        duration_minutes=30,
        job_description="Build real-time microservices with FastAPI and React dashboard.",
    )
    session_res = await create_interview_session(setup, [base_question], is_adaptive=True)
    session_id = session_res.session_id

    # Band 1: Comprehensive (>10 min remaining, e.g. 1200s)
    mock_ai_comp = {
        "id": "q_2",
        "question_number": 2,
        "text": "Design an end-to-end event streaming architecture with FastAPI and WebSockets for real-time dashboards.",
        "assessed_skill": "System Design",
        "difficulty": "Medium",
        "rubric": "Evaluates architectural trade-offs, state persistence, and backpressure handling.",
        "selection_rationale": "Selected to evaluate System Design competency with comprehensive depth (>10 min remaining).",
        "time_band": "comprehensive",
    }
    with patch.object(settings, "GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=MagicMock()), \
         patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = json.dumps(mock_ai_comp)
        res_comp = await generate_next_adaptive_question(session_id, client_remaining_seconds=1200)

        assert res_comp.question.time_band == "comprehensive"
        assert res_comp.time_band == "comprehensive"
        assert res_comp.time_remaining_seconds == 1200
        assert "comprehensive" in res_comp.question.selection_rationale.lower() or "minute" in res_comp.question.selection_rationale.lower()

        # Verify job description was included in prompt sent to Groq
        user_prompt_sent = mock_groq.call_args[1]["messages"][1]["content"]
        assert "TARGET JOB DESCRIPTION CONTEXT" in user_prompt_sent
        assert "FastAPI and React dashboard" in user_prompt_sent

    # Band 2: Focused (5 to 10 min remaining, e.g. 450s)
    mock_ai_focused = {
        "id": "q_3",
        "question_number": 3,
        "text": "In React, how do you handle state synchronization edge cases when WebSockets reconnect after network drops?",
        "assessed_skill": "React",
        "difficulty": "Medium",
        "rubric": "Clear explanation of reconnection lifecycle, deduplication, and optimistic state recovery.",
        "selection_rationale": "Selected to evaluate React competency focused on edge cases for the 5-10 minute time window.",
        "time_band": "focused",
    }
    with patch.object(settings, "GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=MagicMock()), \
         patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = json.dumps(mock_ai_focused)
        res_focused = await generate_next_adaptive_question(session_id, client_remaining_seconds=450)

        assert res_focused.question.time_band == "focused"
        assert res_focused.time_band == "focused"
        assert res_focused.time_remaining_seconds == 450

    # Band 3: Concise (< 5 min remaining, e.g. 180s)
    mock_ai_concise = {
        "id": "q_4",
        "question_number": 4,
        "text": "In 2 minutes, what is the single most critical reason to choose useMemo vs useCallback in performance-critical rendering?",
        "assessed_skill": "React",
        "difficulty": "Medium",
        "rubric": "Succinct distinction between value caching and function reference stability.",
        "selection_rationale": "Selected to test React conceptual clarity in a concise single-focus format for under 5 minutes remaining.",
        "time_band": "concise",
    }
    with patch.object(settings, "GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=MagicMock()), \
         patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = json.dumps(mock_ai_concise)
        res_concise = await generate_next_adaptive_question(session_id, client_remaining_seconds=180)

        assert res_concise.question.time_band == "concise"
        assert res_concise.time_band == "concise"
        assert res_concise.time_remaining_seconds == 180
        assert res_concise.is_last_question is True


# --------------------------------------------------------------------------
# 3. Expired Session Protections (Next Question & Answer Submissions)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_session_rejects_question_generation(base_question):
    """Verify next question request is rejected with 400 Bad Request when session is expired."""
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="FastAPI, PostgreSQL",
        question_count=3,
        adaptive=True,
        duration_minutes=10,
    )
    session_res = await create_interview_session(setup, [base_question], is_adaptive=True)
    session_id = session_res.session_id

    # Simulate expired session by moving created_at back 15 minutes
    now = datetime.now(timezone.utc)
    _in_memory_sessions[session_id]["created_at"] = (now - timedelta(minutes=15)).isoformat()

    with patch.object(settings, "GROQ_API_KEY", "gsk_test_mock_key"):
        with pytest.raises(HTTPException) as exc_info:
            await generate_next_adaptive_question(session_id)
        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_expired_session_rejects_answer_submission(base_question):
    """Verify answer submission is rejected with 400 Bad Request when session is expired."""
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="FastAPI, PostgreSQL",
        question_count=3,
        adaptive=True,
        duration_minutes=15,
    )
    session_res = await create_interview_session(setup, [base_question], is_adaptive=True)
    session_id = session_res.session_id

    # Move created_at to 20 minutes ago
    now = datetime.now(timezone.utc)
    _in_memory_sessions[session_id]["created_at"] = (now - timedelta(minutes=20)).isoformat()

    with pytest.raises(HTTPException) as exc_info:
        await submit_answer(
            session_id,
            SubmitAnswerRequest(question_id="q_1", answer_text="My delayed answer"),
        )
    assert exc_info.value.status_code == 400
    assert "expired" in exc_info.value.detail.lower()


def test_api_endpoints_reject_expired_session(base_question):
    """Test HTTP API endpoints for /next-question and /answers reject expired sessions."""
    client = TestClient(app)

    # 1. Setup session via API
    setup_payload = {
        "role": "QA Engineer",
        "experience_level": "Mid-Level",
        "difficulty": "Medium",
        "focus_areas": "Pytest, Selenium",
        "question_count": 3,
        "adaptive": True,
        "duration_minutes": 10,
    }
    with patch.object(settings, "GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=MagicMock()), \
         patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = json.dumps({
            "id": "q_1",
            "question_number": 1,
            "text": "How do you structure fixtures in Pytest?",
            "assessed_skill": "Pytest",
            "difficulty": "Medium",
            "rubric": "Clear scope and yield explanation",
            "selection_rationale": "Baseline question",
            "time_band": "comprehensive",
        })
        resp = client.post("/api/interviews/setup", json=setup_payload)
        assert resp.status_code == 201
        session_id = resp.json()["session_id"]

    # Age the session to expired
    now = datetime.now(timezone.utc)
    _in_memory_sessions[session_id]["created_at"] = (now - timedelta(minutes=15)).isoformat()

    # Next question attempt on expired session
    resp_next = client.post(
        f"/api/interviews/{session_id}/next-question",
        json={"client_remaining_seconds": 0},
    )
    assert resp_next.status_code == 400
    assert "expired" in resp_next.json()["detail"].lower()

    # Answer submission attempt on expired session
    resp_ans = client.post(
        f"/api/interviews/{session_id}/answers",
        json={"question_id": "q_1", "answer_text": "Late answer text"},
    )
    assert resp_ans.status_code == 400
    assert "expired" in resp_ans.json()["detail"].lower()


# --------------------------------------------------------------------------
# 4. Duplicate Question Prevention & Deduplication
# --------------------------------------------------------------------------

def test_duplicate_question_detection():
    """Verify duplicate detection correctly flags exact, normalized, and high-overlap question texts."""
    existing_q = [
        {"id": "q_1", "text": "Explain how you design scalable REST APIs using FastAPI and async handlers."},
    ]

    # Exact match
    assert is_duplicate_question(
        "Explain how you design scalable REST APIs using FastAPI and async handlers.",
        existing_q,
    ) is True

    # Case & whitespace variation
    assert is_duplicate_question(
        "  explain HOW you design Scalable rest apis using fastapi and async handlers.  ",
        existing_q,
    ) is True

    # High token overlap
    assert is_duplicate_question(
        "Explain how you design scalable REST APIs using FastAPI with async route handlers.",
        existing_q,
    ) is True

    # Completely different question
    assert is_duplicate_question(
        "How do you implement optimistic locking in PostgreSQL using SQLAlchemy?",
        existing_q,
    ) is False


@pytest.mark.asyncio
async def test_duplicate_question_prevention_uses_fallback(base_question):
    """When AI returns a duplicate question text, system intercepts and yields a distinct time-aware fallback."""
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="FastAPI, PostgreSQL",
        question_count=3,
        adaptive=True,
        duration_minutes=30,
    )
    session_res = await create_interview_session(setup, [base_question], is_adaptive=True)
    session_id = session_res.session_id

    # Mock Groq returning the exact same question text as Q1
    duplicate_ai_response = {
        "id": "q_2",
        "question_number": 2,
        "text": base_question.text,  # Exact duplicate of Q1!
        "assessed_skill": "PostgreSQL",
        "difficulty": "Medium",
        "rubric": "Sample rubric indicators for postgresql",
        "selection_rationale": "Sample rationale for postgresql",
        "time_band": "comprehensive",
    }

    with patch.object(settings, "GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=MagicMock()), \
         patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = json.dumps(duplicate_ai_response)
        res = await generate_next_adaptive_question(session_id, client_remaining_seconds=1500)

        # The returned question must NOT be the duplicate text
        assert res.question.text != base_question.text
        assert res.question.id == "q_2"
        assert res.question.question_number == 2
        assert res.question.assessed_skill == "PostgreSQL"
        assert res.question.time_band == "comprehensive"


# --------------------------------------------------------------------------
# 5. Competency Prioritization
# --------------------------------------------------------------------------

def test_select_target_competency_prioritizes_unassessed():
    """Verify target competency selection prioritizes unassessed competencies and rotates away from immediately preceding skill."""
    session = {
        "focus_areas": "Python, Docker, Kubernetes, AWS",
        "questions": [
            {"id": "q_1", "assessed_skill": "Python"},
        ],
        "answers": {},
    }
    state = compute_session_competency_state(session)
    # Python has been touched in Q1; Docker is unassessed and not equal to Python
    selected = select_target_competency(session, state)
    assert selected == "Docker"

    # Now simulate Python and Docker having been assessed; Kubernetes next
    session["questions"].append({"id": "q_2", "assessed_skill": "Docker"})
    state2 = compute_session_competency_state(session)
    selected2 = select_target_competency(session, state2)
    assert selected2 == "Kubernetes"


# --------------------------------------------------------------------------
# 6. Fallback Question Generator Behaviour
# --------------------------------------------------------------------------

def test_time_aware_fallback_generator():
    """Verify fallback generator returns valid QuestionItems for all time bands without crashing."""
    existing = [{"id": "q_1", "text": "Existing question text"}]

    # Concise fallback
    q_concise = generate_time_aware_fallback_question(
        skill="Redis",
        difficulty="Hard",
        time_band="concise",
        next_q_id="q_2",
        next_q_number=2,
        existing_questions=existing,
        role="Senior Backend Engineer",
    )
    assert q_concise.id == "q_2"
    assert q_concise.question_number == 2
    assert q_concise.assessed_skill == "Redis"
    assert q_concise.difficulty == "Hard"
    assert q_concise.time_band == "concise"
    assert "concise" in q_concise.selection_rationale.lower() or "minute" in q_concise.selection_rationale.lower()
    assert len(q_concise.rubric) > 10

    # Focused fallback
    q_focused = generate_time_aware_fallback_question(
        skill="Kafka",
        difficulty="Medium",
        time_band="focused",
        next_q_id="q_3",
        next_q_number=3,
        existing_questions=existing,
        role="Data Engineer",
    )
    assert q_focused.assessed_skill == "Kafka"
    assert q_focused.difficulty == "Medium"
    assert q_focused.time_band == "focused"
    assert "focused" in q_focused.selection_rationale.lower() or "minute" in q_focused.selection_rationale.lower()

    # Comprehensive fallback
    q_comp = generate_time_aware_fallback_question(
        skill="System Architecture",
        difficulty="Easy",
        time_band="comprehensive",
        next_q_id="q_4",
        next_q_number=4,
        existing_questions=existing,
        role="Software Engineer",
    )
    assert q_comp.assessed_skill == "System Architecture"
    assert q_comp.time_band == "comprehensive"
    assert "comprehensive" in q_comp.selection_rationale.lower() or "minute" in q_comp.selection_rationale.lower()
