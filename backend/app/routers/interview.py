import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.config import settings
from app.core.database import db_manager
from app.core.security import (
    get_optional_user,
    require_role,
    ROLE_CANDIDATE,
    ROLE_REVIEWER,
    ROLE_ADMIN,
)
from app.schemas.interview import (
    InterviewSetupRequest,
    InterviewSessionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    SubmitAndAdaptResponse,
    QuestionItem,
    NextQuestionRequest,
    NextQuestionResponse,
    SessionCompetencyState,
    SaveDraftRequest,
    SaveDraftResponse,
    SessionDraftsResponse,
)
from app.schemas.evaluation import (
    EvaluateAnswerRequest,
    AnswerEvaluationResponse,
    AIEvaluationRaw,
    CriterionScores,
    CriterionScore,
)
from app.schemas.integrity import (
    IntegrityEventCreate,
    IntegrityEventRecord,
    IntegrityEventsResponse,
    HumanReviewAuditRequest,
    HumanReviewAuditEntry,
    CandidateExplanationRequest,
    CandidateExplanationEntry,
    ReviewerDecisionRequest,
    ReviewerDecisionEntry,
)
from app.schemas.execution import (
    CodeExecutionRequest,
    CodeExecutionResponse,
    SubmitCodeSolutionRequest,
    CodeSubmissionResult,
    SQLExecutionRequest,
    SQLExecutionResponse,
    SubmitSQLSolutionRequest,
    SQLSubmissionResult,
    TestCase,
)
from app.services.code_execution_service import (
    get_supported_languages,
    execute_code_sandboxed,
    evaluate_code_against_test_cases,
)
from app.services.sql_execution_service import (
    get_fixture_metadata,
    execute_sql_in_memory,
    evaluate_sql_solution,
)
from app.schemas.report import InterviewReportResponse, AvailableReportItem
from app.services.question_generator import (
    generate_adaptive_questions,
    generate_initial_adaptive_question,
)
from app.services.adaptation_service import (
    generate_next_adaptive_question,
    compute_session_competency_state,
)
from app.services.evaluation_service import (
    evaluate_candidate_answer,
    evaluate_system_design_answer,
)
from app.services.report_service import (
    generate_interview_report,
    get_interview_report,
    _in_memory_reports,
)
from app.core.problem_catalog import (
    normalize_and_classify_question,
    find_benchmark_problem,
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    record_answer_and_evaluation,
    record_integrity_event,
    get_integrity_events,
    record_human_review,
    get_human_reviews,
    record_candidate_explanation,
    get_candidate_explanations,
    record_reviewer_decision,
    get_session,
    complete_session,
    compute_session_time_status,
    save_question_draft,
    get_session_drafts,
    _in_memory_sessions,
)

logger = logging.getLogger("interviewiq.interview_router")

router = APIRouter(prefix="/api/interviews", tags=["Interview Workflow"])


@router.post(
    "/setup",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Interview Session and Generate Questions",
    description=(
        "Validates interview parameters, uses Groq AI to generate structured adaptive questions, "
        "and persists the session to MongoDB Atlas (if configured) or active memory."
    ),
)
async def setup_interview(
    setup: InterviewSetupRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> InterviewSessionResponse:
    """Set up interview and generate questions tailored to the candidate profile."""
    owner_id = current_user.get("user_id") if current_user else None
    if getattr(setup, "adaptive", False):
        questions = await generate_initial_adaptive_question(setup)
        session = await create_interview_session(
            setup,
            questions,
            is_adaptive=True,
            target_question_count=setup.question_count,
            owner_id=owner_id,
        )
    else:
        questions = await generate_adaptive_questions(setup)
        session = await create_interview_session(
            setup,
            questions,
            is_adaptive=False,
            target_question_count=setup.question_count,
            owner_id=owner_id,
        )
    return session


@router.post(
    "/{session_id}/next-question",
    response_model=NextQuestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Dynamically Generate Next-Best Question",
    description=(
        "Evaluates previous answer evidence, remaining session time, and competency gaps "
        "to dynamically formulate the next best interview question with adapted difficulty."
    ),
)
async def get_next_adaptive_question(
    session_id: str,
    payload: Optional[NextQuestionRequest] = None,
) -> NextQuestionResponse:
    """Dynamically select and generate the next best question based on candidate evidence and remaining time."""
    client_hint = payload.client_remaining_seconds if payload else None
    return await generate_next_adaptive_question(session_id, client_remaining_seconds=client_hint)


@router.get(
    "/{session_id}/competencies",
    response_model=SessionCompetencyState,
    summary="Get Session Competency Tracking State",
    description="Retrieves current competency evidence status and adapted difficulty level for the session.",
)
async def get_session_competencies(session_id: str) -> SessionCompetencyState:
    """Retrieve live competency tracking state for the active interview session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )
    return compute_session_competency_state(session)


@router.post(
    "/{session_id}/answers",
    response_model=SubmitAnswerResponse,
    summary="Submit Answer for a Question",
    description="Submits the candidate's answer for a specific question within the active session.",
)
@router.post(
    "/{session_id}/answer",
    response_model=SubmitAnswerResponse,
    include_in_schema=False,
)
async def submit_question_answer(
    session_id: str,
    answer_payload: SubmitAnswerRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> SubmitAnswerResponse:
    """Submit and store an answer for an interview question."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    session_owner = session.get("owner_id")
    if session_owner:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to submit answers for this private session.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if current_user.get("role") == ROLE_CANDIDATE and current_user.get("user_id") != session_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot submit answers for another candidate's interview session.",
            )

    if session.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview session '{session_id}' has already been completed.",
        )

    # Check if session time has expired
    time_status = compute_session_time_status(session)
    if time_status["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session time has expired. Cannot submit additional answers.",
        )

    question_ids = [q["id"] for q in session.get("questions", [])]
    if answer_payload.question_id not in question_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Question '{answer_payload.question_id}' was never issued to this session. "
                f"Skipping forward to unissued questions is rejected. Issued question IDs: {question_ids}"
            ),
        )

    return await submit_answer(session_id, answer_payload)



