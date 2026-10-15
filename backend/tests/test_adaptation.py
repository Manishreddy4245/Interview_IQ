import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

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
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    get_session,
    _in_memory_sessions,
)
from app.services.adaptation_service import (
    determine_adaptive_difficulty,
    compute_session_competency_state,
    select_target_competency,
)


@pytest.fixture
def initial_question():
    return QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain how you handle concurrency in FastAPI with async/await.",
        assessed_skill="Concurrency",
        difficulty="Medium",
        rubric="Demonstrates understanding of event loop and non-blocking I/O.",
        selection_rationale="Initial baseline question assessing concurrency.",
    )


@pytest.fixture
def sample_eval_high():
    return AIEvaluationRaw(
        overall_score=85,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Very relevant"),
            technical_depth=CriterionScore(score=9, feedback="Deep async knowledge"),
            completeness=CriterionScore(score=8, feedback="Complete"),
            structure_flow=CriterionScore(score=8, feedback="Clear"),
            clarity_conciseness=CriterionScore(score=9, feedback="Concise"),
        ),
        strengths=["Strong knowledge of Python asyncio"],
        areas_for_improvement=["Could mention uvloop optimizations"],
        actionable_suggestions=["Reference ASGI event loops"],
        coaching_summary="Well articulated response",
    )


@pytest.fixture
def sample_eval_low():
    return AIEvaluationRaw(
        overall_score=40,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=4, feedback="Vague"),
            technical_depth=CriterionScore(score=4, feedback="Superficial"),
            completeness=CriterionScore(score=4, feedback="Incomplete"),
            structure_flow=CriterionScore(score=5, feedback="Disorganized"),
            clarity_conciseness=CriterionScore(score=5, feedback="Wordy"),
        ),
        strengths=["Acknowledged the concept"],
        areas_for_improvement=["Needs more technical depth"],
        actionable_suggestions=["Study event loop lifecycle"],
        coaching_summary="Needs improvement",
    )


@pytest.mark.asyncio
async def test_difficulty_adaptation_rules(initial_question, sample_eval_high, sample_eval_low):
    """Verify deterministic difficulty escalation, de-escalation, and maintenance."""
    setup = InterviewSetupRequest(
        role="Senior Backend Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Concurrency, System Design, FastAPI",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=3,
    )
    session = await get_session(session_res.session_id)

    # 1. Without evaluations, difficulty remains initial difficulty
    assert determine_adaptive_difficulty(session) == "Medium"

    # 2. Score >= 75 escalates difficulty: Medium -> Hard
    await save_evaluation(session_res.session_id, "q_1", sample_eval_high)
    session = await get_session(session_res.session_id)
    assert determine_adaptive_difficulty(session) == "Hard"

    # 3. High score at Hard caps at Hard
    session["questions"][0]["difficulty"] = "Hard"
    assert determine_adaptive_difficulty(session) == "Hard"

    # 4. Score < 50 de-escalates difficulty: Hard -> Medium -> Easy
    await save_evaluation(session_res.session_id, "q_1", sample_eval_low)
    session = await get_session(session_res.session_id)
    session["questions"][0]["difficulty"] = "Hard"
    assert determine_adaptive_difficulty(session) == "Medium"

    session["questions"][0]["difficulty"] = "Medium"
    assert determine_adaptive_difficulty(session) == "Easy"

    # Low score at Easy floors at Easy
    session["questions"][0]["difficulty"] = "Easy"
    assert determine_adaptive_difficulty(session) == "Easy"

    # 5. Score in mid-range (50-74) maintains current difficulty
    sample_eval_mid = sample_eval_high.model_copy(update={"overall_score": 62})
    await save_evaluation(session_res.session_id, "q_1", sample_eval_mid)
    session["questions"][0]["difficulty"] = "Medium"
    assert determine_adaptive_difficulty(session) == "Medium"


