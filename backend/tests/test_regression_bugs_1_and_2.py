import pytest
import asyncio
from app.core.problem_catalog import (
    find_benchmark_problem,
    normalize_and_classify_question,
    BENCHMARK_PROBLEMS,
)
from app.services.oracle_service import (
    verify_and_repair_coding_question,
)
from app.services.code_execution_service import (
    compare_outputs,
    structural_equal,
)
from app.services.session_service import (
    create_interview_session,
    get_session,
    save_question_draft,
    get_session_drafts,
    audit_and_heal_session_coding_questions,
    append_session_question,
)
from app.services.report_service import generate_interview_report
from app.schemas.interview import (
    InterviewSetupRequest,
    SaveDraftRequest,
    SubmitAnswerRequest,
    QuestionItem,
)
from app.routers.interview import (
    submit_code,
)
from app.schemas.execution import SubmitCodeSolutionRequest, TestCase


@pytest.mark.asyncio
async def test_maximum_length_subarray_catalog_and_expected_outputs():
    """Bug 2 regression test: Maximum Length Subarray has non-empty verified expected outputs."""
    bm = find_benchmark_problem("Given two integer arrays nums1 and nums2, return the maximum length of a subarray that appears in both arrays.", "Maximum Length of Repeated Subarray")
    assert bm is not None
    assert bm["id"] == "maximum_length_subarray"
    assert bm["function_name"] == "findLength"

    test_cases = bm.get("test_cases", [])
    assert len(test_cases) >= 3
    for tc in test_cases:
        assert tc.get("expected_output") is not None
        assert str(tc.get("expected_output")).strip() != ""
        # Must not be placeholder or dummy text
        assert "awaiting" not in str(tc.get("expected_output")).lower()

    # Case 1: [1,2,3,2,1], [3,2,1,4,7] -> 3 (subarray [3,2,1])
    assert str(test_cases[0]["expected_output"]).strip() == "3"
    # Case 2: [0,0,0,0,0], [0,0,0,0,0] -> 5
    assert str(test_cases[1]["expected_output"]).strip() == "5"


@pytest.mark.asyncio
async def test_maximum_length_subarray_heals_missing_expected_outputs():
    """Bug 2 regression test: healing question when expected_output is missing."""
    broken_question = {
        "id": "q_broken_max_length",
        "title": "Maximum Length Subarray",
        "text": "Given two integer arrays nums1 and nums2, return the maximum length of an array that appears in both.",
        "assessed_skill": "Dynamic Programming",
        "difficulty": "Medium",
        "question_type": "coding",
        "function_name": "findLength",
        "test_cases": [
            {"id": "tc_1", "input": "[1,2,3,2,1]\n[3,2,1,4,7]", "expected_output": "", "is_hidden": False},
            {"id": "tc_2", "input": "[0,0,0,0,0]\n[0,0,0,0,0]", "expected_output": None, "is_hidden": False},
        ],
    }

    healed = await verify_and_repair_coding_question(broken_question)
    assert healed["oracle_verified"] is True
    tcs = healed["test_cases"]
    assert len(tcs) >= 2
    for tc in tcs:
        assert tc["expected_output"] is not None and str(tc["expected_output"]).strip() != ""
    assert str(tcs[0]["expected_output"]).strip() == "3"
    assert str(tcs[1]["expected_output"]).strip() == "5"


@pytest.mark.asyncio
async def test_maximum_length_subarray_correct_solution_passes():
    """Bug 2 regression test: correct solution passes judge for Maximum Length Subarray."""
    correct_python = '''
class Solution:
    def findLength(self, nums1, nums2):
        m, n = len(nums1), len(nums2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        ans = 0
        for i in range(m - 1, -1, -1):
            for j in range(n - 1, -1, -1):
                if nums1[i] == nums2[j]:
                    dp[i][j] = dp[i + 1][j + 1] + 1
                    if dp[i][j] > ans:
                        ans = dp[i][j]
        return ans
'''
    bm = find_benchmark_problem("maximum length of repeated subarray", "Maximum Length Subarray")
    test_cases = [TestCase(**tc) for tc in bm["test_cases"]]

    req = SubmitCodeSolutionRequest(
        question_id="maximum_length_subarray",
        language="python",
        code=correct_python,
        test_cases=test_cases,
        function_name="findLength",
    )
    result = await submit_code(req)
    assert result.all_passed is True
    assert result.passed_tests == len(test_cases)
    assert result.compilation_error is None


@pytest.mark.asyncio
async def test_maximum_length_subarray_incorrect_solution_fails():
    """Bug 2 regression test: incorrect solution fails judge for Maximum Length Subarray."""
    incorrect_python = '''
class Solution:
    def findLength(self, nums1, nums2):
        # Deliberately flawed implementation returning -1
        return -1
'''
    bm = find_benchmark_problem("maximum length of repeated subarray", "Maximum Length Subarray")
    test_cases = [TestCase(**tc) for tc in bm["test_cases"]]

    req = SubmitCodeSolutionRequest(
        question_id="maximum_length_subarray",
        language="python",
        code=incorrect_python,
        test_cases=test_cases,
        function_name="findLength",
    )
    result = await submit_code(req)
    assert result.all_passed is False
    assert result.passed_tests == 0


