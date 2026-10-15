"""
Regression tests for:
Recursion Coding Question Generation & Authoritative Reference Solution Verification.

Verifies:
1. Missing reference solution triggers generation and validation.
2. Malformed / invalid syntax reference solutions are caught with [stage: reference_solution_validation].
3. Valid recursive reference solutions pass AST recursion checks and oracle execution.
4. Incorrect reference solutions that crash on test inputs are quarantined with [stage: oracle_test_case_execution].
5. Non-recursive implementations submitted for topic 'Recursion' are rejected by AST recursion validation.
6. Strict topic adherence prevents substitution with unrelated problems (e.g. Two Sum).
7. End-to-end generation for Recursion produces a verified problem with an authoritative reference solution.
"""

import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException

from app.services.oracle_service import (
    check_ast_recursion,
    validate_reference_solution,
    clean_reference_solution_code,
    run_oracle_on_test_cases,
    verify_and_repair_coding_question,
)
from app.core.topic_validator import validate_question_topic
from app.schemas.interview import InterviewSetupRequest
from app.services.question_generator import generate_initial_adaptive_question


def test_ast_recursion_detection():
    # 1. Direct recursion
    direct_rec = """
class Solution:
    def fib(self, n: int) -> int:
        if n <= 1:
            return n
        return self.fib(n - 1) + self.fib(n - 2)
"""
    assert check_ast_recursion(direct_rec) is True

    # 2. Nested helper recursion (backtracking / dfs)
    nested_rec = """
class Solution:
    def subsets(self, nums):
        res = []
        def backtrack(start, path):
            res.append(path[:])
            for i in range(start, len(nums)):
                path.append(nums[i])
                backtrack(i + 1, path)
                path.pop()
        backtrack(0, [])
        return res
"""
    assert check_ast_recursion(nested_rec) is True

    # 3. Iterative code with no recursion
    iterative = """
class Solution:
    def twoSum(self, nums, target):
        seen = {}
        for i, n in enumerate(nums):
            diff = target - n
            if diff in seen:
                return [seen[diff], i]
            seen[n] = i
        return []
"""
    assert check_ast_recursion(iterative) is False


def test_clean_reference_solution_strips_markdown_and_preamble():
    raw_markdown = """```python
class Solution:
    def solve(self, n):
        return n
```"""
    cleaned = clean_reference_solution_code(raw_markdown)
    assert cleaned.startswith("class Solution:")
    assert "```" not in cleaned


def test_validate_reference_solution_catches_syntax_error():
    broken_code = """
class Solution:
    def broken(self, x)
        return x +
"""
    is_valid, err_reason, _ = validate_reference_solution(broken_code, "broken", topic="Recursion")
    assert is_valid is False
    assert "syntax error" in err_reason.lower()


def test_validate_reference_solution_catches_missing_method():
    code_wrong_method = """
class Solution:
    def wrongMethod(self, x: int) -> int:
        return x
"""
    is_valid, err_reason, _ = validate_reference_solution(code_wrong_method, "targetMethod", topic="Arrays")
    assert is_valid is False
    assert "targetMethod" in err_reason


def test_validate_reference_solution_rejects_non_recursive_code_for_recursion_topic():
    non_rec_code = """
class Solution:
    def climbStairs(self, n: int) -> int:
        a, b = 1, 1
        for _ in range(n):
            a, b = b, a + b
        return a
"""
    is_valid, err_reason, _ = validate_reference_solution(non_rec_code, "climbStairs", topic="Recursion")
    assert is_valid is False
    assert "requires genuine recursive problem decomposition" in err_reason or "does not use recursion" in err_reason


def test_validate_reference_solution_accepts_valid_recursive_code():
    valid_rec = """
class Solution:
    def climbStairs(self, n: int) -> int:
        memo = {}
        def helper(i):
            if i <= 1:
                return 1
            if i not in memo:
                memo[i] = helper(i - 1) + helper(i - 2)
            return memo[i]
        return helper(n)
"""
    is_valid, err_reason, cleaned = validate_reference_solution(valid_rec, "climbStairs", topic="Recursion")
    assert is_valid is True
    assert err_reason is None
    assert "class Solution:" in cleaned


def test_oracle_execution_failure_quarantines_question():
    crashing_solution = """
class Solution:
    def divide(self, a: int, b: int) -> int:
        return a // b
"""
    # Passing 0 as denominator causes ZeroDivisionError
    test_cases = [{"id": "tc_1", "input": "10\n0", "is_hidden": False}]
    success, _, oracle_err = run_oracle_on_test_cases(crashing_solution, "divide", test_cases)
    assert success is False
    assert "ZeroDivisionError" in oracle_err or "failed on test case" in oracle_err


@pytest.mark.asyncio
async def test_verify_and_repair_with_valid_recursive_solution():
    problem = {
        "id": "q_test",
        "title": "Generate Combinations",
        "text": "Given n and k, return all possible combinations of k numbers chosen from 1 to n using recursion.",
        "assessed_skill": "Recursion",
        "difficulty": "Medium",
        "function_name": "combine",
        "input_format": "n: int, k: int",
        "output_format": "List[List[int]]",
        "constraints": ["1 <= n <= 20", "1 <= k <= n"],
        "examples": [{"example_number": 1, "input": "4\n2", "output": "[[1,2],[1,3],[1,4],[2,3],[2,4],[3,4]]"}],
        "test_cases": [
            {"id": "tc_1", "input": "4\n2", "is_hidden": False},
            {"id": "tc_2", "input": "1\n1", "is_hidden": False},
        ],
        "reference_solution": """
class Solution:
    def combine(self, n: int, k: int):
        res = []
        def backtrack(start, comb):
            if len(comb) == k:
                res.append(comb[:])
                return
            for i in range(start, n + 1):
                comb.append(i)
                backtrack(i + 1, comb)
                comb.pop()
        backtrack(1, [])
        return res
""",
    }

    v_dict = await verify_and_repair_coding_question(problem)
    assert v_dict.get("oracle_verified") is True
    assert v_dict.get("quarantined") is False
    assert v_dict.get("validation_error") is None
    assert len(v_dict.get("test_cases")) >= 4  # Ensured test diversity