@pytest.mark.asyncio
async def test_competency_state_updates_after_evaluated_answer(initial_question, sample_eval_high, sample_eval_low):
    """Verify per-session competency state tracking and status transitions."""
    setup = InterviewSetupRequest(
        role="Senior Backend Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Concurrency, System Design, FastAPI",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=3,
    )
    session = await get_session(session_res.session_id)
    state = compute_session_competency_state(session)

    # Before evaluation, Concurrency is tracked as needs_further_assessment (pending evaluated evidence)
    assert "Concurrency" in state.skills
    assert state.skills["Concurrency"].status == CompetencyStatus.NEEDS_FURTHER_ASSESSMENT
    assert "System Design" in state.skills
    assert state.skills["System Design"].status == CompetencyStatus.NOT_ASSESSED

    # Submit answer and save high evaluation (score >= 70) -> demonstrated
    await submit_answer(session_res.session_id, SubmitAnswerRequest(
        question_id="q_1",
        answer_text="We use asyncio.gather and avoid blocking CPU tasks.",
    ))
    await save_evaluation(session_res.session_id, "q_1", sample_eval_high)

    session = await get_session(session_res.session_id)
    state_after = compute_session_competency_state(session)
    assert state_after.skills["Concurrency"].status == CompetencyStatus.DEMONSTRATED
    assert state_after.skills["Concurrency"].questions_evaluated == 1
    assert state_after.skills["Concurrency"].latest_score == 85

    # If score < 70 -> needs_further_assessment
    await save_evaluation(session_res.session_id, "q_1", sample_eval_low)
    session = await get_session(session_res.session_id)
    state_low = compute_session_competency_state(session)
    assert state_low.skills["Concurrency"].status == CompetencyStatus.NEEDS_FURTHER_ASSESSMENT


@pytest.mark.asyncio
async def test_target_competency_selection_avoids_back_to_back(initial_question):
    """Verify selecting next target competency prioritizes unassessed competencies and avoids duplicate skills."""
    setup = InterviewSetupRequest(
        role="Senior Backend Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Concurrency, System Design, FastAPI",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=3,
    )
    session = await get_session(session_res.session_id)
    comp_state = compute_session_competency_state(session)

    # Question 1 was Concurrency, so next competency should pick System Design or FastAPI
    target = select_target_competency(session, comp_state)
    assert target.lower() != "concurrency"
    assert target.lower() in ["system design", "fastapi"]


@pytest.mark.asyncio
async def test_next_question_selected_using_prior_evidence(client: TestClient, initial_question, sample_eval_high):
    """Verify next question generation endpoint integrates prior answers, evaluations, and rationale."""
    setup = InterviewSetupRequest(
        role="Senior Backend Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Concurrency, System Design, FastAPI",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=3,
    )
    await submit_answer(session_res.session_id, SubmitAnswerRequest(
        question_id="q_1",
        answer_text="I use async def routes with Tortoise ORM.",
    ))
    await save_evaluation(session_res.session_id, "q_1", sample_eval_high)

    mock_generated_json = {
        "id": "q_2",
        "question_number": 2,
        "text": "How would you architect distributed rate limiting across multiple FastAPI workers?",
        "assessed_skill": "System Design",
        "difficulty": "Hard",
        "rubric": "Looks for Redis token bucket or sliding window implementation with latency awareness.",
        "selection_rationale": "High score on Concurrency justified stepping up to Hard System Design.",
    }

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(mock_generated_json)
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        response = client.post(f"/api/interviews/{session_res.session_id}/next-question")
        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == session_res.session_id
        assert data["question"]["id"] == "q_2"
        assert data["question"]["question_number"] == 2
        assert data["question"]["assessed_skill"] == "System Design"
        assert data["question"]["difficulty"] == "Hard"
        assert data["question"]["selection_rationale"] is not None
        assert "stepping up to Hard" in data["question"]["selection_rationale"]
        assert data["target_question_count"] == 3
        assert data["is_last_question"] is False

        # Session in storage should now have 2 questions persisted
        updated_session = await get_session(session_res.session_id)
        assert len(updated_session["questions"]) == 2
        assert updated_session["questions"][1]["id"] == "q_2"


@pytest.mark.asyncio
async def test_no_duplicate_questions_or_answers(client: TestClient, initial_question):
    """Verify that calling next question appends cleanly and does not duplicate questions or answers."""
    setup = InterviewSetupRequest(
        role="Senior Backend Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Concurrency, FastAPI",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=3,
    )

    mock_generated_json = {
        "id": "q_2",
        "question_number": 2,
        "text": "Explain connection pooling in PostgreSQL.",
        "assessed_skill": "FastAPI",
        "difficulty": "Medium",
        "rubric": "Evaluates understanding of max connections, queueing, and pgBouncer.",
        "selection_rationale": "Assessing database integration.",
    }

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(mock_generated_json)
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        res1 = client.post(f"/api/interviews/{session_res.session_id}/next-question")
        assert res1.status_code == 200

        # Submitting answer for q_1 updates in-place rather than creating duplicate entries
        client.post(
            f"/api/interviews/{session_res.session_id}/answers",
            json={"question_id": "q_1", "answer_text": "Answer version 1"},
        )
        res_sub2 = client.post(
            f"/api/interviews/{session_res.session_id}/answers",
            json={"question_id": "q_1", "answer_text": "Answer version 2 updated"},
        )
        assert res_sub2.status_code == 200

        updated_session = await get_session(session_res.session_id)
        assert len(updated_session["answers"]) == 1
        assert updated_session["answers"]["q_1"]["answer_text"] == "Answer version 2 updated"


