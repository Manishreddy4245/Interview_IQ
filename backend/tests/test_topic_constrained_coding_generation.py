"""
Regression tests for Issue 2:
Authoritative topic constraint enforcement for coding questions,
strict semantic validation, and rejection of unrelated fallbacks (e.g., Two Sum when Recursion is requested).
"""

import pytest
from fastapi import HTTPException

from app.core.topic_validator import (
    parse_focus_area_topics,
    validate_question_topic,
    select_next_topic_from_focus_areas,
    is_topic_in_allowed_set,
)
from app.core.problem_catalog import BENCHMARK_PROBLEMS
from app.schemas.interview import InterviewSetupRequest, QuestionItem


def test_parse_focus_area_topics():
    topics = parse_focus_area_topics("Recursion")
    assert topics == ["Recursion"]

    topics_multi = parse_focus_area_topics("Recursion, Dynamic Programming; Trees")
    assert "Recursion" in topics_multi
    assert "Dynamic Programming" in topics_multi
    assert "Trees" in topics_multi


def test_two_sum_strictly_rejected_for_recursion():
    two_sum = BENCHMARK_PROBLEMS["two_sum"]
    is_valid, reason = validate_question_topic(two_sum, ["Recursion"])
    assert is_valid is False
    assert "Recursion" in reason
    assert "Two Sum" in reason or "Array" in reason


def test_recursion_problem_accepted_for_recursion():
    recursion_problem = {
        "title": "Subsets and Combinations Generator",
        "text": "Given an integer array nums of unique elements, return all possible subsets (the power set) using recursive backtracking.",
        "assessed_skill": "Recursion & Backtracking",
        "function_name": "subsets",
        "test_cases": [{"input": "[1,2,3]", "expected_output": "[[],[1],[2],[3],[1,2],[1,3],[2,3],[1,2,3]]"}]
    }
    is_valid, reason = validate_question_topic(recursion_problem, ["Recursion"])
    assert is_valid is True
    assert reason is None


def test_text_mentioning_recursion_as_keyword_does_not_mask_two_sum():
    fake_two_sum_with_mention = {
        "title": "Two Sum (Mentions Recursion)",
        "text": "Given an array of integers nums and an integer target, return indices of the two numbers that sum to target. Even though recursion could theoretically be mentioned here, the problem is hash map lookup.",
        "assessed_skill": "Arrays & Hash Maps",
        "function_name": "twoSum",
        "test_cases": [{"input": "[2,7,11,15]\n9", "expected_output": "[0,1]"}]
    }
    is_valid, reason = validate_question_topic(fake_two_sum_with_mention, ["Recursion"])
    assert is_valid is False
    assert "Two Sum" in reason or "anti-pattern" in reason or "Array" in reason


def test_multiple_topics_allowed_but_unrelated_rejected():
    allowed = ["Recursion", "Dynamic Programming"]
    dp_problem = {
        "title": "Climbing Stairs",
        "text": "You are climbing a staircase. It takes n steps to reach the top. Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top? Solve using dynamic programming or memoization.",
        "assessed_skill": "Dynamic Programming",
        "function_name": "climbStairs",
        "test_cases": [{"input": "3", "expected_output": "3"}]
    }
    is_valid_dp, _ = validate_question_topic(dp_problem, allowed)
    assert is_valid_dp is True

    # SQL problem should be rejected under [Recursion, Dynamic Programming]
    sql_problem = BENCHMARK_PROBLEMS["sql_department_salaries"]
    is_valid_sql, sql_reason = validate_question_topic(sql_problem, allowed)
    assert is_valid_sql is False


def test_select_next_topic_ensures_coverage():
    allowed = ["Recursion", "Trees", "Dynamic Programming"]
    t1 = select_next_topic_from_focus_areas(allowed, [])
    assert t1 == "Recursion"

    t2 = select_next_topic_from_focus_areas(allowed, ["Recursion"])
    assert t2 == "Trees"

    t3 = select_next_topic_from_focus_areas(allowed, ["Recursion", "Trees"])
    assert t3 == "Dynamic Programming"


@pytest.mark.asyncio
async def test_adaptive_fallback_refuses_unrelated_benchmark_for_recursion():
    from app.services.adaptation_service import generate_time_aware_fallback_question
    with pytest.raises(HTTPException) as exc_info:
        generate_time_aware_fallback_question(
            skill="Recursion",
            difficulty="Medium",
            time_band="focused",
            next_q_id="q_2",
            next_q_number=2,
            existing_questions=[],
            role="Software Engineer",
            job_description=None,
            session_mode="CODING",
        )
    assert exc_info.value.status_code == 502
    assert "Never substituting an unrelated problem" in exc_info.value.detail
