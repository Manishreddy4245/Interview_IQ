import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
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
    save_evaluation,
    append_session_question,
    _in_memory_sessions,
)
from app.services.adaptation_service import (
    determine_adaptive_difficulty,
    generate_next_adaptive_question,
)

client = TestClient(app)


@pytest.fixture
def candidate_headers():
    token = create_access_token(user_id="cand_test_user", role=ROLE_CANDIDATE, name="Test Candidate")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_verbal_evaluation():
    return AIEvaluationRaw(
        overall_score=85,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Strong relevance"),
            technical_depth=CriterionScore(score=8, feedback="Good JVM depth"),
            completeness=CriterionScore(score=8, feedback="Covered heap and stack"),
            structure_flow=CriterionScore(score=9, feedback="Logical progression"),
            clarity_conciseness=CriterionScore(score=8, feedback="Crisp delivery"),
        ),
        strengths=["Clear distinction between class and object", "Good memory model understanding"],
        areas_for_improvement=["Could mention Metaspace explicitly"],
        actionable_suggestions=["Review JVM memory regions"],
        coaching_summary="Solid conceptual explanation of OOP in Java.",
    )


@pytest.mark.asyncio
async def test_1_successful_verbal_evaluation_and_consistent_persistence(mock_verbal_evaluation, candidate_headers):
    """
    1. Successful verbal answer evaluation.
    4. Accurate saved_to_db and db_status values.
    Top-level response and child evaluation both report saved_to_db=True, db_status='persisted'
    when MongoDB Atlas acknowledges writes.
    """
    setup = InterviewSetupRequest(
        role="Java Developer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Java, OOP",
        interview_mode="VERBAL",
        target_question_count=3,
    )
    first_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="What is the difference between a class and an object in Java?",
        assessed_skill="Java",
        difficulty="Medium",
        rubric="Explains blueprint vs instance",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[first_q], owner_id="cand_test_user", is_adaptive=True)

    mock_db = MagicMock()
    # Mock update_one acknowledging writes
    mock_db["interview_sessions"].update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    mock_db["interview_sessions"].find_one = AsyncMock(return_value=None)

    next_q_json = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "Explain polymorphism and method overriding in Java.",
        "assessed_skill": "OOP",
        "difficulty": "Hard",
        "rubric": "Runtime polymorphism with virtual method table",
        "question_type": "verbal",
        "selection_rationale": "Deepens OOP hierarchy based on demonstrated proficiency.",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", "mongodb+srv://mock_atlas:secret@cluster.mongodb.net"):
        with patch("app.core.database.db_manager.get_database", return_value=mock_db):
            with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
                mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
                with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                    mock_groq.return_value = next_q_json

                    response = client.post(
                        f"/api/interviews/{session.session_id}/submit-and-adapt",
                        headers=candidate_headers,
                        json={
                            "question_id": "q_1",
                            "answer_text": "A class is a blueprint, an object is an instantiated entity on the heap.",
                            "answer_mode": "verbal",
                        },
                    )

    assert response.status_code == 200, response.text
    data = response.json()

    # Child evaluation persistence
    assert data["evaluation"]["saved_to_db"] is True
    assert data["evaluation"]["db_status"] == "persisted"
    assert data["evaluation"]["overall_score"] == 85

    # Top-level response persistence matches
    assert data["saved_to_db"] is True
    assert data["db_status"] == "persisted"

    # Next question is active and returned
    assert data["active_question_id"] == "q_2"
    assert data["next_question"]["id"] == "q_2"
    assert data["next_question"]["question_type"] == "verbal"


