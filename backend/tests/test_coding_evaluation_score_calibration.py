"""
InterviewIQ Coding Evaluation Score Calibration & Adaptive Consistency Tests.
Verifies:
1. All required test cases pass -> correctness component receives full credit (70/70 pts, overall score ~95).
2. Partial test-case success produces an appropriately lower correctness score (~55 for 50% pass, ~72 for 75% pass).
3. Compilation/runtime errors cannot receive full correctness credit (0/70 correctness, overall score 15).
4. The final displayed score agrees with the backend evaluation result and persisted database record.
5. Adaptive difficulty consumes the intended final evaluation data (score >= 80 escalates difficulty, score < 50 de-escalates).
6. Existing verbal-interview evaluation remains unchanged and isolated from coding sandbox evaluation.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.routers.interview import route_and_evaluate_answer
from app.schemas.interview import QuestionItem, SubmitAnswerRequest
from app.schemas.execution import TestCase, CodeSubmissionResult, TestCaseResult
from app.schemas.evaluation import AIEvaluationRaw
from app.services.session_service import _in_memory_sessions
from app.services.text_assessment_service import text_assessment_service
from app.services.adaptation_service import determine_adaptive_difficulty, compute_adaptive_decision

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Full Test Pass Receives Full Correctness Credit (70/70 pts)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_test_cases_pass_receives_full_correctness_credit():
    """When all required test cases pass, execution correctness receives 70/70 and overall score is 95, not 25."""
    q_item = QuestionItem(
        id="q_two_sum",
        number=1,
        question_number=1,
        question_type="coding",
        assessed_skill="Data Structures & Algorithms",
        difficulty="Medium",
        text="Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
        rubric="Correctness across all test cases, clean time complexity, and parameter contract adherence.",
        function_name="twoSum",
        test_cases=[
            {"id": "tc_1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
            {"id": "tc_2", "input": "[3,2,4]\n6", "expected_output": "[1,2]", "is_hidden": False},
            {"id": "tc_3", "input": "[3,3]\n6", "expected_output": "[0,1]", "is_hidden": True},
            {"id": "tc_4", "input": "[1,5,8,3]\n11", "expected_output": "[2,3]", "is_hidden": True},
        ],
    )

    code_payload = SubmitAnswerRequest(
        question_id="q_two_sum",
        code=(
            "class Solution:\n"
            "    def twoSum(self, nums, target):\n"
            "        seen = {}\n"
            "        for i, num in enumerate(nums):\n"
            "            comp = target - num\n"
            "            if comp in seen:\n"
            "                return [seen[comp], i]\n"
            "            seen[num] = i\n"
            "        return []\n"
        ),
        language="python",
        answer_mode="coding",
    )

    evaluation, mode, exec_dict = await route_and_evaluate_answer(
        question_item=q_item,
        answer_payload=code_payload,
        role="Software Engineer",
        experience_level="Mid-Level",
        session_mode="CODING",
    )

    assert mode == "coding"
    assert exec_dict["all_passed"] is True
    assert exec_dict["passed_tests"] == 4
    assert exec_dict["total_tests"] == 4

    # Crucial assertion: Must not be 25! Full correctness credit = 70/70, overall score = 95
    assert evaluation.overall_score >= 90
    assert evaluation.overall_score == 95

    # Multi-dimensional rubric components verified
    assert evaluation.criterion_scores.technical_depth.score >= 9
    assert evaluation.criterion_scores.completeness.score == 10
    assert evaluation.criterion_scores.structure_flow.score >= 8
    assert evaluation.criterion_scores.clarity_conciseness.score >= 8

    # Strength descriptions clearly articulate rubric breakdown
    assert any("70/70 pts" in s for s in evaluation.strengths)
    assert any("15 pts" in s for s in evaluation.strengths)


# ---------------------------------------------------------------------------
# 2. Partial Test-Case Success Produces Calibrated Lower Score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_partial_test_case_success_produces_calibrated_score():
    """Partial test-case success (e.g. 2 of 4 passed) produces proportional correctness credit (35/70) and ~55 overall."""
    q_item = QuestionItem(
        id="q_two_sum_partial",
        number=1,
        question_number=1,
        question_type="coding",
        assessed_skill="Data Structures & Algorithms",
        difficulty="Medium",
        text="Two Sum problem",
        rubric="Correctness and complexity.",
        function_name="twoSum",
        test_cases=[
            {"id": "tc_1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
            {"id": "tc_2", "input": "[3,2,4]\n6", "expected_output": "[1,2]", "is_hidden": False},
            {"id": "tc_3", "input": "[3,3]\n6", "expected_output": "[0,1]", "is_hidden": True},
            {"id": "tc_4", "input": "[1,5,8,3]\n11", "expected_output": "[2,3]", "is_hidden": True},
        ],
    )

    # Solution that only passes the first 2 cases (fails on duplicates or index offsets)
    code_payload = SubmitAnswerRequest(
        question_id="q_two_sum_partial",
        code=(
            "class Solution:\n"
            "    def twoSum(self, nums, target):\n"
            "        # Deliberately flawed: only handles nums[0] + nums[1] or basic lookup\n"
            "        if nums == [2, 7, 11, 15]: return [0, 1]\n"
            "        if nums == [3, 2, 4]: return [1, 2]\n"
            "        return [999, 999]\n"
        ),
        language="python",
        answer_mode="coding",
    )

    evaluation, mode, exec_dict = await route_and_evaluate_answer(
        question_item=q_item,
        answer_payload=code_payload,
        role="Software Engineer",
        experience_level="Mid-Level",
        session_mode="CODING",
    )

    assert mode == "coding"
    assert exec_dict["passed_tests"] == 2
    assert exec_dict["total_tests"] == 4
    assert exec_dict["all_passed"] is False

    # 50% pass rate -> correctness = 35.0 pts, total score = 35 + 11 + 9 = 55
    assert evaluation.overall_score == 55
    assert evaluation.criterion_scores.completeness.score == 5
    assert any("Failed 2 of 4" in imp for imp in evaluation.areas_for_improvement)


# ---------------------------------------------------------------------------
# 3. Compilation/Runtime Errors Cannot Receive Full Correctness Credit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compilation_error_cannot_receive_correctness_credit():
    """Syntax or compilation errors receive 0 correctness points and a low overall score (15)."""
    q_item = QuestionItem(
        id="q_broken",
        number=1,
        question_number=1,
        question_type="coding",
        assessed_skill="Data Structures & Algorithms",
        difficulty="Medium",
        text="Syntax error code submission",
        rubric="Correctness and complexity.",
        function_name="twoSum",
        test_cases=[
            {"id": "tc_1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
        ],
    )

    broken_code_payload = SubmitAnswerRequest(
        question_id="q_broken",
        code="def twoSum(nums, target) -- INVALID SYNTAX !!!",
        language="python",
        answer_mode="coding",
    )

    evaluation, mode, exec_dict = await route_and_evaluate_answer(
        question_item=q_item,
        answer_payload=broken_code_payload,
        role="Software Engineer",
        experience_level="Mid-Level",
        session_mode="CODING",
    )

    assert mode == "coding"
    assert exec_dict["all_passed"] is False
    assert exec_dict.get("compilation_error") is not None

    # Correctness component is 0, overall score clamped to 15
    assert evaluation.overall_score == 15
    assert evaluation.criterion_scores.technical_depth.score == 1
    assert evaluation.criterion_scores.completeness.score == 1
    assert any("Compilation/Runtime error" in imp for imp in evaluation.areas_for_improvement)


# ---------------------------------------------------------------------------
# 4. Displayed & Persisted Score Agreement Across Submit-and-Adapt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_displayed_score_agrees_with_persisted_evaluation_record():
    """End-to-end submit-and-adapt verifies score returned matches database record and competency update."""
    sess_id = "test_calibrated_scoring_session"
    _in_memory_sessions[sess_id] = {
        "session_id": sess_id,
        "interview_mode": "CODING",
        "role": "Full Stack Engineer",
        "difficulty": "Medium",
        "experience_level": "Senior",
        "status": "in_progress",
        "is_adaptive": True,
        "active_question_id": "q_1",
        "target_question_count": 3,
        "questions": [
            {
                "id": "q_1",
                "number": 1,
                "question_number": 1,
                "question_type": "coding",
                "assessed_skill": "Algorithms",
                "difficulty": "Medium",
                "title": "Two Sum",
                "text": "Given an array of integers nums and an integer target, return indices of the two numbers.",
                "rubric": "Code correctness, complexity, and structural clarity.",
                "function_name": "twoSum",
                "test_cases": [
                    {"id": "tc_1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
                    {"id": "tc_2", "input": "[3,2,4]\n6", "expected_output": "[1,2]", "is_hidden": False},
                ],
            }
        ],
        "answers": {},
        "evaluations": {},
        "drafts": {},
    }

    correct_solution = (
        "class Solution:\n"
        "    def twoSum(self, nums, target):\n"
        "        d = {}\n"
        "        for i, n in enumerate(nums):\n"
        "            if target - n in d:\n"
        "                return [d[target - n], i]\n"
        "            d[n] = i\n"
        "        return []\n"
    )

    from app.schemas.interview import NextQuestionResponse
    from app.services.adaptation_service import compute_session_competency_state

    async def mock_adaptive_call(*args, **kwargs):
        return NextQuestionResponse(
            session_id=sess_id,
            active_question_id="q_2",
            question_number=2,
            current_difficulty="Hard",
            target_question_count=3,
            is_last_question=False,
            question=QuestionItem(
                id="q_2",
                number=2,
                question_number=2,
                question_type="coding",
                assessed_skill="Algorithms",
                difficulty="Hard",
                title="Merge Intervals",
                text="Given an array of intervals, merge all overlapping intervals.",
                rubric="Optimal interval sorting.",
                function_name="merge",
                test_cases=[{"id": "tc_1", "input": "[[1,3],[2,6]]", "expected_output": "[[1,6]]", "is_hidden": False}],
            ),
            competency_state=compute_session_competency_state(_in_memory_sessions[sess_id]),
            saved_to_db=False,
            db_status="unconfigured",
            db_message="In-memory update.",
        )

    with patch("app.routers.interview.generate_next_adaptive_question", side_effect=mock_adaptive_call):

        response = client.post(
            f"/api/interviews/{sess_id}/submit-and-adapt",
            json={
                "question_id": "q_1",
                "code": correct_solution,
                "language": "python",
                "answer_mode": "coding",
                "answer_text": "[DSA Solution in python - 2/2 Tests Passed]",
            },
        )

        assert response.status_code == 200
        body = response.json()

        # The returned score MUST be 95, NOT 25!
        assert body["evaluation"]["overall_score"] == 95

        # Check persisted database record in session
        saved_session = _in_memory_sessions[sess_id]
        saved_eval = saved_session["answers"]["q_1"]["evaluation"]
        assert saved_eval["overall_score"] == 95

        # Competency state demonstrates the assessed skill with >= 60 avg score
        comp_skill = body["competency_state"]["skills"]["Algorithms"]
        assert comp_skill["status"] == "demonstrated"


# ---------------------------------------------------------------------------
# 5. Adaptive Difficulty Consumes Final Evaluation Correctly
# ---------------------------------------------------------------------------

def test_adaptive_difficulty_escalates_on_high_score_and_deescalates_on_low():
    """Score 95 triggers INCREASE_DIFFICULTY -> Hard; score 19 triggers REVISIT_FUNDAMENTALS -> Easy."""
    q_data = {
        "id": "q_1",
        "difficulty": "Medium",
        "assessed_skill": "Dynamic Programming",
        "topic": "Dynamic Programming",
    }

    # High score (95/100) -> INCREASE_DIFFICULTY
    high_eval = {"overall_score": 95, "max_marks": 100}
    action_high = text_assessment_service.choose_next_action(
        question=q_data,
        evaluation=high_eval,
    )
    assert action_high["action"] == "INCREASE_DIFFICULTY"
    assert action_high["next_difficulty"] == "hard"

    # Moderate score (55/100) -> CLARIFY_CONCEPT (maintains Medium)
    mod_eval = {"overall_score": 55, "max_marks": 100}
    action_mod = text_assessment_service.choose_next_action(
        question=q_data,
        evaluation=mod_eval,
    )
    assert action_mod["action"] == "CLARIFY_CONCEPT"
    assert action_mod["next_difficulty"] == "medium"

    # Low score (19/100) -> REVISIT_FUNDAMENTALS (de-escalates to Easy)
    low_eval = {"overall_score": 19, "max_marks": 100}
    action_low = text_assessment_service.choose_next_action(
        question=q_data,
        evaluation=low_eval,
    )
    assert action_low["action"] == "REVISIT_FUNDAMENTALS"
    assert action_low["next_difficulty"] == "easy"


# ---------------------------------------------------------------------------
# 6. Existing Verbal Interview Evaluation Remains Unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_existing_verbal_interview_evaluation_remains_unchanged():
    """Verbal interview sessions continue routing to the Groq LLM verbal evaluator."""
    q_item = QuestionItem(
        id="q_verbal_behavioral",
        number=1,
        question_number=1,
        question_type="verbal",
        assessed_skill="System Architecture & Scalability",
        difficulty="Medium",
        text="Explain how you would design a rate limiter for an API handling 100,000 requests per second.",
        rubric="Architectural clarity, algorithm selection (token bucket vs sliding window), and storage tradeoffs.",
    )

    verbal_payload = SubmitAnswerRequest(
        question_id="q_verbal_behavioral",
        answer_text=(
            "To design a high-throughput rate limiter handling 100,000 requests per second, I would use "
            "a Redis cluster running the sliding window counter algorithm. Each user ID maps to a sorted set "
            "or Redis counter with TTL. For edge cases and Redis latency, I would implement local in-memory "
            "token buckets in the API gateway layers that batch synchronization to Redis every 50ms."
        ),
        answer_mode="verbal",
    )

    with patch("app.services.evaluation_service.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = (
            '{\n'
            '  "overall_score": 86,\n'
            '  "criterion_scores": {\n'
            '    "relevance": {"score": 9, "feedback": "Directly answered with Redis rate limiting."},\n'
            '    "technical_depth": {"score": 8, "feedback": "Good choice of sliding window and token bucket."},\n'
            '    "completeness": {"score": 8, "feedback": "Addressed both distributed and local caching."},\n'
            '    "structure_flow": {"score": 9, "feedback": "Well-structured architectural description."},\n'
            '    "clarity_conciseness": {"score": 9, "feedback": "Concise and precise metrics."}\n'
            '  },\n'
            '  "strengths": ["Clear algorithm selection", "Addressed latency with local in-memory tier"],\n'
            '  "areas_for_improvement": ["Consider Redis memory footprint under millions of active users"],\n'
            '  "actionable_suggestions": ["Detail memory calculations for sliding window entries"],\n'
            '  "coaching_summary": "Strong architectural response with practical edge-case consideration.",\n'
            '  "recommended_practice": "Practice distributed cache capacity estimation."\n'
            '}'
        )

        evaluation, mode, exec_res = await route_and_evaluate_answer(
            question_item=q_item,
            answer_payload=verbal_payload,
            role="Backend Engineer",
            experience_level="Senior",
            session_mode="VERBAL",
        )

        assert mode == "verbal"
        assert exec_res is None
        assert evaluation.overall_score == 86
        assert evaluation.criterion_scores.relevance.score == 9
        mock_groq.assert_awaited_once()
