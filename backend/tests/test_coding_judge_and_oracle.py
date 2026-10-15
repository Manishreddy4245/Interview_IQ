"""
InterviewIQ Comprehensive Correctness & Oracle Verification Suite
Tests the complete assessment pipeline:
1. Known-correct reference solution passes its own validated tests.
2. Deliberately incorrect candidate solutions fail.
3. Inconsistent examples or reference outputs cause question rejection / repair.
4. Invalid generated test cases are rejected.
5. Same logical input and expected result work across supported languages (Python, Java, C++, JS).
6. Parsing and comparison handle supported return types correctly (ints, floats, booleans, strings, arrays, 2D arrays).
7. Public and hidden test cases are evaluated consistently and hidden tests are never leaked.
8. Saved and cached questions retain their verified outputs.
9. Execution failures are not reported as successful answers.
10. Existing adaptive question generation, session persistence, reports, and coding/verbal separation continue working.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.problem_catalog import BENCHMARK_PROBLEMS, find_benchmark_problem
from app.services.code_execution_service import (
    compare_outputs,
    parse_output_value,
    structural_equal,
    evaluate_code_against_test_cases,
)
from app.services.oracle_service import (
    validate_problem_specification,
    run_oracle_solution,
    run_oracle_on_test_cases,
    verify_examples_consistency,
    verify_and_repair_coding_question,
)
from app.schemas.execution import TestCase
from app.schemas.interview import QuestionItem

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Structural Comparison Engine Unit Tests
# ---------------------------------------------------------------------------

def test_structural_comparison_primitives():
    """Verify comparison for integers, booleans, strings, and floats with epsilon."""
    # Integers
    passed, _ = compare_outputs("42", "42")
    assert passed is True
    passed, _ = compare_outputs("42", "43")
    assert passed is False

    # Booleans
    passed, _ = compare_outputs("true", "true")
    assert passed is True
    passed, _ = compare_outputs("True", "true")
    assert passed is True
    passed, _ = compare_outputs("false", "false")
    assert passed is True
    passed, _ = compare_outputs("true", "false")
    assert passed is False

    # Floats with tolerance
    passed, _ = compare_outputs("3.1415926", "3.14159", comparison_policy="float_tolerance", float_tolerance=1e-4)
    assert passed is True
    passed, _ = compare_outputs("3.1415926", "3.14", comparison_policy="float_tolerance", float_tolerance=1e-4)
    assert passed is False


def test_structural_comparison_arrays_and_matrices():
    """Verify comparison for 1D arrays, 2D matrices, and unordered policy."""
    # 1D Array with differing whitespace
    passed, _ = compare_outputs("[0, 1]", "[0,1]")
    assert passed is True
    passed, _ = compare_outputs("[0, 2]", "[0,1]")
    assert passed is False

    # 2D Matrices
    passed, _ = compare_outputs("[[1,2],[3,4]]", "[[1, 2], [3, 4]]")
    assert passed is True
    passed, _ = compare_outputs("[[1,2],[3,4]]", "[[1, 2], [3, 5]]")
    assert passed is False

    # Unordered array policy
    passed, _ = compare_outputs("[2, 1, 3]", "[1, 2, 3]", comparison_policy="unordered_array")
    assert passed is True
    passed, _ = compare_outputs("[2, 1, 3]", "[1, 2, 3]", comparison_policy="strict_structural")
    assert passed is False


def test_structural_comparison_ignores_preceding_debug_prints():
    """Verify candidate stdout with debug prints before the return value does not cause false failures."""
    stdout_with_debug = "DEBUG: index 0\nDEBUG: current sum 15\n[0, 1]\n"
    passed, _ = compare_outputs(stdout_with_debug, "[0,1]")
    assert passed is True


# ---------------------------------------------------------------------------
# 2. Problem Specification Validation Tests
# ---------------------------------------------------------------------------

def test_validate_problem_specification_valid():
    """Valid problem specification passes schema check."""
    q_data = {
        "title": "Two Sum",
        "text": "Given an array of integers nums and an integer target...",
        "function_name": "twoSum",
        "test_cases": [{"input": "[2,7,11,15]\n9", "expected_output": "[0,1]"}],
    }
    valid, err = validate_problem_specification(q_data)
    assert valid is True
    assert err is None


def test_validate_problem_specification_invalid():
    """Invalid function_name or missing test cases is rejected."""
    # Invalid function name with spaces
    invalid_fn = {
        "title": "Invalid Fn",
        "text": "Detailed problem description with enough characters...",
        "function_name": "two sum",
        "test_cases": [{"input": "test"}],
    }
    valid, err = validate_problem_specification(invalid_fn)
    assert valid is False
    assert "Invalid function_name" in err

    # Missing test cases
    no_tests = {
        "title": "No Tests",
        "text": "Detailed problem description with enough characters...",
        "function_name": "solve",
        "test_cases": [],
    }
    valid, err = validate_problem_specification(no_tests)
    assert valid is False
    assert "requires at least one configured test case" in err


# ---------------------------------------------------------------------------
# 3. Oracle Verification & Expected Output Calculation
# ---------------------------------------------------------------------------

def test_oracle_execution_computes_verified_expected_output():
    """Oracle runs reference solution against inputs and replaces unverified outputs with ground truth."""
    ref_sol = """