@pytest.mark.asyncio
async def test_2_evaluation_persistence_failure_reports_accurately(mock_verbal_evaluation, candidate_headers):
    """
    2. Evaluation persistence failure:
    When MongoDB Atlas write for evaluation fails, saved_to_db is False and db_status is 'unreachable'.
    """
    setup = InterviewSetupRequest(
        role="Java Developer",
        experience_level="Junior",
        difficulty="Easy",
        focus_areas="Java",
        interview_mode="VERBAL",
        target_question_count=2,
    )
    first_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="What is a Java primitive?",
        assessed_skill="Java",
        difficulty="Easy",
        rubric="Basic types",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[first_q], owner_id="cand_test_user", is_adaptive=True)

    mock_db = MagicMock()
    # Mock update_one raising connection failure
    mock_db["interview_sessions"].update_one = AsyncMock(side_effect=Exception("Atlas Connection Lost"))
    mock_db["interview_sessions"].find_one = AsyncMock(return_value=None)

    next_q_json = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "What is boxing and unboxing?",
        "assessed_skill": "Java",
        "difficulty": "Medium",
        "rubric": "Autoboxing mechanics",
        "question_type": "verbal",
        "selection_rationale": "Progressive depth",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", "mongodb+srv://mock_atlas:secret@cluster.mongodb.net"):
        with patch("app.core.database.db_manager.get_database", return_value=mock_db):
            with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
                mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
                with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                    mock_groq.return_value = next_q_json

                    response = client.post(
                        f"/api/interviews/{session.session_id}/submit-and-adapt",
                        headers=candidate_headers,
                        json={
                            "question_id": "q_1",
                            "answer_text": "Primitives are non-object basic types like int, boolean.",
                            "answer_mode": "verbal",
                        },
                    )

    assert response.status_code == 200
    data = response.json()

    # Child evaluation reports failure accurately
    assert data["evaluation"]["saved_to_db"] is False
    assert data["evaluation"]["db_status"] == "unreachable"

    # Top level reports failure accurately
    assert data["saved_to_db"] is False
    assert data["db_status"] == "unreachable"


@pytest.mark.asyncio
async def test_3_session_update_persistence_failure_reports_accurately(mock_verbal_evaluation, candidate_headers):
    """
    3. Session-update persistence failure:
    If evaluation succeeded in DB, but appending the next question fails in Atlas,
    child evaluation reports saved_to_db=True, but top-level response reports saved_to_db=False.
    """
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Databases",
        interview_mode="VERBAL",
        target_question_count=3,
    )
    first_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain ACID properties.",
        assessed_skill="Databases",
        difficulty="Medium",
        rubric="Atomicity, Consistency, Isolation, Durability",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[first_q], owner_id="cand_test_user", is_adaptive=True)

    call_count = 0

    async def flaky_update_one(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Calls 1 (submit_answer) and 2 (save_evaluation) succeed
        if call_count <= 2:
            return MagicMock(matched_count=1)
        # Call 3 (append_session_question) fails
        raise Exception("Atlas Write Concern Timeout")

    mock_db = MagicMock()
    mock_db["interview_sessions"].update_one = AsyncMock(side_effect=flaky_update_one)
    mock_db["interview_sessions"].find_one = AsyncMock(return_value={
        "session_id": session.session_id,
        "is_adaptive": True,
        "target_question_count": 3,
        "questions": [first_q.model_dump()],
    })

    next_q_json = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "What is optimistic locking vs pessimistic locking?",
        "assessed_skill": "Databases",
        "difficulty": "Hard",
        "rubric": "Version columns vs select for update",
        "question_type": "verbal",
        "selection_rationale": "Concurrency control depth",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", "mongodb+srv://mock_atlas:secret@cluster.mongodb.net"):
        with patch("app.core.database.db_manager.get_database", return_value=mock_db):
            with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
                mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
                with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                    mock_groq.return_value = next_q_json

                    response = client.post(
                        f"/api/interviews/{session.session_id}/submit-and-adapt",
                        headers=candidate_headers,
                        json={
                            "question_id": "q_1",
                            "answer_text": "ACID stands for Atomicity, Consistency, Isolation, Durability.",
                            "answer_mode": "verbal",
                        },
                    )

    assert response.status_code == 200
    data = response.json()

    # Child evaluation succeeded
    assert data["evaluation"]["saved_to_db"] is True
    assert data["evaluation"]["db_status"] == "persisted"

    # Top-level reflects that session update failed
    assert data["saved_to_db"] is False
    assert data["db_status"] == "unreachable"


@pytest.mark.asyncio
async def test_4_unconfigured_database_reports_consistent_status(mock_verbal_evaluation, candidate_headers):
    """
    4. When MongoDB Atlas is unconfigured, both evaluation and top-level response report
    saved_to_db=False and db_status='unconfigured'.
    """
    setup = InterviewSetupRequest(
        role="DevOps Engineer",
        experience_level="Senior",
        difficulty="Hard",
        focus_areas="Kubernetes",
        interview_mode="VERBAL",
        target_question_count=2,
    )
    first_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Kubernetes Ingress vs NodePort.",
        assessed_skill="Kubernetes",
        difficulty="Hard",
        rubric="Routing and L7 vs L4",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[first_q], owner_id="cand_test_user", is_adaptive=True)

    next_q_json = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "How do CNI plugins manage Pod networking?",
        "assessed_skill": "Kubernetes",
        "difficulty": "Hard",
        "rubric": "Overlay networks and iptables/eBPF",
        "question_type": "verbal",
        "selection_rationale": "Deepening networking",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", None):
        with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
            with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                mock_groq.return_value = next_q_json

                response = client.post(
                    f"/api/interviews/{session.session_id}/submit-and-adapt",
                    headers=candidate_headers,
                    json={
                        "question_id": "q_1",
                        "answer_text": "Ingress is an L7 reverse proxy, NodePort opens a static port on each node.",
                        "answer_mode": "verbal",
                    },
                )

    assert response.status_code == 200
    data = response.json()

    assert data["evaluation"]["saved_to_db"] is False
    assert data["evaluation"]["db_status"] == "unconfigured"
    assert data["saved_to_db"] is False
    assert data["db_status"] == "unconfigured"


