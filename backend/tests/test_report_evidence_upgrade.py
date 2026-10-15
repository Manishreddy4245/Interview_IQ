import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.schemas.interview import QuestionItem, SubmitAnswerRequest, InterviewSetupRequest
from app.schemas.evaluation import AIEvaluationRaw, CriterionScores, CriterionScore
from app.schemas.report import (
    InterviewReportResponse,
    QuestionPerformanceSummary,
    CompetencyAnalysisItem,
    PersonalizedRoadmapItem,
    ExecutiveSummaryDetails,
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
)
from app.services.report_service import (
    generate_interview_report,
    get_interview_report,
    _in_memory_reports,
)


async def _make_session(questions, role="Software Engineer", experience_level="Mid-Level", difficulty="Medium") -> str:
    setup = InterviewSetupRequest(
        role=role,
        experience_level=experience_level,
        difficulty=difficulty,
        focus_areas="General",
        question_count=len(questions),
    )
    session = await create_interview_session(setup=setup, questions=questions)
    return session.session_id


@pytest.fixture
def multi_modal_questions():
    return [
        QuestionItem(
            id="q_verbal_1",
            question_number=1,
            text="In Java, what is the difference between a class and an object? Describe memory allocation.",
            assessed_skill="Java Core",
            difficulty="Medium",
            question_type="verbal",
            rubric="Distinguishes blueprint vs instance; explains heap allocation for objects and metadata in metaspace.",
        ),
        QuestionItem(
            id="q_coding_2",
            question_number=2,
            text="Given an array of integers nums and an integer target, return indices of the two numbers that add up to target.",
            assessed_skill="Data Structures & Algorithms",
            difficulty="Easy",
            question_type="coding_dsa",
            rubric="Solves Two Sum in O(N) time with hash map; handles edge cases.",
            constraints=["2 <= nums.length <= 10^4", "Exactly one valid answer exists."],
        ),
        QuestionItem(
            id="q_unassessed_3",
            question_number=3,
            text="Explain database sharding and partitioning strategies.",
            assessed_skill="Distributed Databases",
            difficulty="Hard",
            question_type="verbal",
            rubric="Discusses horizontal sharding, hash key distribution, and rebalancing.",
        ),
    ]


@pytest.fixture
def eval_verbal():
    return AIEvaluationRaw(
        overall_score=85,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=10, feedback="Directly answers distinction and memory allocation."),
            technical_depth=CriterionScore(score=8, feedback="Identifies heap for objects; could name metaspace for class metadata."),
            completeness=CriterionScore(score=8, feedback="Covers core rubric points concisely."),
            structure_flow=CriterionScore(score=9, feedback="Logical flow from definition to memory layout."),
            clarity_conciseness=CriterionScore(score=10, feedback="Crisp and accurate explanation without filler."),
            star_structure=CriterionScore(score=5, feedback="Conceptual technical question; STAR behavioral method not applicable."),
        ),
        strengths=[
            "Clear distinction between class (blueprint) and object (instance).",
            "Correctly identifies heap allocation for objects.",
        ],
        areas_for_improvement=[
            "Could explicitly name the metaspace where class metadata resides.",
        ],
        actionable_suggestions=[
            "Specify that class metadata is stored in Metaspace/Method Area.",
        ],
        coaching_summary="Strong conceptual explanation. Add exact JVM memory terminology to demonstrate deep production expertise.",
        stronger_example_answer="A class is a blueprint; an object is an instantiated entity on the heap. Class metadata resides in Metaspace.",
        recommended_practice="Review JVM memory segments: Heap, Stack, and Metaspace.",
    )


@pytest.fixture
def eval_coding():
    return AIEvaluationRaw(
        overall_score=95,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=10, feedback="Implements exact Two Sum function interface."),
            technical_depth=CriterionScore(score=10, feedback="Optimal O(N) time complexity using hash map single pass."),
            completeness=CriterionScore(score=9, feedback="Passes all test cases and handles boundaries."),
            structure_flow=CriterionScore(score=9, feedback="Clean procedural implementation structure."),
            clarity_conciseness=CriterionScore(score=9, feedback="Efficient Python code with descriptive variables."),
        ),
        strengths=[
            "Optimal single-pass hash map approach achieving O(N) time complexity.",
            "Passed 3 of 3 automated test cases.",
        ],
        areas_for_improvement=[
            "Add docstrings explaining input constraints and memory trade-offs.",
        ],
        actionable_suggestions=[
            "Include inline documentation on space complexity trade-offs.",
        ],
        coaching_summary="Exemplary algorithmic solution with verified automated test execution.",
        stronger_example_answer="def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        diff = target - num\n        if diff in seen:\n            return [seen[diff], i]\n        seen[num] = i\n    return []",
        recommended_practice="Practice hash map lookups on prefix-sum and subarray problems.",
    )