async def route_and_evaluate_answer(
    question_item: QuestionItem,
    answer_payload: SubmitAnswerRequest,
    role: str = "Candidate",
    experience_level: str = "Mid-Level",
    session_mode: Optional[str] = None,
) -> tuple[AIEvaluationRaw, str, Optional[Dict[str, Any]]]:
    """
    Authoritative mode-aware evaluation routing:
    - Coding submissions execute against test cases in isolated sandbox.
    - SQL submissions execute against relational schema in SQLite sandbox.
    - System design submissions evaluate against architectural criteria.
    - Verbal submissions evaluate against communication & STAR rubric.
    Never sends source code to verbal evaluator or treats verbal response as code.
    Returns (evaluation, active_mode, execution_result).
    """
    s_mode = (session_mode or "").strip().upper() if session_mode else None
    mode = (answer_payload.answer_mode or "").strip().lower()

    # Strict session mode validation
    if s_mode == "VERBAL":
        if mode == "coding" or (answer_payload.code and not (answer_payload.answer_text and answer_payload.answer_text.strip())):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incompatible submission: Source code submissions are strictly forbidden in a Verbal Interview session. Please submit a verbal response.",
            )
    elif s_mode == "CODING":
        if mode == "verbal" or (not (answer_payload.code and answer_payload.code.strip()) and answer_payload.answer_text):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incompatible submission: Verbal text submissions are strictly forbidden in a Coding Interview session. Please submit executable source code.",
            )

    if not mode:
        if s_mode == "CODING":
            mode = "coding"
        elif s_mode == "VERBAL":
            mode = "verbal"
        elif answer_payload.answer_text and answer_payload.answer_text.strip():
            # Legacy un-moded submission with textual answer payload
            mode = "verbal"
        elif answer_payload.code and answer_payload.code.strip():
            mode = "coding"
        elif answer_payload.sql_query and answer_payload.sql_query.strip():
            mode = "sql"
        elif question_item.question_type == "system_design":
            mode = "system_design"
        else:
            mode = question_item.recommended_mode or question_item.question_type or "verbal"

    available_modes = question_item.available_modes or [question_item.question_type or "verbal"]
    if mode not in available_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Incompatible answer mode: '{mode}' is not compatible with question '{question_item.id}' "
                f"({question_item.question_type}). Compatible modes: {available_modes}"
            ),
        )

    if mode == "coding":
        code_str = (answer_payload.code or "").strip()
        if not code_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source code is required when submitting in Coding Mode.",
            )

        test_cases: List[TestCase] = []
        raw_cases = question_item.test_cases or []
        for idx, rc in enumerate(raw_cases, 1):
            if isinstance(rc, dict):
                tc_data = dict(rc)
                if not tc_data.get("id"):
                    tc_data["id"] = f"tc_{idx}"
                if "expected_output" not in tc_data and "output" in tc_data:
                    tc_data["expected_output"] = str(tc_data["output"])
                test_cases.append(TestCase(**tc_data))
            elif isinstance(rc, TestCase):
                test_cases.append(rc)

        qid = (question_item.id or "").lower()
        qtext = (question_item.text or "").lower()
        fn_name = question_item.function_name
        comparison_policy = getattr(question_item, "comparison_policy", None) or "strict_structural"
        float_tolerance = getattr(question_item, "float_tolerance", None) or 1e-5

        bm = find_benchmark_problem(qtext, question_item.title, q_id=question_item.id)
        if bm:
            if not fn_name:
                fn_name = bm.get("function_name")
            if not test_cases:
                test_cases = [TestCase(**tc) for tc in bm.get("test_cases", [])]
            elif any(not str(getattr(tc, "expected_output", "")).strip() for tc in test_cases):
                if bm.get("test_cases"):
                    test_cases = [TestCase(**tc) for tc in bm["test_cases"]]
            comparison_policy = bm.get("comparison_policy") or comparison_policy
            float_tolerance = bm.get("float_tolerance") or float_tolerance

        if not fn_name and code_str:
            import re
            m = re.search(r"(?:def|function)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", code_str)
            if m:
                detected_fn = m.group(1)
                if detected_fn not in ("solve", "main", "__init__"):
                    fn_name = detected_fn

        code_exec = await evaluate_code_against_test_cases(
            question_id=question_item.id,
            language=answer_payload.language or "python",
            code=code_str,
            test_cases=test_cases,
            function_name=fn_name,
            comparison_policy=comparison_policy,
            float_tolerance=float_tolerance,
        )

        exec_dict = code_exec.model_dump()
        total = code_exec.total_tests
        passed = code_exec.passed_tests
        pass_ratio = (passed / total) if total > 0 else 0.0

        # Rubric Calibration with Distinct Multi-Dimensional Scoring:
        # Dimension 1: Execution Correctness (Weight 70%, max 70.0 pts)
        # Dimension 2: Code Quality & Parameter Contracts (Weight 15%, max 15.0 pts)
        # Dimension 3: Algorithmic Efficiency & Complexity (Weight 15%, max 15.0 pts)
        if code_exec.provider_error:
            correctness_pts = 0.0
            quality_pts = 5.0
            complexity_pts = 5.0
            overall_score = 10
        elif code_exec.compilation_error:
            correctness_pts = 0.0
            quality_pts = 5.0
            complexity_pts = 5.0
            overall_score = 15
        elif total > 0:
            correctness_pts = 70.0 * pass_ratio
            if code_exec.all_passed:
                quality_pts = 13.0
                complexity_pts = 12.0
                overall_score = int(round(correctness_pts + quality_pts + complexity_pts)) # 95
            elif passed > 0:
                quality_pts = 11.0
                complexity_pts = 9.0
                overall_score = int(round(correctness_pts + quality_pts + complexity_pts)) # e.g. 55 for 50%, 72 for 75%
            else:
                # 0 test cases passed
                quality_pts = 10.0
                complexity_pts = 9.0
                overall_score = 19
        else:
            correctness_pts = 50.0
            quality_pts = 13.0
            complexity_pts = 12.0
            overall_score = 75

        overall_score = max(10, min(100, overall_score))
        depth_score = max(1, min(10, int(round((correctness_pts + complexity_pts) / 8.5))))
        comp_score = max(1, min(10, int(round((passed / total * 10) if total > 0 else (overall_score / 10)))))
        struct_score = 8 if not (code_exec.compilation_error or code_exec.provider_error) else 3
        clarity_score = 8 if not (code_exec.compilation_error or code_exec.provider_error) else 4

        strengths = [
            f"Submitted solution in {code_exec.language} passed {passed} of {total} test cases."
            if total > 0 and not code_exec.provider_error else f"Compiled and ran {code_exec.language} solution."
        ]
        if code_exec.all_passed:
            strengths.append(f"Execution Correctness ({int(round(correctness_pts))}/70 pts): Verified correctness across all {total} functional and boundary test cases.")
            strengths.append(f"Code Quality ({int(round(quality_pts))}/15 pts): Modular procedural implementation adhering to parameter contracts.")
            strengths.append(f"Algorithmic Complexity ({int(round(complexity_pts))}/15 pts): Executed within allotted time and resource constraints.")

        improvements = []
        if code_exec.provider_error:
            improvements.append(f"Code execution provider error: {code_exec.provider_error[:250]}")
        elif code_exec.compilation_error:
            improvements.append(f"Compilation/Runtime error: {code_exec.compilation_error[:250]}")
        elif not code_exec.all_passed and total > 0:
            improvements.append(f"Execution Correctness ({int(round(correctness_pts))}/70 pts): Failed {total - passed} of {total} test cases. Review boundary conditions and output formatting.")
        else:
            improvements.append("Consider theoretical space-time tradeoffs and potential asymptotic micro-optimizations.")

        relevance_score = 9 if not (code_exec.compilation_error or code_exec.provider_error) else 4
        if code_exec.provider_error:
            depth_feedback = f"Execution blocked by provider: {code_exec.provider_error[:120]}"
            comp_feedback = "Unable to verify test coverage due to execution provider error."
            coaching_summary = f"Code execution blocked by provider: {code_exec.provider_error[:120]}"
        else:
            depth_feedback = f"Execution verification: {passed}/{total} tests passed ({int(round(correctness_pts))}/70 pts correctness)."
            comp_feedback = f"Test coverage verification achieved {int(round(pass_ratio * 100)) if total > 0 else overall_score}% pass rate."
            coaching_summary = f"Coding evaluation: {passed}/{total} tests passed ({overall_score}/100). Focus on test-driven verification."

        evaluation = AIEvaluationRaw(
            overall_score=overall_score,
            criterion_scores=CriterionScores(
                relevance=CriterionScore(score=relevance_score, feedback="Solution directly implements the required algorithmic function."),
                technical_depth=CriterionScore(score=depth_score, feedback=depth_feedback),
                completeness=CriterionScore(score=comp_score, feedback=comp_feedback),
                structure_flow=CriterionScore(score=struct_score, feedback="Clean procedural implementation structure adhering to function signature."),
                clarity_conciseness=CriterionScore(score=clarity_score, feedback="Direct algorithm adhering to parameter contracts."),
            ),
            strengths=strengths,
            areas_for_improvement=improvements,
            actionable_suggestions=[
                "Test edge cases locally before submission (e.g. empty inputs, duplicates, extreme values).",
                "Analyze theoretical time and space complexity."
            ],
            coaching_summary=coaching_summary,
            recommended_practice=f"Practice {question_item.assessed_skill} problems on sandboxed algorithmic runners.",
            acoustic_disclaimer="Evaluated via automated sandbox execution and test-case verification.",
        )
        return evaluation, mode, exec_dict

    elif mode == "sql":
        query_str = (answer_payload.sql_query or "").strip()
        if not query_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SQL query is required when submitting in SQL Mode.",
            )

        fixture_key = question_item.sql_fixture or "employees_departments"
        expected_query = question_item.expected_sql_query
        sql_exec = evaluate_sql_solution(
            candidate_query=query_str,
            expected_query=expected_query,
            fixture_key=fixture_key,
        )

        exec_dict = sql_exec.model_dump()

        if sql_exec.is_correct:
            overall_score = 95
            strengths = ["SQL query executed successfully and matched benchmark result set columns and rows."]
            improvements = ["Consider indexing or query execution plan optimization for production tables."]
        elif sql_exec.error:
            overall_score = 25
            strengths = ["SQL query formulated against schema."]
            improvements = [f"SQL syntax or execution error: {sql_exec.error}"]
        else:
            overall_score = 55
            strengths = ["SQL query executed without syntax errors."]
            improvements = [f"Result set mismatch: query returned {sql_exec.row_count} rows differing from expected output."]

        depth_score = max(1, min(10, int(overall_score / 10)))

        evaluation = AIEvaluationRaw(
            overall_score=overall_score,
            criterion_scores=CriterionScores(
                relevance=CriterionScore(score=9, feedback="Query targets the relational schema tables and filtering criteria."),
                technical_depth=CriterionScore(score=depth_score, feedback=f"SQL execution accuracy: {'Correct' if sql_exec.is_correct else 'Mismatched'}."),
                completeness=CriterionScore(score=depth_score, feedback="Result set column and row verification completed."),
                structure_flow=CriterionScore(score=8, feedback="Standard SQL clause structure (SELECT, FROM, JOIN, GROUP BY)."),
                clarity_conciseness=CriterionScore(score=8, feedback="Query projection and predicate structure."),
            ),
            strengths=strengths,
            areas_for_improvement=improvements,
            actionable_suggestions=[
                "Verify JOIN conditions and aggregation functions against sample rows.",
                "Check NULL handling and filtering clauses."
            ],
            coaching_summary=f"SQL evaluation: {'Verified correct' if sql_exec.is_correct else 'Needs query adjustment'} ({overall_score}/100).",
            recommended_practice="Practice relational queries with GROUP BY, HAVING, and subqueries.",
            acoustic_disclaimer="Evaluated via sandboxed relational database execution.",
        )
        return evaluation, mode, exec_dict

    elif mode == "system_design":
        text_str = (answer_payload.answer_text or "").strip()
        if not text_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer text is required when submitting in System Design Mode.",
            )

        evaluation = await evaluate_system_design_answer(
            question=question_item,
            answer_text=text_str,
            role=role,
            experience_level=experience_level,
        )
        return evaluation, mode, None

    else:  # mode == "verbal"
        text_str = (answer_payload.answer_text or "").strip()
        if not text_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer text is required when submitting in Verbal Mode.",
            )

        evaluation = await evaluate_candidate_answer(
            question=question_item,
            answer_text=text_str,
            role=role,
            experience_level=experience_level,
        )
        return evaluation, mode, None