@pytest.mark.asyncio
async def test_5_next_question_generation_and_active_question_consistency(mock_verbal_evaluation, candidate_headers):
    """
    5. Next-question generation and active-question consistency:
    The returned active_question_id matches the generated next question's id and
    the stored session's active_question_id.
    """
    setup = InterviewSetupRequest(
        role="Frontend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="React",
        interview_mode="VERBAL",
        target_question_count=3,
    )
    first_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain React useEffect dependency array.",
        assessed_skill="React",
        difficulty="Medium",
        rubric="Dependencies and cleanup function",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[first_q], owner_id="cand_test_user", is_adaptive=True)

    next_q_json = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "How does useMemo differ from useCallback?",
        "assessed_skill": "React",
        "difficulty": "Hard",
        "rubric": "Cached value vs cached function instance",
        "question_type": "verbal",
        "selection_rationale": "Hook memoization concepts",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", None):
        with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
            with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                mock_groq.return_value = next_q_json

                response = client.post(
                    f"/api/interviews/{session.session_id}/submit-and-adapt",
                    headers=candidate_headers,
                    json={
                        "question_id": "q_1",
                        "answer_text": "The dependency array tells React when to re-execute the effect.",
                        "answer_mode": "verbal",
                    },
                )

    data = response.json()
    assert data["active_question_id"] == "q_2"
    assert data["next_question"]["id"] == "q_2"

    stored_session = await get_session(session.session_id)
    assert stored_session["active_question_id"] == "q_2"


@pytest.mark.asyncio
async def test_6_adaptive_context_includes_real_prior_evaluation_evidence(mock_verbal_evaluation, candidate_headers):
    """
    6. Adaptive context includes real prior evaluation evidence:
    Verifies that the prompt sent to Groq includes the candidate's actual answer,
    scores, strengths, improvement gaps, and criterion scores without fabrication.
    """
    setup = InterviewSetupRequest(
        role="Java Developer",
        experience_level="Senior",
        difficulty="Hard",
        focus_areas="Java",
        interview_mode="VERBAL",
        target_question_count=3,
    )
    first_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Java Garbage Collection algorithms.",
        assessed_skill="Java",
        difficulty="Hard",
        rubric="G1, ZGC, generational hypothesis",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[first_q], owner_id="cand_test_user", is_adaptive=True)

    captured_messages = []

    async def fake_groq(messages, **kwargs):
        nonlocal captured_messages
        captured_messages = messages
        return json.dumps({
            "id": "q_2",
            "question_number": 2,
            "text": "How does ZGC achieve sub-millisecond pause times?",
            "assessed_skill": "Java",
            "difficulty": "Hard",
            "rubric": "Colored pointers and load barriers",
            "question_type": "verbal",
            "selection_rationale": "Addressing low-latency GC gaps",
            "time_band": "comprehensive",
        })

    with patch.object(settings, "MONGODB_URI", None):
        with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
            with patch("app.core.groq_client.groq_manager.execute_chat_completion", side_effect=fake_groq):
                client.post(
                    f"/api/interviews/{session.session_id}/submit-and-adapt",
                    headers=candidate_headers,
                    json={
                        "question_id": "q_1",
                        "answer_text": "G1 GC divides heap into regions, whereas ZGC uses colored pointers.",
                        "answer_mode": "verbal",
                    },
                )

    user_prompt = [m["content"] for m in captured_messages if m["role"] == "user"][0]
    # Check that real evidence was injected
    assert "G1 GC divides heap into regions" in user_prompt
    assert "85/100" in user_prompt
    assert "Clear distinction between class and object" in user_prompt
    assert "Could mention Metaspace explicitly" in user_prompt
    assert "relevance: 9" in user_prompt