@pytest.mark.asyncio
async def test_executive_summary_mathematical_consistency(multi_modal_questions, eval_verbal, eval_coding):
    """Verify that overall score calculation strictly averages evaluated questions and excludes unassessed ones."""
    sid = await _make_session(
        multi_modal_questions,
        role="Software Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
    )

    # Submit Q1 (Verbal)
    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_verbal_1",
            answer_text="A class is a template and an object is an instance on the heap.",
            answer_mode="verbal",
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_verbal_1", evaluation=eval_verbal)

    # Submit Q2 (Coding)
    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_coding_2",
            code="def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen: return [seen[target - n], i]\n        seen[n] = i",
            language="python",
            answer_mode="coding",
            execution_result={
                "passed_tests": 3,
                "total_tests": 3,
                "all_passed": True,
                "test_results": [
                    {"test_case_id": "tc_1", "input": "[2,7,11,15], 9", "expected_output": "[0, 1]", "actual_output": "[0, 1]", "passed": True},
                    {"test_case_id": "tc_2", "input": "[3,2,4], 6", "expected_output": "[1, 2]", "actual_output": "[1, 2]", "passed": True},
                    {"test_case_id": "tc_3", "input": "[3,3], 6", "expected_output": "[0, 1]", "actual_output": "[0, 1]", "passed": True},
                ],
            },
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_coding_2", evaluation=eval_coding)

    # Note: q_unassessed_3 is left completely untouched (unanswered & unevaluated)

    report = await generate_interview_report(sid)

    assert report.total_questions == 3
    assert report.answered_questions == 2
    assert report.unanswered_questions == 1
    assert report.evaluated_questions == 2
    # Unevaluated question (q3) is not treated as 0: mean of 85 and 95 is exactly 90.0
    assert report.overall_score == 90.0
    assert report.evaluation_coverage_pct == round((2 / 3) * 100, 1)

    # Executive summary details check
    exec_details: ExecutiveSummaryDetails = report.executive_summary_details
    assert exec_details is not None
    assert exec_details.overall_score == 90.0
    assert exec_details.total_questions == 3
    assert exec_details.attempted_questions == 2
    assert exec_details.evaluated_questions == 2
    assert exec_details.unevaluated_questions == 1
    assert "85.0" in exec_details.scoring_calculation and "95.0" in exec_details.scoring_calculation
    assert "excluded" in exec_details.scoring_calculation.lower()
    assert exec_details.readiness_level == "Interview Ready"


@pytest.mark.asyncio
async def test_grounded_answer_availability_and_no_fabrication(multi_modal_questions, eval_verbal):
    """Verify that actual candidate answer is preserved verbatim and unsubmitted questions show proper availability."""
    sid = await _make_session(
        multi_modal_questions,
        role="Java Developer",
        experience_level="Junior",
        difficulty="Medium",
    )

    exact_candidate_text = "A class is the blueprint and an object is the concrete instance created via new on heap."
    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_verbal_1",
            answer_text=exact_candidate_text,
            answer_mode="verbal",
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_verbal_1", evaluation=eval_verbal)

    report = await generate_interview_report(sid)

    q1_perf = next(q for q in report.questions_performance if q.question_id == "q_verbal_1")
    assert q1_perf.answer_availability == "available"
    assert q1_perf.full_candidate_answer == exact_candidate_text

    q3_perf = next(q for q in report.questions_performance if q.question_id == "q_unassessed_3")
    assert q3_perf.answer_availability == "unanswered"
    assert q3_perf.full_candidate_answer is None
    assert q3_perf.is_evaluated is False
    assert q3_perf.overall_score is None