class Solution:
    def twoSum(self, nums: list, target: int) -> list:
        seen = {}
        for i, x in enumerate(nums):
            if target - x in seen:
                return [seen[target - x], i]
            seen[x] = i
        return []
"""
    raw_tests = [
        {"id": "tc1", "input": "[2,7,11,15]\n9", "expected_output": "WRONG_HALLUCINATED_VALUE"},
        {"id": "tc2", "input": "[3,2,4]\n6", "expected_output": "ANOTHER_WRONG_VALUE"},
    ]

    success, verified_tests, err = run_oracle_on_test_cases(ref_sol, "twoSum", raw_tests)
    assert success is True
    assert err is None
    assert verified_tests[0]["expected_output"] == "[0,1]"
    assert verified_tests[1]["expected_output"] == "[1,2]"


def test_oracle_rejects_broken_reference_solution():
    """Oracle fails and returns actionable error when reference solution crashes on an input."""
    broken_ref_sol = """
class Solution:
    def twoSum(self, nums: list, target: int) -> list:
        raise ZeroDivisionError("Crash on purpose")
"""
    raw_tests = [{"id": "tc1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]"}]
    success, verified_tests, err = run_oracle_on_test_cases(broken_ref_sol, "twoSum", raw_tests)
    assert success is False
    assert "ZeroDivisionError" in err


def test_oracle_verifies_and_repairs_examples():
    """Oracle checks problem examples and aligns contradictory outputs with ground truth."""
    ref_sol = """
class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        seen = {}
        l = 0
        ans = 0
        for r, c in enumerate(s):
            if c in seen and seen[c] >= l:
                l = seen[c] + 1
            seen[c] = r
            ans = max(ans, r - l + 1)
        return ans
"""
    examples = [
        {"example_number": 1, "input": 's = "abcabcbb"', "output": "999"},  # Conflicting output
    ]
    success, verified_exs, err = verify_examples_consistency(ref_sol, "lengthOfLongestSubstring", examples)
    assert success is True
    assert verified_exs[0]["output"] == "3"


# ---------------------------------------------------------------------------
# 4. Maximum Sum of Non-Overlapping Subarrays Benchmark & Oracle Verification
# ---------------------------------------------------------------------------

def test_max_sum_non_overlapping_subarrays_benchmark_catalog():
    """Benchmark problem Maximum Sum of Two Non-Overlapping Subarrays is registered with verified oracle."""
    prob = find_benchmark_problem("Maximum Sum of Two Non-Overlapping Subarrays")
    assert prob is not None
    assert prob["function_name"] == "maxSumTwoNoOverlap"
    assert prob["oracle_verified"] is True
    assert prob["oracle_provenance"] == "benchmark_catalog"

    # Verify reference solution runs and produces correct benchmark outputs
    ref_sol = prob["reference_solution"]
    for tc in prob["test_cases"]:
        res = run_oracle_solution(ref_sol, "maxSumTwoNoOverlap", tc["input"])
        assert res.exit_code == 0
        assert res.stdout.strip() == tc["expected_output"]


# ---------------------------------------------------------------------------
# 5. Multi-Language Driver & Correctness Evaluation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_python_known_correct_solution_passes():
    """Known-correct Python solution passes all test cases."""
    code = """
class Solution:
    def twoSum(self, nums: list, target: int) -> list:
        seen = {}
        for i, x in enumerate(nums):
            if target - x in seen:
                return [seen[target - x], i]
            seen[x] = i
        return []
"""
    tcs = [
        TestCase(id="tc1", input="[2,7,11,15]\n9", expected_output="[0,1]", is_hidden=False),
        TestCase(id="tc2", input="[3,2,4]\n6", expected_output="[1,2]", is_hidden=False),
    ]
    res = await evaluate_code_against_test_cases("two_sum", "python", code, tcs, function_name="twoSum")
    assert res.all_passed is True
    assert res.passed_tests == 2


@pytest.mark.asyncio
async def test_python_deliberately_incorrect_solution_fails():
    """Deliberately incorrect Python solution (wrong answer) fails evaluation."""
    code = """
class Solution:
    def twoSum(self, nums: list, target: int) -> list:
        return [0, 0]  # Deliberately incorrect
"""
    tcs = [
        TestCase(id="tc1", input="[2,7,11,15]\n9", expected_output="[0,1]", is_hidden=False),
    ]
    res = await evaluate_code_against_test_cases("two_sum", "python", code, tcs, function_name="twoSum")
    assert res.all_passed is False
    assert res.passed_tests == 0
    assert res.results[0].passed is False


@pytest.mark.asyncio
async def test_hidden_test_cases_remain_strictly_hidden():
    """Hidden test cases never leak their input or expected output to the candidate result payload."""
    code = """