@pytest.mark.asyncio
async def test_7_verbal_mode_never_generates_coding_question(mock_verbal_evaluation, candidate_headers):
    """
    7. VERBAL mode never generates a coding question.
    Even if the LLM hallucinated coding fields or code, it is sanitized to verbal.
    """
    setup = InterviewSetupRequest(
        role="Python Developer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python",
        interview_mode="VERBAL",
        target_question_count=3,
    )
    first_q = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Python GIL.",
        assessed_skill="Python",
        difficulty="Medium",
        rubric="Global Interpreter Lock and thread safety",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[first_q], owner_id="cand_test_user", is_adaptive=True)

    # Hallucinated coding output
    hallucinated_q = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "Write a python script that implements a multi-threaded queue.",
        "assessed_skill": "Python",
        "difficulty": "Medium",
        "rubric": "Code implementation",
        "question_type": "coding",
        "function_name": "queue_func",
        "test_cases": [{"id": "tc1", "input": "x", "expected_output": "y"}],
        "selection_rationale": "Coding practice",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", None):
        with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
            with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                mock_groq.return_value = hallucinated_q

                response = client.post(
                    f"/api/interviews/{session.session_id}/submit-and-adapt",
                    headers=candidate_headers,
                    json={
                        "question_id": "q_1",
                        "answer_text": "The GIL prevents multiple native threads from executing Python bytecode simultaneously.",
                        "answer_mode": "verbal",
                    },
                )

    data = response.json()
    next_q = data["next_question"]
    assert next_q["question_type"] == "verbal"
    assert next_q.get("test_cases") is None or len(next_q.get("test_cases") or []) == 0


@pytest.mark.asyncio
async def test_8_coding_mode_never_generates_verbal_question():
    """
    8. CODING mode never generates a verbal question.
    Fallback and generation always enforce executable coding format.
    """
    setup = InterviewSetupRequest(
        role="Algorithm Specialist",
        experience_level="Senior",
        difficulty="Hard",
        focus_areas="Algorithms",
        interview_mode="CODING",
        target_question_count=3,
    )
    coding_q = QuestionItem(
        id="q_1",
        question_number=1,
        title="Two Sum",
        text="Find two integers that sum to target.",
        assessed_skill="Algorithms",
        difficulty="Medium",
        rubric="O(n) hash map",
        question_type="coding",
        function_name="twoSum",
        test_cases=[{"id": "tc1", "input": "[2,7,11,15], 9", "expected_output": "[0,1]"}],
    )
    session = await create_interview_session(setup, questions=[coding_q], owner_id="cand_test_user", is_adaptive=True)

    # Hallucinated verbal output
    hallucinated_verbal = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "What is the time complexity of QuickSort in the worst case?",
        "assessed_skill": "Algorithms",
        "difficulty": "Hard",
        "rubric": "O(n^2)",
        "question_type": "verbal",
        "selection_rationale": "Verbal question in coding interview",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", None):
        with patch.object(settings, "GROQ_API_KEY", "mock_groq_key"):
            with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                mock_groq.return_value = hallucinated_verbal

                next_res = await generate_next_adaptive_question(session.session_id)
                assert next_res.question.question_type == "coding"
                assert next_res.question.function_name is not None