@router.post(
    "/{session_id}/questions/{question_id}/evaluate",
    response_model=AnswerEvaluationResponse,
    summary="Evaluate Candidate Answer for Specific Question",
    description=(
        "Evaluates the candidate's answer for a specific question against appropriate rubrics or sandbox execution. "
        "Returns multi-dimensional criterion scores, strengths, areas for improvement, and actionable coaching."
    ),
)
async def evaluate_question_answer(
    session_id: str,
    question_id: str,
    payload: Optional[EvaluateAnswerRequest] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> AnswerEvaluationResponse:
    """Evaluate candidate answer and provide communication coaching."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    session_owner = session.get("owner_id")
    if session_owner:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to evaluate answers for this private session.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if current_user.get("role") == ROLE_CANDIDATE and current_user.get("user_id") != session_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot evaluate answers for another candidate's interview session.",
            )

    if session.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview session '{session_id}' has already been completed.",
        )

    if session.get("is_unreliable_mode") or session.get("interview_mode") == "AMBIGUOUS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session mode is ambiguous or unreliable due to inconsistent question history. Please restart a new Coding or Verbal interview session.",
        )

    # Find the question
    matching_q = None
    for q in session.get("questions", []):
        if q["id"] == question_id:
            matching_q = q
            break

    if not matching_q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question '{question_id}' not found in session '{session_id}'.",
        )

    saved_answer = session.get("answers", {}).get(question_id, {})
    has_payload = payload and (
        (payload.answer_text is not None and bool(payload.answer_text.strip()))
        or (payload.code is not None and bool(payload.code.strip()))
        or (payload.sql_query is not None and bool(payload.sql_query.strip()))
        or (payload.answer_mode is not None and bool(payload.answer_mode.strip()))
    )

    s_mode = session.get("interview_mode")
    if has_payload:
        target_mode = (
            payload.answer_mode
            or saved_answer.get("answer_mode")
            or matching_q.get("recommended_mode")
            or ("coding" if matching_q.get("question_type") == "coding" else None)
            or ("coding" if s_mode == "CODING" else None)
            or "verbal"
        )
        resolved_code = payload.code or saved_answer.get("code")
        if not resolved_code and target_mode == "coding":
            drafts = session.get("drafts", {}).get(question_id, {})
            lang = payload.language or saved_answer.get("language") or "python"
            resolved_code = drafts.get(lang) or (list(drafts.values())[0] if drafts else None)

        ans_req = SubmitAnswerRequest(
            question_id=question_id,
            answer_text=(payload.answer_text.strip() if payload.answer_text else saved_answer.get("answer_text", "")),
            code=resolved_code,
            language=payload.language or saved_answer.get("language") or "python",
            sql_query=payload.sql_query or saved_answer.get("sql_query"),
            answer_mode=target_mode,
        )
        await submit_answer(session_id, ans_req)
    else:
        if not saved_answer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No answer has been submitted for question '{question_id}'. "
                    "Please submit an answer before requesting evaluation."
                ),
            )
        resolved_mode = (
            saved_answer.get("answer_mode")
            or matching_q.get("recommended_mode")
            or ("coding" if matching_q.get("question_type") == "coding" else None)
            or ("coding" if s_mode == "CODING" else None)
            or "verbal"
        )
        resolved_code = saved_answer.get("code")
        if not resolved_code and resolved_mode == "coding":
            drafts = session.get("drafts", {}).get(question_id, {})
            lang = saved_answer.get("language") or "python"
            resolved_code = drafts.get(lang) or (list(drafts.values())[0] if drafts else None)

        ans_req = SubmitAnswerRequest(
            question_id=question_id,
            answer_text=saved_answer.get("answer_text") or "",
            code=resolved_code,
            language=saved_answer.get("language") or "python",
            sql_query=saved_answer.get("sql_query"),
            answer_mode=resolved_mode,
        )

    s_mode = session.get("interview_mode")
    question_item = QuestionItem.model_validate(normalize_and_classify_question(matching_q, session_mode=s_mode))
    role = session.get("role", "Candidate")
    experience_level = session.get("experience_level", "Mid-Level")

    evaluation, mode, exec_res = await route_and_evaluate_answer(
        question_item=question_item,
        answer_payload=ans_req,
        role=role,
        experience_level=experience_level,
        session_mode=s_mode,
    )

    if exec_res:
        ans_req.execution_result = exec_res
        await submit_answer(session_id, ans_req)

    return await save_evaluation(session_id, question_id, evaluation)


@router.put(
    "/{session_id}/questions/{question_id}/draft",
    response_model=SaveDraftResponse,
    summary="Autosave Candidate Code or Query Draft",
    description="Autosaves candidate code or query draft with out-of-order write protection and per-language draft isolation.",
)
async def autosave_question_draft(
    session_id: str,
    question_id: str,
    draft_payload: SaveDraftRequest,
) -> SaveDraftResponse:
    """Autosave candidate code or SQL draft for a question and language."""
    return await save_question_draft(session_id, question_id, draft_payload)


@router.get(
    "/{session_id}/drafts",
    response_model=SessionDraftsResponse,
    summary="Get All Saved Question Drafts for Session",
    description="Returns all autosaved code and query drafts across questions and languages for the interview session.",
)
async def get_all_session_drafts(session_id: str) -> SessionDraftsResponse:
    """Retrieve all saved drafts for an active interview session."""
    drafts = await get_session_drafts(session_id)
    return SessionDraftsResponse(session_id=session_id, drafts=drafts)


@router.post(
    "/{session_id}/submit-and-adapt",
    response_model=SubmitAndAdaptResponse,
    summary="Submit Answer, Evaluate Evidence, and Dynamically Adapt Next Question",
    description=(
        "Atomic transition executing the complete sequential adaptive lifecycle: "
        "1. Validates and records answer for active question in chosen mode; "
        "2. Evaluates answer using mode-appropriate evaluator (sandbox code execution, SQL sandbox, architecture rubric, or verbal); "
        "3. Updates session competency state; "
        "4. Dynamically adapts difficulty and generates next question if interview is not complete."
    ),
)
async def submit_and_adapt_lifecycle(
    session_id: str,
    answer_payload: SubmitAnswerRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> SubmitAndAdaptResponse:
    """Execute complete sequential adaptive step: submit answer -> evaluate -> adapt next question."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    session_owner = session.get("owner_id")
    if session_owner:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to submit answers for this private session.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if current_user.get("role") == ROLE_CANDIDATE and current_user.get("user_id") != session_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot submit answers for another candidate's interview session.",
            )

    if session.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview session '{session_id}' has already been completed.",
        )

    if session.get("is_unreliable_mode") or session.get("interview_mode") == "AMBIGUOUS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session mode is ambiguous or unreliable due to inconsistent question history. Please restart a new Coding or Verbal interview session.",
        )

    time_status = compute_session_time_status(session)
    if time_status["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session time has expired. Cannot submit additional answers.",
        )

    # Validate active question in sequential lifecycle
    active_q = session.get("active_question_id") or (
        session["questions"][-1]["id"] if session.get("questions") else None
    )
    if active_q and answer_payload.question_id != active_q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot submit answer for '{answer_payload.question_id}'. "
                f"The currently active question is '{active_q}'. "
                "Skipping forward or submitting out of order is not allowed."
            ),
        )

    # Locate question item for evaluation
    matching_q = None
    for q in session.get("questions", []):
        if q["id"] == answer_payload.question_id:
            matching_q = q
            break

    if not matching_q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question '{answer_payload.question_id}' not found in session '{session_id}'.",
        )

    s_mode = session.get("interview_mode")
    question_item = QuestionItem.model_validate(normalize_and_classify_question(matching_q, session_mode=s_mode))
    role = session.get("role", "Candidate")
    experience_level = session.get("experience_level", "Mid-Level")

    t_start = time.perf_counter()

    # Evaluate answer through mode-appropriate pipeline
    t_eval_0 = time.perf_counter()
    evaluation, active_mode, exec_res = await route_and_evaluate_answer(
        question_item=question_item,
        answer_payload=answer_payload,
        role=role,
        experience_level=experience_level,
        session_mode=s_mode,
    )
    t_eval_1 = time.perf_counter()
    eval_ms = round((t_eval_1 - t_eval_0) * 1000, 2)

    answer_payload.answer_mode = active_mode
    if exec_res:
        answer_payload.execution_result = exec_res

    # Record answer and evaluation atomically in a single operation, keeping in-memory session fresh
    t_save_0 = time.perf_counter()
    ans_res, saved_eval, updated_session = await record_answer_and_evaluation(
        session_id=session_id,
        answer_payload=answer_payload,
        evaluation=evaluation,
        current_session=session,
    )
    t_save_1 = time.perf_counter()
    persistence_ms = round((t_save_1 - t_save_0) * 1000, 2)

    competency_state = compute_session_competency_state(updated_session)

    # Check if target question count reached or session complete
    target_count = updated_session.get("target_question_count", 3)
    questions_count = len(updated_session.get("questions", []))
    is_last = (questions_count >= target_count) or time_status["is_expired"]

    next_question: Optional[QuestionItem] = None
    next_active_id = active_q
    next_res = None
    adapt_ms = 0.0

    if not is_last and updated_session.get("is_adaptive"):
        # Adapt and formulate the next question based on evidence, reusing updated_session
        t_adapt_0 = time.perf_counter()
        next_res = await generate_next_adaptive_question(
            session_id,
            current_session=updated_session,
            client_remaining_seconds=time_status["effective_remaining_seconds"],
        )
        t_adapt_1 = time.perf_counter()
        adapt_ms = round((t_adapt_1 - t_adapt_0) * 1000, 2)

        if hasattr(next_res, "question"):
            next_question = next_res.question
            next_active_id = next_res.active_question_id or (next_res.question.id if next_res.question else None)
            competency_state = getattr(next_res, "competency_state", competency_state)
            is_last = getattr(next_res, "is_last_question", is_last)
            q_num = getattr(next_res, "question_number", questions_count + 1)
        else:
            next_question = next_res
            next_active_id = getattr(next_res, "id", None)
            q_num = getattr(next_res, "question_number", questions_count + 1)
        msg = f"Answer evaluated in {active_mode.upper()} mode. Question {q_num} adapted and issued."
    else:
        msg = f"Answer evaluated in {active_mode.upper()} mode. Target interview questions completed."

    t_end = time.perf_counter()
    total_ms = round((t_end - t_start) * 1000, 2)
    stage_timings = {
        "evaluation_ms": eval_ms,
        "persistence_ms": persistence_ms,
        "adaptation_ms": adapt_ms,
        "total_ms": total_ms,
    }
    logger.info(
        "[Adaptive Lifecycle Timing] session=%s q=%s mode=%s: eval=%.1fms, persistence=%.1fms, adaptation=%.1fms, total=%.1fms",
        session_id,
        answer_payload.question_id,
        active_mode,
        eval_ms,
        persistence_ms,
        adapt_ms,
        total_ms,
    )

    # Compute top-level persistence status reflecting the full lifecycle:
    # Evaluation persistence + session update / next question persistence
    if next_res is not None:
        next_saved = getattr(next_res, "saved_to_db", False)
        next_status = getattr(next_res, "db_status", "unconfigured")
        next_msg = getattr(next_res, "db_message", None)
        if saved_eval.saved_to_db and next_saved and ans_res.saved_to_db:
            overall_saved_to_db = True
            overall_db_status = "persisted"
            overall_db_msg = "Evaluation and next adaptive question successfully persisted to MongoDB Atlas."
        else:
            overall_saved_to_db = False
            if not saved_eval.saved_to_db:
                overall_db_status = saved_eval.db_status
                overall_db_msg = saved_eval.db_message
            elif not next_saved:
                overall_db_status = next_status
                overall_db_msg = next_msg or "Adaptive question could not be persisted to MongoDB Atlas."
            else:
                overall_db_status = ans_res.db_status
                overall_db_msg = ans_res.message
    else:
        if saved_eval.saved_to_db and ans_res.saved_to_db:
            overall_saved_to_db = True
            overall_db_status = "persisted"
            overall_db_msg = "Evaluation successfully persisted to MongoDB Atlas."
        else:
            overall_saved_to_db = False
            overall_db_status = saved_eval.db_status if not saved_eval.saved_to_db else ans_res.db_status
            overall_db_msg = saved_eval.db_message if not saved_eval.saved_to_db else ans_res.message

    adaptive_dec = None
    if next_res is not None and hasattr(next_res, "adaptive_decision"):
        adaptive_dec = next_res.adaptive_decision
    if not adaptive_dec:
        from app.services.adaptation_service import compute_adaptive_decision
        adaptive_dec = compute_adaptive_decision(updated_session)

    return SubmitAndAdaptResponse(
        session_id=session_id,
        question_id=answer_payload.question_id,
        answer_mode=active_mode,
        evaluation=saved_eval.model_dump(),
        next_question=next_question,
        active_question_id=next_active_id,
        is_last_question=is_last,
        competency_state=competency_state,
        time_remaining_seconds=time_status["effective_remaining_seconds"],
        saved_to_db=overall_saved_to_db,
        db_status=overall_db_status,
        db_message=overall_db_msg,
        adaptive_decision=adaptive_dec,
        stage_timings=stage_timings,
        message=msg,
    )