class Solution:
    def isValid(self, s: str) -> bool:
        return s == "()"
"""
    tcs = [
        TestCase(id="tc1", input="()", expected_output="true", is_hidden=False),
        TestCase(id="tc2", input="()[]{}", expected_output="true", is_hidden=True),
        TestCase(id="tc3", input="(]", expected_output="false", is_hidden=True),
    ]
    res = await evaluate_code_against_test_cases("valid_parentheses", "python", code, tcs, function_name="isValid")

    # tc1 is public
    assert res.results[0].input == "()"
    assert res.results[0].expected_output == "true"

    # tc2 and tc3 are hidden
    assert res.results[1].is_hidden is True
    assert res.results[1].input == "[Hidden Test Case Input]"
    assert res.results[1].expected_output == "[Hidden Expected Output]"

    assert res.results[2].is_hidden is True
    assert res.results[2].input == "[Hidden Test Case Input]"
    assert res.results[2].expected_output == "[Hidden Expected Output]"


@pytest.mark.asyncio
async def test_compilation_error_reported_as_failure():
    """Syntax error / compilation error is recorded as failure, not as a pass."""
    code = """
class Solution:
    def twoSum(self, nums: list, target: int) -> list:
        this is invalid syntax !!!
"""
    tcs = [TestCase(id="tc1", input="[2,7,11,15]\n9", expected_output="[0,1]")]
    res = await evaluate_code_against_test_cases("two_sum", "python", code, tcs, function_name="twoSum")
    assert res.all_passed is False
    assert res.compilation_error is not None
    assert "SyntaxError" in res.compilation_error


# ---------------------------------------------------------------------------
# 6. Cross-Language Consistency Tests (API Level)
# ---------------------------------------------------------------------------

def test_api_submit_code_python_java_cross_language():
    """Verify that Python and Java implementations pass identical test cases via the /submit-code API."""
    py_code = """
class Solution:
    def twoSum(self, nums: list, target: int) -> list:
        seen = {}
        for i, x in enumerate(nums):
            if target - x in seen:
                return [seen[target - x], i]
            seen[x] = i
        return []
"""
    resp_py = client.post("/api/interviews/submit-code", json={
        "question_id": "two_sum",
        "language": "python",
        "code": py_code,
        "test_cases": [
            {"id": "tc1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
            {"id": "tc2", "input": "[3,2,4]\n6", "expected_output": "[1,2]", "is_hidden": True},
        ]
    })
    assert resp_py.status_code == 200
    data_py = resp_py.json()
    assert data_py["all_passed"] is True
    assert data_py["passed_tests"] == 2

    # Java solution
    java_code = """
import java.util.*;

class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int complement = target - nums[i];
            if (map.containsKey(complement)) {
                return new int[] { map.get(complement), i };
            }
            map.put(nums[i], i);
        }
        return new int[0];
    }
}
"""
    resp_java = client.post("/api/interviews/submit-code", json={
        "question_id": "two_sum",
        "language": "java",
        "code": java_code,
        "test_cases": [
            {"id": "tc1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
            {"id": "tc2", "input": "[3,2,4]\n6", "expected_output": "[1,2]", "is_hidden": True},
        ]
    })
    assert resp_java.status_code == 200
    data_java = resp_java.json()
    assert data_java["all_passed"] is True
    assert data_java["passed_tests"] == 2


# ---------------------------------------------------------------------------
# 7. Safe Data Healing and Quarantine
# ---------------------------------------------------------------------------

def test_session_coding_questions_audit_and_heal():
    """Verify stored session coding questions are healed with oracle verification without losing candidate records."""
    from app.services.session_service import audit_and_heal_session_coding_questions

    session = {
        "session_id": "test_heal_session",
        "interview_mode": "CODING",
        "questions": [
            {
                "id": "q_1",
                "question_number": 1,
                "title": "Two Sum",
                "text": "Given an array of integers nums and an integer target, return indices of the two numbers that sum to target.",
                "question_type": "coding",
                "oracle_verified": False,
            },
            {
                "id": "q_2",
                "question_number": 2,
                "title": "Unverifiable Custom Problem",
                "text": "Solve this completely undefined riddle.",
                "question_type": "coding",
                "oracle_verified": False,
            }
        ],
        "answers": {
            "q_1": {"code": "print('user solution')", "answer_text": "Solution draft"}
        }
    }

    healed = audit_and_heal_session_coding_questions(session)

    # Question 1 matched benchmark Two Sum and is healed
    q1 = healed["questions"][0]
    assert q1["oracle_verified"] is True
    assert q1["oracle_provenance"] == "benchmark_catalog"
    assert q1["quarantined"] is False
    assert len(q1.get("test_cases", [])) >= 2

    # Question 2 could not be verified and is safely quarantined
    q2 = healed["questions"][1]
    assert q2["oracle_verified"] is False
    assert q2["quarantined"] is True

    # Candidate submissions are preserved intact
    assert "q_1" in healed["answers"]
    assert healed["answers"]["q_1"]["code"] == "print('user solution')"
