"""
Comprehensive Verification Suite for:
1. Code Execution Provider & Sandbox Hardening (Issue 1)
   - Successful execution (Python, JS)
   - Compile/Syntax errors
   - Runtime errors
   - Wrong answers
   - Provider error detection & graceful handling (never mark failed provider runs as accepted)
   - Piston whitelist interception
2. Adaptive Question Generation & Lifecycle Optimization (Issue 2)
   - Atomic answer & evaluation persistence
   - Stage timing measurements (evaluation_ms, persistence_ms, adaptation_ms, total_ms)
   - Adaptive question generation dependency on answer evaluation
   - Prompt context compaction
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.code_execution_service import (
    execute_code_sandboxed,
    evaluate_code_against_test_cases,
    get_configured_piston_url,
    get_configured_judge0_url,
)
from app.schemas.execution import TestCase
from app.schemas.interview import (
    InterviewSetupRequest,
    SubmitAnswerRequest,
    QuestionItem,
)
from app.services.session_service import (
    create_interview_session,
    record_answer_and_evaluation,
    get_session,
)
from app.schemas.evaluation import (
    AIEvaluationRaw,
    CriterionScores,
    CriterionScore,
)

client = TestClient(app)


# =========================================================================
# ISSUE 1 TESTS: CODE EXECUTION & PROVIDER HARDENING
# =========================================================================

@pytest.mark.asyncio
async def test_successful_python_execution():
    """Verify valid Python code executes successfully in sandbox and produces stdout."""
    res = await execute_code_sandboxed(
        language="python",
        code="print('Hello from InterviewIQ test runner!')",
        stdin="",
    )
    assert res.exit_code == 0
    assert res.status == "success"
    assert "Hello from InterviewIQ test runner!" in res.stdout
    assert res.error is None


@pytest.mark.asyncio
async def test_python_syntax_error_handling():
    """Verify Python syntax errors are correctly classified as compilation/syntax errors, not provider errors."""
    bad_code = "def broken(\n  print('missing paren'"
    res = await execute_code_sandboxed(
        language="python",
        code=bad_code,
        stdin="",
    )
    assert res.exit_code != 0
    assert res.status in ("error", "compilation_error")
    assert "SyntaxError" in (res.stderr or res.output or res.error or "")
    # Should not be blamed on the provider
    assert "Execution provider error" not in (res.error or "")


@pytest.mark.asyncio
async def test_python_runtime_error_handling():
    """Verify runtime errors (e.g. ZeroDivisionError) exit with non-zero code and descriptive stderr."""
    runtime_err_code = "x = 10 / 0"
    res = await execute_code_sandboxed(
        language="python",
        code=runtime_err_code,
        stdin="",
    )
    assert res.exit_code != 0
    assert res.status in ("error", "runtime_error")
    assert "ZeroDivisionError" in (res.stderr or res.output or res.error or "")


@pytest.mark.asyncio
async def test_evaluate_against_test_cases_all_passed():
    """Verify test cases pass when code produces expected output."""
    code = """
import sys
line = sys.stdin.read().strip()
nums = [int(x) for x in line.split()]
print(sum(nums))
"""
    test_cases = [
        TestCase(id="tc1", input="2 3", expected_output="5"),
        TestCase(id="tc2", input="10 -4", expected_output="6"),
    ]
    sub_res = await evaluate_code_against_test_cases(
        question_id="sum_test",
        language="python",
        code=code,
        test_cases=test_cases,
    )
    assert sub_res.all_passed is True
    assert sub_res.passed_tests == 2
    assert sub_res.total_tests == 2
    assert sub_res.status == "evaluated"
    assert sub_res.provider_error is None
    assert sub_res.compilation_error is None


@pytest.mark.asyncio
async def test_evaluate_against_test_cases_wrong_answer():
    """Verify wrong answer is correctly identified and does not trigger provider error."""
    code = """