@router.post(
    "/{session_id}/integrity-events",
    response_model=IntegrityEventRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record Browser or Device Integrity Event",
    description=(
        "Records observable session events such as visibility changes (tab hidden/visible), "
        "media permissions, or practice timer state. Factual and neutral."
    ),
)
async def log_integrity_event(
    session_id: str,
    event_payload: IntegrityEventCreate,
) -> IntegrityEventRecord:
    """Record an observable browser presence or media event."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    if session.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview session '{session_id}' has already been completed.",
        )

    if event_payload.question_id:
        question_ids = [q["id"] for q in session.get("questions", [])]
        if question_ids and event_payload.question_id not in question_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Question '{event_payload.question_id}' does not belong to session '{session_id}'. "
                    f"Valid question IDs: {question_ids}"
                ),
            )

    return await record_integrity_event(session_id, event_payload)


@router.get(
    "/{session_id}/integrity-events",
    response_model=IntegrityEventsResponse,
    summary="Get Session Integrity Timeline",
    description="Retrieves chronological timeline of recorded neutral integrity events for the session.",
)
async def get_session_integrity_timeline(session_id: str) -> IntegrityEventsResponse:
    """Retrieve integrity timeline for an interview session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    return await get_integrity_events(session_id)


@router.post(
    "/{session_id}/integrity-review",
    response_model=HumanReviewAuditEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Record Human Review Note for Integrity Telemetry",
    description=(
        "Records an auditable contextual review note submitted by a human reviewer. "
        "Preserved separately from automated capability scores. Identity is documented as self-declared. "
        "Permitted on active and completed interview sessions."
    ),
)
async def add_integrity_human_review(
    session_id: str,
    review_payload: HumanReviewAuditRequest,
) -> HumanReviewAuditEntry:
    """Record an auditable review note by a human reviewer."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    return await record_human_review(session_id, review_payload)


@router.get(
    "/{session_id}/integrity-review",
    response_model=list[HumanReviewAuditEntry],
    summary="Get Session Human Review Audit Trail",
    description="Retrieves chronological audit trail of human review notes for this session.",
)
async def get_session_human_reviews(session_id: str) -> list[HumanReviewAuditEntry]:
    """Retrieve all human review audit entries for a session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    return await get_human_reviews(session_id)