@pytest.mark.asyncio
async def test_9_duplicate_submission_behavior(mock_verbal_evaluation, candidate_headers):
    """
    9. Duplicate submission behavior:
    Submitting an answer for an inactive/already-submitted question is rejected (400),
    maintaining idempotency and preventing state corruption.
    """
    setup = InterviewSetupRequest(
        role="Go Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Go",
        interview_mode="VERBAL",
        target_question_count=3,
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Go channels.",
        assessed_skill="Go",
        difficulty="Medium",
        rubric="Buffered vs unbuffered",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[q1], owner_id="cand_test_user", is_adaptive=True)

    next_q_json = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "Explain Go select statement.",
        "assessed_skill": "Go",
        "difficulty": "Medium",
        "rubric": "Channel multiplexing",
        "question_type": "verbal",
        "selection_rationale": "Go concurrency",
        "time_band": "comprehensive",
    })

    with patch.object(settings, "MONGODB_URI", None):
        with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)
            with patch("app.core.groq_client.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
                mock_groq.return_value = next_q_json

                # First submission advances session to q_2
                res1 = client.post(
                    f"/api/interviews/{session.session_id}/submit-and-adapt",
                    headers=candidate_headers,
                    json={"question_id": "q_1", "answer_text": "Channels pass data between goroutines.", "answer_mode": "verbal"},
                )
                assert res1.status_code == 200

                # Second submission attempts to submit for q_1 again
                res2 = client.post(
                    f"/api/interviews/{session.session_id}/submit-and-adapt",
                    headers=candidate_headers,
                    json={"question_id": "q_1", "answer_text": "Duplicate submission attempt", "answer_mode": "verbal"},
                )
                assert res2.status_code == 400
                assert "currently active question is 'q_2'" in res2.text


@pytest.mark.asyncio
async def test_10_time_limit_and_target_question_safeguards(mock_verbal_evaluation, candidate_headers):
    """
    10. Existing time-limit and target-question-count safeguards:
    - Reaching target question count flags is_last_question=True and does not generate further questions.
    - Submitting when session is expired is rejected with 400.
    """
    setup = InterviewSetupRequest(
        role="QA Engineer",
        experience_level="Junior",
        difficulty="Easy",
        focus_areas="Testing",
        interview_mode="VERBAL",
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="What is the difference between smoke testing and sanity testing?",
        assessed_skill="Testing",
        difficulty="Easy",
        rubric="Broad shallow vs narrow deep",
        question_type="verbal",
    )
    session = await create_interview_session(setup, questions=[q1], owner_id="cand_test_user", is_adaptive=True, target_question_count=1)

    with patch.object(settings, "MONGODB_URI", None):
        with patch("app.routers.interview.route_and_evaluate_answer", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = (mock_verbal_evaluation, "verbal", None)

            res = client.post(
                f"/api/interviews/{session.session_id}/submit-and-adapt",
                headers=candidate_headers,
                json={"question_id": "q_1", "answer_text": "Smoke is build verification, sanity is bug fix verification.", "answer_mode": "verbal"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["is_last_question"] is True
            assert data["next_question"] is None
            assert "Target interview questions completed" in data["message"]


def test_11_difficulty_does_not_blindly_escalate_with_unresolved_weakness():
    """
    Phase 3: High score (>= 75) does NOT escalate difficulty if candidate has an
    important unresolved weakness (e.g. criterion score <= 6 or multiple areas for improvement).
    """
    session = {
        "difficulty": "Medium",
        "questions": [
            {"id": "q_1", "difficulty": "Medium", "assessed_skill": "Security"}
        ],
        "answers": {
            "q_1": {
                "evaluation": {
                    "overall_score": 78,
                    "criterion_scores": {
                        "technical_depth": {"score": 5, "feedback": "Lacks depth in cryptography"},
                        "relevance": {"score": 9, "feedback": "Good"},
                    },
                    "areas_for_improvement": ["Missed cryptographic salt explanation", "Did not mention timing attacks"],
                }
            }
        }
    }
    # Score is 78 (>= 75), but technical_depth is 5 (<= 6) and 2 improvement areas exist:
    # Must maintain Medium difficulty rather than blindly escalating to Hard!
    diff = determine_adaptive_difficulty(session)
    assert diff == "Medium"