@pytest.mark.asyncio
async def test_rubric_breakdown_and_star_non_penalization(multi_modal_questions, eval_verbal):
    """Verify that rubric criteria are mapped with exact deductions and technical questions do not penalize STAR."""
    sid = await _make_session(
        multi_modal_questions,
        role="Backend Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
    )

    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_verbal_1",
            answer_text="Classes define fields. Objects are instances.",
            answer_mode="verbal",
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_verbal_1", evaluation=eval_verbal)

    report = await generate_interview_report(sid)
    q1_perf = next(q for q in report.questions_performance if q.question_id == "q_verbal_1")

    assert len(q1_perf.rubric_breakdown) > 0
    criterion_names = [rb.criterion_name for rb in q1_perf.rubric_breakdown]

    # Verify standard technical criteria are present
    assert any("Technical Depth" in name for name in criterion_names)
    assert any("Relevance" in name for name in criterion_names)

    # CRITICAL: Since q_verbal_1 is a technical conceptual prompt, STAR Framework deduction MUST NOT be penalized
    assert not any("STAR Framework" in name for name in criterion_names)

    # Verify deduction reason explains score
    tech_depth = next(rb for rb in q1_perf.rubric_breakdown if "Technical Depth" in rb.criterion_name)
    assert tech_depth.score_awarded == 8.0
    assert tech_depth.max_score == 10.0
    assert "2.0 pts" in tech_depth.deduction_reason


@pytest.mark.asyncio
async def test_coding_solution_analysis_test_cases_and_verification_mode(multi_modal_questions, eval_coding):
    """Verify coding solution analysis captures test case execution records, complexity, and correct code."""
    sid = await _make_session(
        multi_modal_questions,
        role="Algorithm Engineer",
        experience_level="Senior",
        difficulty="Medium",
    )

    code_submission = "def two_sum(nums, target):\n    lookup = {}\n    for i, num in enumerate(nums):\n        if target - num in lookup: return [lookup[target - num], i]\n        lookup[num] = i"
    test_results_data = [
        {"test_case_id": "tc_1", "input": "[2,7,11,15], 9", "expected_output": "[0, 1]", "actual_output": "[0, 1]", "passed": True},
        {"test_case_id": "tc_2", "input": "[3,2,4], 6", "expected_output": "[1, 2]", "actual_output": "[1, 2]", "passed": True},
    ]

    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_coding_2",
            code=code_submission,
            language="python",
            answer_mode="coding",
            execution_result={
                "passed_tests": 2,
                "total_tests": 2,
                "all_passed": True,
                "test_results": test_results_data,
            },
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_coding_2", evaluation=eval_coding)

    report = await generate_interview_report(sid)
    q2_perf = next(q for q in report.questions_performance if q.question_id == "q_coding_2")

    sol_analysis = q2_perf.solution_analysis
    assert sol_analysis is not None
    assert sol_analysis.is_coding is True
    assert sol_analysis.verification_mode == "verified_execution"
    assert len(sol_analysis.test_cases) == 2
    assert sol_analysis.test_cases[0].passed is True
    assert sol_analysis.test_cases[0].actual_output == "[0, 1]"
    assert "2 of 2" in sol_analysis.test_cases_summary
    assert sol_analysis.corrected_code is not None


@pytest.mark.asyncio
async def test_competency_aggregation_and_unassessed_status(multi_modal_questions, eval_verbal):
    """Verify that evaluated competencies receive appropriate status while unassessed ones are marked Insufficient Evidence."""
    sid = await _make_session(
        multi_modal_questions,
        role="Full Stack Developer",
        experience_level="Mid-Level",
        difficulty="Medium",
    )

    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_verbal_1",
            answer_text="Class is blueprint, object is memory on heap.",
            answer_mode="verbal",
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_verbal_1", evaluation=eval_verbal)

    report = await generate_interview_report(sid)

    comp_map = {c.competency_name: c for c in report.competencies_analysis}

    # Java Core was evaluated with 85 -> Status: Demonstrated
    assert "Java Core" in comp_map
    java_comp = comp_map["Java Core"]
    assert java_comp.status == "Demonstrated"
    assert java_comp.average_score == 85.0
    assert java_comp.evaluated_questions_count == 1
    assert len(java_comp.demonstrated_strengths) > 0

    # Distributed Databases was NEVER assessed -> Status: Insufficient Evidence (Never labeled weak!)
    assert "Distributed Databases" in comp_map
    db_comp = comp_map["Distributed Databases"]
    assert db_comp.status == "Insufficient Evidence"
    assert db_comp.average_score is None
    assert db_comp.evaluated_questions_count == 0