def test_strict_topic_adherence_rejects_two_sum_for_recursion():
    two_sum_prob = {
        "title": "Two Sum",
        "text": "Given an array of integers and a target, return indices of two numbers that add to target.",
        "assessed_skill": "Arrays & Hash Maps",
        "function_name": "twoSum",
        "test_cases": [{"input": "[2,7,11,15]\n9", "expected_output": "[0,1]"}],
    }
    is_valid, reason = validate_question_topic(two_sum_prob, ["Recursion"])
    assert is_valid is False
    assert "Recursion" in reason


@pytest.mark.asyncio
async def test_deterministic_recursion_initial_question_generation():
    """Deterministic regression test for initial recursion coding question generation & oracle verification."""
    setup = InterviewSetupRequest(
        role="Software Engineer",
        experience_level="Mid-level",
        difficulty="Medium",
        focus_areas="Recursion",
        interview_mode="CODING",
        question_count=3,
        duration_minutes=30,
    )

    mock_llm_json = json.dumps({
        "title": "Generate Combinations",
        "text": "Given n and k, return all possible combinations of k numbers chosen from 1 to n using recursion.",
        "assessed_skill": "Recursion",
        "difficulty": "Medium",
        "function_name": "combine",
        "input_format": "n: int, k: int",
        "output_format": "List[List[int]]",
        "constraints": ["1 <= n <= 20", "1 <= k <= n"],
        "examples": [{"example_number": 1, "input": "4\n2", "output": "[[1, 2], [1, 3], [1, 4], [2, 3], [2, 4], [3, 4]]"}],
        "test_cases": [
            {"id": "tc_1", "input": "4\n2", "is_hidden": False},
            {"id": "tc_2", "input": "1\n1", "is_hidden": False},
            {"id": "tc_3", "input": "3\n2", "is_hidden": True},
            {"id": "tc_4", "input": "2\n1", "is_hidden": True},
        ],
        "reference_solution": (
            "class Solution:\n"
            "    def combine(self, n: int, k: int):\n"
            "        res = []\n"
            "        def backtrack(start, comb):\n"
            "            if len(comb) == k:\n"
            "                res.append(comb[:])\n"
            "                return\n"
            "            for i in range(start, n + 1):\n"
            "                comb.append(i)\n"
            "                backtrack(i + 1, comb)\n"
            "                comb.pop()\n"
            "        backtrack(1, [])\n"
            "        return res\n"
        ),
    })

    with patch("app.services.question_generator.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = mock_llm_json
        questions = await generate_initial_adaptive_question(setup)

    assert len(questions) == 1
    q = questions[0]
    assert q.oracle_verified is True
    assert q.quarantined is False
    assert q.reference_solution is not None
    assert len(q.reference_solution.strip()) > 20
    assert q.question_type == "coding"
    assert q.assessed_skill.lower() == "recursion"
    # Ensure reference solution is genuinely recursive
    assert check_ast_recursion(q.reference_solution) is True
    # Ensure test cases have verified outputs from the oracle
    assert len(q.test_cases) >= 4
    for tc in q.test_cases:
        assert tc.get("expected_output") is not None
        assert str(tc.get("expected_output")).strip() != ""


@pytest.mark.asyncio
async def test_recursion_initial_question_generation_groq_failure_handling():
    """Verify that external Groq failure or rate limit returns actionable HTTP error without fake questions."""
    setup = InterviewSetupRequest(
        role="Software Engineer",
        experience_level="Mid-level",
        difficulty="Medium",
        focus_areas="Recursion",
        interview_mode="CODING",
        question_count=3,
        duration_minutes=30,
    )
    with patch(
        "app.services.question_generator.groq_manager.execute_chat_completion",
        new_callable=AsyncMock,
        side_effect=HTTPException(
            status_code=429,
            detail="Rate limit reached for model openai/gpt-oss-20b on tokens per day (TPD).",
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await generate_initial_adaptive_question(setup)
        assert exc_info.value.status_code == 429
        assert "Rate limit reached" in exc_info.value.detail


@pytest.mark.live_groq
@pytest.mark.asyncio
async def test_live_recursion_initial_question_generation():
    """
    Live integration test: requires active Groq API credentials and daily quota.
    Opt-in execution command: pytest -m live_groq
    """
    setup = InterviewSetupRequest(
        role="Software Engineer",
        experience_level="Mid-level",
        difficulty="Medium",
        focus_areas="Recursion",
        interview_mode="CODING",
        question_count=3,
        duration_minutes=30,
    )
    questions = await generate_initial_adaptive_question(setup)
    assert len(questions) == 1
    q = questions[0]
    assert q.oracle_verified is True
    assert q.quarantined is False
    assert q.reference_solution is not None
    assert len(q.reference_solution.strip()) > 20
    assert q.question_type == "coding"
    assert q.assessed_skill.lower() == "recursion"
    # Ensure reference solution is genuinely recursive
    assert check_ast_recursion(q.reference_solution) is True
    # Ensure test cases have verified outputs from the oracle
    assert len(q.test_cases) >= 4
    for tc in q.test_cases:
        assert tc.get("expected_output") is not None
        assert str(tc.get("expected_output")).strip() != ""