@pytest.mark.asyncio
async def test_invalid_session_and_completed_session_handling(client: TestClient, initial_question):
    """Verify 404 for invalid session ID and 400 when session is completed or reached question target."""
    # 1. Invalid session ID
    response = client.post("/api/interviews/non-existent-session-id/next-question")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    # 2. Session already reached target question count
    setup = InterviewSetupRequest(
        role="Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=1,
    )
    response_target = client.post(f"/api/interviews/{session_res.session_id}/next-question")
    assert response_target.status_code == 400
    assert "reached its target question count" in response_target.json()["detail"]

    # 3. Session status is 'completed'
    _in_memory_sessions[session_res.session_id]["status"] = "completed"
    _in_memory_sessions[session_res.session_id]["target_question_count"] = 5
    response_completed = client.post(f"/api/interviews/{session_res.session_id}/next-question")
    assert response_completed.status_code == 400
    assert "completed" in response_completed.json()["detail"].lower()


@pytest.mark.asyncio
async def test_groq_failures_safe_actionable_errors_no_fallback(client: TestClient, initial_question):
    """Verify Groq failure produces clean HTTP errors without fabricating fallback questions."""
    setup = InterviewSetupRequest(
        role="Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=3,
    )

    # 1. Missing GROQ_API_KEY -> 503
    with patch("app.core.config.settings.GROQ_API_KEY", None):
        res = client.post(f"/api/interviews/{session_res.session_id}/next-question")
        assert res.status_code == 503
        assert "Groq API key is not configured" in res.json()["detail"]

    # 2. Malformed AI output -> 502
    mock_choice = MagicMock()
    mock_choice.message.content = "Not a json response"
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        res_malformed = client.post(f"/api/interviews/{session_res.session_id}/next-question")
        assert res_malformed.status_code == 502
        assert "invalid JSON" in res_malformed.json()["detail"]

    # Verify no fallback question was silently inserted
    updated = await get_session(session_res.session_id)
    assert len(updated["questions"]) == 1


@pytest.mark.asyncio
async def test_competencies_endpoint(client: TestClient, initial_question):
    """Verify GET /api/interviews/{session_id}/competencies returns correct state."""
    setup = InterviewSetupRequest(
        role="Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Concurrency, FastAPI",
        question_count=3,
        adaptive=True,
    )
    session_res = await create_interview_session(
        setup,
        [initial_question],
        is_adaptive=True,
        target_question_count=3,
    )
    res = client.get(f"/api/interviews/{session_res.session_id}/competencies")
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session_res.session_id
    assert "skills" in data
    assert data["current_difficulty"] == "Medium"


@pytest.mark.asyncio
async def test_existing_sessions_and_reports_compatibility(client: TestClient, sample_eval_high):
    """Verify legacy non-adaptive sessions remain fully compatible with report generation."""
    setup = InterviewSetupRequest(
        role="Product Designer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Design Systems, Prototyping",
        question_count=3,
        adaptive=False,
    )
    questions = [
        QuestionItem(
            id="q_1",
            question_number=1,
            text="Describe your design tokens architecture.",
            assessed_skill="Design Systems",
            difficulty="Medium",
            rubric="Evaluates naming conventions and hierarchy.",
        ),
        QuestionItem(
            id="q_2",
            question_number=2,
            text="How do you test interactive prototypes?",
            assessed_skill="Prototyping",
            difficulty="Medium",
            rubric="Evaluates usability testing protocols.",
        ),
    ]
    session_res = await create_interview_session(
        setup,
        questions,
        is_adaptive=False,
        target_question_count=2,
    )
    await submit_answer(session_res.session_id, SubmitAnswerRequest(
        question_id="q_1",
        answer_text="We use semantic token tiers mapped to primitive colors.",
    ))
    await save_evaluation(session_res.session_id, "q_1", sample_eval_high)

    # Generate final report
    res_report = client.post(f"/api/interviews/{session_res.session_id}/report")
    assert res_report.status_code == 200
    report_data = res_report.json()
    assert report_data["session_id"] == session_res.session_id
    assert report_data["evaluated_questions"] == 1
    assert report_data["overall_score"] == 85.0
    assert report_data["score_status"] == "calculated"
    assert report_data["total_questions"] == 2