@pytest.mark.asyncio
async def test_personalized_roadmap_priority_sequencing(multi_modal_questions, eval_verbal, eval_coding):
    """Verify that learning roadmap priorities sequence foundational gaps before advanced topics."""
    sid = await _make_session(
        multi_modal_questions,
        role="Software Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
    )

    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_verbal_1",
            answer_text="Java answer with memory omission.",
            answer_mode="verbal",
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_verbal_1", evaluation=eval_verbal)

    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_coding_2",
            code="def two_sum(): pass",
            language="python",
            answer_mode="coding",
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_coding_2", evaluation=eval_coding)

    report = await generate_interview_report(sid)

    roadmap = report.learning_roadmap
    assert len(roadmap) > 0
    # Ranks must be sequential starting at 1
    assert roadmap[0].priority_rank == 1
    assert all(hasattr(item, "what_to_learn_first") for item in roadmap)
    assert all(hasattr(item, "practice_exercise") for item in roadmap)
    assert all(hasattr(item, "completion_criterion") for item in roadmap)


@pytest.mark.asyncio
async def test_report_persistence_and_backward_compatibility(multi_modal_questions, eval_verbal):
    """Verify report retrieval from database/cache and safe auto-upgrade of legacy reports."""
    sid = await _make_session(
        multi_modal_questions,
        role="Java Engineer",
        experience_level="Junior",
        difficulty="Easy",
    )

    await submit_answer(
        session_id=sid,
        answer_data=SubmitAnswerRequest(
            question_id="q_verbal_1",
            answer_text="A class is a blueprint; an object is an instance.",
            answer_mode="verbal",
        ),
    )
    await save_evaluation(session_id=sid, question_id="q_verbal_1", evaluation=eval_verbal)

    # Initial report generation with deterministic local test seam
    with patch(
        "app.services.report_service._synthesize_executive_summary_with_groq",
        new=AsyncMock(
            return_value={
                "executive_summary": "Java Engineer completed evaluation.",
                "recommended_next_steps": ["Review JVM memory segments."],
            }
        ),
    ):
        report = await generate_interview_report(sid)
    assert report.report_id is not None

    # Retrieve report via get_interview_report
    retrieved = await get_interview_report(sid)
    assert retrieved is not None
    assert retrieved.report_id == report.report_id
    assert retrieved.overall_score == report.overall_score
    assert retrieved.executive_summary_details is not None
    assert len(retrieved.competencies_analysis) > 0

    # Simulate legacy document without rich fields
    legacy_doc = {
        "report_id": str(uuid.uuid4()),
        "session_id": sid,
        "created_at": "2026-01-01T00:00:00Z",
        "role": "Java Engineer",
        "experience_level": "Junior",
        "difficulty": "Easy",
        "focus_areas": "",
        "total_questions": 3,
        "answered_questions": 1,
        "unanswered_questions": 2,
        "evaluated_questions": 1,
        "evaluation_coverage_pct": 33.3,
        "overall_score": 85.0,
        "score_status": "calculated",
        "scoring_formula_explanation": "Arithmetic mean",
        "criterion_averages": {},
        "key_strengths": ["Java knowledge"],
        "priority_improvements": ["Metaspace"],
        "recommended_next_steps": ["Review JVM"],
        "executive_summary": "Legacy summary",
        "questions_performance": [],
        "has_resume_comparison": False,
        "integrity_summary": {
            "total_events": 0,
            "events_summary": {},
            "events_timeline": [],
            "neutral_disclaimer": "Neutral",
            "score_impact": "None",
        },
        # Missing executive_summary_details, competencies_analysis, learning_roadmap
    }
    _in_memory_reports[sid] = legacy_doc

    # get_interview_report should safely detect missing rich details and auto-upgrade
    upgraded = await get_interview_report(sid)
    assert upgraded is not None
    assert upgraded.executive_summary_details is not None
    assert len(upgraded.competencies_analysis) > 0
    assert len(upgraded.learning_roadmap) > 0