@router.post(
    "/{session_id}/integrity-explanations",
    response_model=CandidateExplanationEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Record Candidate Contextual Explanation or Dispute for Integrity Telemetry",
    description=(
        "Records an auditable contextual explanation or dispute note submitted by a candidate. "
        "Can be associated with a specific event_id or session-level timeline. "
        "Preserved separately from automated capability scores. Candidate identity is documented as unverified. "
        "Permitted on active and completed interview sessions."
    ),
)
async def add_candidate_explanation(
    session_id: str,
    explanation_payload: CandidateExplanationRequest,
) -> CandidateExplanationEntry:
    """Record a contextual explanation or dispute submitted by the candidate."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    if explanation_payload.event_id:
        existing_event_ids = [
            ev.get("event_id") if isinstance(ev, dict) else getattr(ev, "event_id", None)
            for ev in session.get("integrity_events", [])
        ]
        if explanation_payload.event_id not in existing_event_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Integrity event '{explanation_payload.event_id}' does not belong to session '{session_id}'."
                ),
            )

    return await record_candidate_explanation(session_id, explanation_payload)


@router.get(
    "/{session_id}/integrity-explanations",
    response_model=list[CandidateExplanationEntry],
    summary="Get Session Candidate Explanations",
    description="Retrieves chronological audit trail of candidate explanations for this session.",
)
async def get_session_candidate_explanations(session_id: str) -> list[CandidateExplanationEntry]:
    """Retrieve all candidate explanations for a session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    return await get_candidate_explanations(session_id)