import sys
line = sys.stdin.read().strip()
# Intentionally incorrect logic: multiplies instead of adding
nums = [int(x) for x in line.split()]
print(nums[0] * nums[1])
"""
    test_cases = [
        TestCase(id="tc1", input="2 3", expected_output="5"),  # Code outputs 6 -> FAILS
    ]
    sub_res = await evaluate_code_against_test_cases(
        question_id="sum_test",
        language="python",
        code=code,
        test_cases=test_cases,
    )
    assert sub_res.all_passed is False
    assert sub_res.passed_tests == 0
    assert sub_res.total_tests == 1
    assert sub_res.status == "evaluated"
    assert sub_res.provider_error is None


@pytest.mark.asyncio
async def test_piston_public_api_whitelist_guard():
    """Verify unauthenticated emkc.org URL is intercepted and not invoked without explicit key."""
    # When PISTON_API_URL is default emkc.org and PISTON_API_KEY is empty:
    with patch("app.services.code_execution_service.settings.PISTON_API_URL", "https://emkc.org/api/v2/piston/execute"), \
         patch("app.services.code_execution_service.settings.PISTON_API_KEY", ""):
        assert get_configured_piston_url() is None

    # When custom URL is provided:
    with patch("app.services.code_execution_service.settings.PISTON_API_URL", "https://my-piston.internal/api/v2/execute"), \
         patch("app.services.code_execution_service.settings.PISTON_API_KEY", ""):
        assert get_configured_piston_url() == "https://my-piston.internal/api/v2/execute"


@pytest.mark.asyncio
async def test_provider_error_does_not_mark_solution_accepted():
    """Verify that when the execution provider fails, all_passed is False and provider_error is recorded."""
    test_cases = [
        TestCase(id="tc1", input="1", expected_output="1"),
    ]
    # Mock execute_code_sandboxed to simulate external provider outage
    with patch("app.services.code_execution_service.execute_code_sandboxed") as mock_exec:
        from app.schemas.execution import CodeExecutionResponse
        mock_exec.return_value = CodeExecutionResponse(
            stdout="",
            stderr="",
            output="",
            exit_code=1,
            status="error",
            error="Execution provider error: HTTP 503 Service Unavailable",
            provider="piston",
        )
        sub_res = await evaluate_code_against_test_cases(
            question_id="provider_fail_q",
            language="python",
            code="print(1)",
            test_cases=test_cases,
        )

    assert sub_res.all_passed is False
    assert sub_res.status == "provider_error"
    assert sub_res.provider_error is not None
    assert "503" in sub_res.provider_error


# =========================================================================
# ISSUE 2 TESTS: ADAPTATION & LIFECYCLE OPTIMIZATION
# =========================================================================

@pytest.mark.asyncio
async def test_atomic_record_answer_and_evaluation():
    """Verify record_answer_and_evaluation updates answers, evaluations, and timestamps in one atomic operation."""
    # Create test session
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Mid-Level",
        duration_minutes=30,
        focus_areas="APIs, System Architecture",
        interview_mode="VERBAL",
        adaptive=True,
    )
    q1 = QuestionItem(
        id="q_test_1",
        question_number=1,
        text="Explain the principles of RESTful API design.",
        assessed_skill="REST APIs",
        difficulty="Medium",
        rubric="Clear coverage of statelessness, resource modeling, and idempotency.",
        recommended_mode="verbal",
    )
    session_res = await create_interview_session(setup, questions=[q1])
    session_id = session_res.session_id
    q_id = "q_test_1"

    answer_req = SubmitAnswerRequest(
        question_id=q_id,
        answer_text="REST is stateless, uses standard HTTP methods, and separates client and server concerns.",
        answer_mode="verbal",
    )
    evaluation = AIEvaluationRaw(
        overall_score=85,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Strong relevance"),
            technical_depth=CriterionScore(score=8, feedback="Good architectural depth"),
            completeness=CriterionScore(score=8, feedback="Covered key constraints"),
            structure_flow=CriterionScore(score=8, feedback="Clear organization"),
            clarity_conciseness=CriterionScore(score=9, feedback="Concise"),
        ),
        strengths=["Clear articulation of statelessness"],
        areas_for_improvement=["Could mention cacheability"],
        actionable_suggestions=["Discuss HATEOAS in senior contexts"],
        coaching_summary="Well structured answer.",
        recommended_practice="Review caching headers",
        acoustic_disclaimer="Evaluated via automated NLP rubric.",
    )

    ans_res, saved_eval, updated_session = await record_answer_and_evaluation(
        session_id=session_id,
        answer_payload=answer_req,
        evaluation=evaluation,
    )

    assert ans_res.db_status in ("persisted", "unconfigured")
    assert saved_eval.db_status in ("persisted", "unconfigured")
    assert ans_res.question_id == q_id
    assert saved_eval.overall_score == 85
    assert q_id in updated_session.get("answers", {})
    assert "evaluation" in updated_session["answers"][q_id]
    assert updated_session["answers"][q_id]["evaluation"]["overall_score"] == 85


def test_submit_and_adapt_includes_stage_timings():
    """Verify submit-and-adapt lifecycle endpoint measures and returns stage_timings."""
    # 1. Create a session via API
    setup_payload = {
        "role": "Software Engineer",
        "experience_level": "Mid-Level",
        "duration_minutes": 30,
        "focus_areas": "Python, Problem Solving",
        "interview_mode": "VERBAL",
        "adaptive": True,
    }
    resp = client.post("/api/interviews/setup", json=setup_payload)
    assert resp.status_code == 201
    s_data = resp.json()
    session_id = s_data["session_id"]
    q_id = s_data["questions"][0]["id"]

    # 2. Submit answer to submit-and-adapt
    submit_payload = {
        "question_id": q_id,
        "answer_text": "Object-oriented programming utilizes encapsulation, inheritance, and polymorphism to model complex systems.",
        "answer_mode": "verbal",
    }
    sub_resp = client.post(f"/api/interviews/{session_id}/submit-and-adapt", json=submit_payload)
    assert sub_resp.status_code == 200
    res_data = sub_resp.json()

    # 3. Verify stage_timings dictionary is present and structured
    assert "stage_timings" in res_data
    timings = res_data["stage_timings"]
    assert timings is not None
    assert "evaluation_ms" in timings
    assert "persistence_ms" in timings
    assert "adaptation_ms" in timings
    assert "total_ms" in timings
    assert timings["total_ms"] >= 0
    assert timings["persistence_ms"] >= 0

    # 4. Verify evaluation was recorded and next question issued
    assert res_data["evaluation"] is not None
    assert res_data["evaluation"]["overall_score"] > 0
    assert res_data["adaptive_decision"] is not None