@pytest.mark.asyncio
async def test_navigation_without_attempt_preserves_order_and_unanswered_status():
    """Bug 1 regression test: Candidate can advance without attempt; question remains unanswered and unpenalized."""
    q1 = QuestionItem(
        id="q_1",
        title="Two Sum",
        text="Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
        difficulty="Easy",
        assessed_skill="Hash Tables",
        question_type="coding",
        function_name="twoSum",
        test_cases=[],
    )
    setup_req = InterviewSetupRequest(
        role="Full Stack Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Algorithms, Data Structures",
        question_count=3,
        interview_mode="CODING",
        adaptive=True,
    )
    session = await create_interview_session(setup_req, [q1], is_adaptive=True, target_question_count=3)
    session_id = session.session_id

    # Session starts with question 1
    assert len(session.questions) == 1
    q1_id = session.questions[0].id

    # 1. Candidate autosaves some code in draft without submitting answer
    draft_req = SaveDraftRequest(
        language="python",
        code="def twoSum(nums, target):\n    # Draft in progress\n    pass",
        version=1,
    )
    save_res = await save_question_draft(session_id, q1_id, draft_req)
    assert save_res.saved_to_db is True or save_res.db_status in ("persisted", "saved_memory", "unconfigured")

    # 2. Candidate navigates to next question WITHOUT submitting
    q2 = QuestionItem(
        id="q_2",
        title="Valid Parentheses",
        text="Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.",
        difficulty="Easy",
        assessed_skill="Stack",
        question_type="coding",
        function_name="isValid",
        test_cases=[],
    )
    await append_session_question(session_id, q2)

    # Verify session now has both questions in order
    updated_session = await get_session(session_id)
    assert len(updated_session["questions"]) == 2
    assert updated_session["questions"][0]["id"] == q1_id
    assert updated_session["questions"][1]["id"] == "q_2"

    # Verify question 1 was NOT marked as submitted or evaluated
    answers = updated_session.get("answers", {})
    assert q1_id not in answers or not answers[q1_id].get("evaluation")

    # 3. Candidate returns to question 1 and checks draft restoration
    drafts_dict = await get_session_drafts(session_id)
    assert q1_id in drafts_dict
    assert "python" in drafts_dict[q1_id]
    assert "Draft in progress" in drafts_dict[q1_id]["python"]["code"]

    # 4. Generate final report and verify skipped question 1 is tracked as unanswered
    report = await generate_interview_report(session_id)
    assert report.total_questions == 2
    # Verify performance summary for q1 marks unanswered
    q1_perf = next((qp for qp in report.questions_performance if qp.question_id == q1_id), None)
    assert q1_perf is not None
    assert q1_perf.is_evaluated is False
    assert q1_perf.answer_availability == "unanswered"
    assert q1_perf.overall_score is None


@pytest.mark.asyncio
async def test_rapid_draft_saves_do_not_cross_contaminate_questions():
    """Bug 1 regression test: drafts for different question IDs and languages stay strictly isolated."""
    q1 = QuestionItem(id="q_1", title="Problem One", text="Problem 1 detailed description here.", difficulty="Easy", assessed_skill="Algo", question_type="coding", test_cases=[])
    q2 = QuestionItem(id="q_2", title="Problem Two", text="Problem 2 detailed description here.", difficulty="Medium", assessed_skill="Algo", question_type="coding", test_cases=[])
    q3 = QuestionItem(id="q_3", title="Problem Three", text="Problem 3 detailed description here.", difficulty="Hard", assessed_skill="Algo", question_type="coding", test_cases=[])
    setup_req = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Senior",
        difficulty="Hard",
        focus_areas="Algorithms",
        question_count=3,
        interview_mode="CODING",
        adaptive=False,
    )
    session = await create_interview_session(setup_req, [q1, q2, q3], is_adaptive=False, target_question_count=3)
    session_id = session.session_id

    # Rapid concurrent draft saves on q1 (python) and q2 (javascript)
    await asyncio.gather(
        save_question_draft(session_id, "q_1", SaveDraftRequest(language="python", code="# Q1 python code", version=1)),
        save_question_draft(session_id, "q_2", SaveDraftRequest(language="javascript", code="// Q2 js code", version=1)),
        save_question_draft(session_id, "q_1", SaveDraftRequest(language="cpp", code="// Q1 cpp code", version=1)),
    )

    drafts = await get_session_drafts(session_id)
    assert drafts["q_1"]["python"]["code"] == "# Q1 python code"
    assert drafts["q_1"]["cpp"]["code"] == "// Q1 cpp code"
    assert drafts["q_2"]["javascript"]["code"] == "// Q2 js code"
    # Ensure q2 has no python draft from q1
    assert "python" not in drafts["q_2"]