@router.post(
    "/{session_id}/integrity-explanations/{explanation_id}/decision",
    response_model=CandidateExplanationEntry,
    status_code=status.HTTP_200_OK,
    summary="Record Reviewer Decision for Candidate Explanation",
    description=(
        "Records an append-only reviewer determination or outcome on a candidate explanation. "
        "Preserves original candidate explanation verbatim. Reviewer attribution is documented as self-declared. "
        "Permitted on active and completed interview sessions."
    ),
)
async def record_candidate_explanation_decision(
    session_id: str,
    explanation_id: str,
    decision_payload: ReviewerDecisionRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> CandidateExplanationEntry:
    """Record an auditable reviewer decision on a candidate explanation."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    if current_user and current_user.get("role") == ROLE_CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: role 'candidate' lacks permission for this action. Authorized roles: reviewer, admin.",
        )

    if current_user and current_user.get("name"):
        decision_payload.reviewer_name = current_user["name"]

    return await record_reviewer_decision(session_id, explanation_id, decision_payload)


@router.get(
    "/available-reports",
    response_model=List[AvailableReportItem],
    summary="List Interview Sessions and Reports Available to User",
    description="Lists interview sessions and reports accessible to the caller, strictly enforcing RBAC ownership.",
)
async def list_available_reports(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> List[AvailableReportItem]:
    """
    Retrieve list of interview sessions and reports accessible to the authenticated user.
    Preserves RBAC: candidates only see their own sessions or unowned records;
    reviewers and admins see all sessions.
    """
    user_id = current_user.get("user_id") if current_user else None
    user_role = current_user.get("role") if current_user else None
    is_candidate = (user_role == ROLE_CANDIDATE)

    reports_map: Dict[str, Dict[str, Any]] = {}
    sessions_list: List[Dict[str, Any]] = []

    # 1. Gather from MongoDB Atlas if configured
    persisted_session_ids = set()
    if settings.is_mongodb_configured:
        try:
            if db_manager._db is None or db_manager.client is None:
                db_manager.connect()
            db = db_manager.get_database()

            raw_reports = await db["interview_reports"].find({}).sort("created_at", -1).to_list(500)
            for r in raw_reports:
                sid = r.get("session_id")
                if sid:
                    reports_map[sid] = r

            raw_sessions = await db["interview_sessions"].find({}).sort("created_at", -1).to_list(500)
            for s in raw_sessions:
                sid = s.get("session_id")
                if sid:
                    persisted_session_ids.add(sid)
            sessions_list.extend(raw_sessions)
        except Exception as exc:
            logger.warning("Error querying MongoDB for available reports: %s", type(exc).__name__)

    # 2. Merge in-memory store (fallback when MongoDB is unavailable or session was memory-only)
    for sid, r in _in_memory_reports.items():
        if sid not in reports_map:
            reports_map[sid] = r
    for sid, s in _in_memory_sessions.items():
        if not any(existing.get("session_id") == sid for existing in sessions_list):
            sessions_list.append(s)

    # 3. If there are reports whose session_id was not in sessions_list, synthesize session entry
    known_session_ids = {s.get("session_id") for s in sessions_list}
    for sid, r in reports_map.items():
        if sid not in known_session_ids:
            sessions_list.append({
                "session_id": sid,
                "role": r.get("role", "Candidate"),
                "experience_level": r.get("experience_level"),
                "difficulty": r.get("difficulty"),
                "interview_mode": r.get("interview_mode"),
                "created_at": r.get("created_at"),
                "status": "completed",
                "owner_id": r.get("owner_id"),
                "resume_analysis_id": r.get("associated_analysis_id"),
            })
            known_session_ids.add(sid)

    # 4. Filter strictly by RBAC candidate ownership
    items: List[AvailableReportItem] = []
    for s in sessions_list:
        owner = s.get("owner_id")

        if is_candidate:
            if owner and owner != user_id:
                continue
        elif not current_user:
            if owner:
                continue

        sid = s.get("session_id")
        rep = reports_map.get(sid)

        created_dt = s.get("created_at") or (rep.get("created_at") if rep else None)
        if isinstance(created_dt, str):
            try:
                created_dt = datetime.fromisoformat(created_dt)
            except Exception:
                created_dt = None

        report_id = rep.get("report_id") if rep else None
        overall_score = rep.get("overall_score") if rep else None
        resume_analysis_id = s.get("resume_analysis_id") or (rep.get("associated_analysis_id") if rep else None)

        s_status = s.get("status") or ("completed" if rep else "in_progress")
        if rep:
            report_status = "Report Ready"
        elif s_status == "completed":
            report_status = "Completed"
        else:
            report_status = "In Progress"

        mode = s.get("interview_mode") or (rep.get("interview_mode") if rep else None)
        if not mode:
            qs = s.get("questions", [])
            if any(q.get("question_type") == "coding" or q.get("response_mode") == "coding_ide" or q.get("function_name") for q in qs):
                mode = "CODING"
            elif qs:
                mode = "VERBAL"
            else:
                mode = "VERBAL"

        is_persisted = (sid in persisted_session_ids) or bool(s.get("saved_to_db", False))

        items.append(AvailableReportItem(
            session_id=sid,
            report_id=report_id,
            resume_analysis_id=resume_analysis_id,
            role=s.get("role") or (rep.get("role") if rep else "Candidate"),
            experience_level=s.get("experience_level") or (rep.get("experience_level") if rep else None),
            difficulty=s.get("difficulty") or (rep.get("difficulty") if rep else None),
            status=s_status,
            report_status=report_status,
            overall_score=overall_score,
            created_at=created_dt,
            owner_id=owner,
            interview_mode=mode,
            is_persisted=is_persisted,
        ))

    def sort_key(item: AvailableReportItem):
        if item.created_at:
            dt = item.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (0, dt)
        return (1, datetime.min.replace(tzinfo=timezone.utc))

    items.sort(key=sort_key, reverse=True)
    return items


@router.get(
    "/languages",
    summary="Get Supported Code Execution Languages",
    description="Returns list of languages genuinely supported by the sandbox execution runner with templates.",
)
async def get_execution_languages():
    return {"languages": get_supported_languages()}


@router.post(
    "/execute-code",
    response_model=CodeExecutionResponse,
    summary="Run Code in Isolated Sandbox",
    description="Executes candidate code with optional custom standard input in an isolated sandbox.",
)
async def run_code(payload: CodeExecutionRequest) -> CodeExecutionResponse:
    function_name = payload.function_name
    if not function_name and payload.session_id and payload.question_id:
        session = await get_session(payload.session_id)
        if session:
            for q in session.get("questions", []):
                if q.get("id") == payload.question_id:
                    function_name = q.get("function_name")
                    break

    if not function_name and payload.question_id:
        qid = payload.question_id.lower()
        if "two_sum" in qid:
            function_name = "twoSum"
        elif "parenthes" in qid:
            function_name = "isValid"
        elif "longest_sub" in qid or "substring" in qid:
            function_name = "lengthOfLongestSubstring"

    return await execute_code_sandboxed(
        language=payload.language,
        code=payload.code,
        stdin=payload.stdin or "",
        function_name=function_name,
    )


@router.post(
    "/submit-code",
    response_model=CodeSubmissionResult,
    summary="Evaluate Code against Test Cases",
    description="Evaluates candidate code against question test cases in an isolated sandbox.",
)
async def submit_code(
    payload: SubmitCodeSolutionRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> CodeSubmissionResult:
    # Attempt to retrieve question test cases and function name from payload or active session
    test_cases: List[TestCase] = []
    function_name: Optional[str] = None

    comparison_policy = payload.comparison_policy or "strict_structural"
    float_tolerance = payload.float_tolerance or 1e-5

    if payload.session_id:
        session = await get_session(payload.session_id)
        if session:
            for q in session.get("questions", []):
                if q.get("id") == payload.question_id:
                    function_name = q.get("function_name")
                    comparison_policy = q.get("comparison_policy") or comparison_policy
                    float_tolerance = q.get("float_tolerance") or float_tolerance
                    if not payload.test_cases:
                        raw_cases = q.get("test_cases") or []
                        for rc in raw_cases:
                            if isinstance(rc, dict):
                                test_cases.append(TestCase(**rc))
                            elif isinstance(rc, TestCase):
                                test_cases.append(rc)
                    break

    if payload.test_cases:
        test_cases = list(payload.test_cases)

    # Authoritative benchmark lookup from problem catalog
    if not test_cases:
        from app.core.problem_catalog import find_benchmark_problem
        benchmark = find_benchmark_problem(payload.question_id or "", q_id=payload.question_id)
        if benchmark:
            if not function_name:
                function_name = benchmark.get("function_name")
            comparison_policy = benchmark.get("comparison_policy") or comparison_policy
            raw_cases = benchmark.get("test_cases") or []
            for rc in raw_cases:
                test_cases.append(TestCase(**rc))

    return await evaluate_code_against_test_cases(
        question_id=payload.question_id,
        language=payload.language,
        code=payload.code,
        test_cases=test_cases,
        function_name=function_name,
        comparison_policy=comparison_policy,
        float_tolerance=float_tolerance,
    )


@router.get(
    "/sql-schema/{fixture_key}",
    summary="Get SQL Sandbox Schema and Sample Data",
    description="Retrieves table definitions, column types, and sample rows for the requested SQL fixture.",
)
async def get_sql_schema(fixture_key: str):
    return get_fixture_metadata(fixture_key)


@router.post(
    "/execute-sql",
    response_model=SQLExecutionResponse,
    summary="Run SQL Query in Isolated Sandbox",
    description="Executes a candidate SQL query inside an ephemeral in-memory SQLite sandbox.",
)
async def run_sql(payload: SQLExecutionRequest) -> SQLExecutionResponse:
    fixture_key = payload.question_id or "employees_departments"
    return execute_sql_in_memory(
        query=payload.query,
        fixture_key=fixture_key,
    )


@router.post(
    "/submit-sql",
    response_model=SQLSubmissionResult,
    summary="Evaluate SQL Query against Benchmark",
    description="Evaluates candidate SQL query results against benchmark query in the isolated sandbox.",
)
async def submit_sql(
    payload: SubmitSQLSolutionRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> SQLSubmissionResult:
    fixture_key = payload.fixture_key or payload.question_id or "employees_departments"
    expected_query = payload.expected_query
    if payload.session_id:
        session = await get_session(payload.session_id)
        if session:
            for q in session.get("questions", []):
                if q.get("id") == payload.question_id:
                    if q.get("sql_fixture"):
                        fixture_key = q.get("sql_fixture")
                    if q.get("expected_sql_query"):
                        expected_query = q.get("expected_sql_query")
                    break

    return evaluate_sql_solution(
        candidate_query=payload.query,
        expected_query=expected_query,
        fixture_key=fixture_key,
    )


@router.get(
    "/{session_id}",
    summary="Get Interview Session Details",
    description="Retrieve an active or persisted interview session by ID.",
)
async def get_interview_session(
    session_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Retrieve full session data including questions, submitted answers, and evaluations."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )
    session_owner = session.get("owner_id")
    if session_owner:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view this private interview session.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if current_user.get("role") == ROLE_CANDIDATE and session_owner != current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot view another candidate's private interview session.",
            )
    if "questions" in session:
        session["questions"] = [normalize_and_classify_question(q) for q in session.get("questions", [])]
    return session


@router.post(
    "/{session_id}/report",
    response_model=InterviewReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Candidate Decision Intelligence Report",
    description=(
        "Compiles final interview report with deterministic score aggregation, "
        "criterion averages, resume-to-interview evidence correlation, and qualitative coaching."
    ),
)
async def create_final_report(session_id: str) -> InterviewReportResponse:
    """Generate final interview decision intelligence report."""
    report = await generate_interview_report(session_id)
    await complete_session(session_id)
    return report


@router.get(
    "/{session_id}/report",
    response_model=InterviewReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Final Candidate Report",
    description="Retrieve existing compiled report for an interview session.",
)
async def fetch_final_report(
    session_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> InterviewReportResponse:
    """Retrieve existing or compile final report for an interview session."""
    target_session_id = session_id
    session = await get_session(session_id)

    # Fallback: if session not found by session_id, check if caller provided a report_id
    if not session:
        rep_doc = None
        if settings.is_mongodb_configured:
            try:
                db = db_manager.get_database()
                rep_doc = await db["interview_reports"].find_one({"report_id": session_id})
            except Exception:
                pass
        if not rep_doc:
            for r in _in_memory_reports.values():
                if r.get("report_id") == session_id:
                    rep_doc = r
                    break
        if rep_doc and rep_doc.get("session_id"):
            target_session_id = rep_doc["session_id"]
            session = await get_session(target_session_id)

    if session:
        session_owner = session.get("owner_id")
        if session_owner:
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to view this private report.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if current_user.get("role") == ROLE_CANDIDATE and session_owner != current_user.get("user_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden: You cannot view another candidate's private report.",
                )
    report = await get_interview_report(target_session_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )
    return report
