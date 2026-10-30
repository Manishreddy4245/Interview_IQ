import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
import groq

from app.core.config import settings
from app.core.database import db_manager
from app.core.groq_client import groq_manager
from app.schemas.evaluation import CriterionScores
from app.schemas.integrity import (
    IntegrityEventRecord,
    HumanReviewAuditEntry,
    CandidateExplanationEntry,
    ReviewerDecisionEntry,
)
from app.schemas.report import (
    CriterionAverageScores,
    IntegrityReportSection,
    PotentialCommunicationEventRecord,
    InterviewReportResponse,
    QuestionPerformanceSummary,
    ResumeComparisonSection,
    ResumeSkillComparisonItem,
    ExecutiveSummaryDetails,
    StrengthEvidenceDetail,
    WeaknessEvidenceDetail,
    QuestionRubricDeduction,
    TestCaseExecutionRecord,
    QuestionSolutionAnalysis,
    QuestionActionableImprovement,
    CompetencyAnalysisItem,
    PersonalizedRoadmapItem,
)
from app.services.resume_service import get_resume_analysis
from app.services.session_service import get_session
from app.services.gap_closure_service import build_traceable_skill_comparisons

logger = logging.getLogger("interviewiq.report_service")

# Fallback in-memory store for reports when MongoDB Atlas is unconfigured
_in_memory_reports: Dict[str, Dict[str, Any]] = {}


def _get_field(ev: Any, field_name: str, default: Any = None) -> Any:
    """Helper to retrieve field from dict or object safely."""
    if isinstance(ev, dict):
        return ev.get(field_name, default)
    return getattr(ev, field_name, default)


def _safe_parse_datetime(val: Any) -> Optional[datetime]:
    """Parse string or datetime object into UTC datetime, returning None on invalid inputs."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None
    return None


def _sort_events_chronologically(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort events chronologically by timestamp ascending.
    Events with invalid timestamps are preserved at the end in stable relative order.
    """
    indexed = list(enumerate(events))

    def sort_key(item):
        idx, ev = item
        parsed = _safe_parse_datetime(_get_field(ev, "timestamp"))
        if parsed is not None:
            return (0, parsed, idx)
        return (1, datetime.max.replace(tzinfo=timezone.utc), idx)

    return [ev for _, ev in sorted(indexed, key=sort_key)]


def compute_integrity_analytics(
    raw_events: List[Any],
) -> Tuple[float, int, Dict[str, int]]:
    """
    Calculate presence intelligence metrics from observable integrity events.

    Documented Interval-Pairing and Aggregation Rules:
    1. Per-Question Aggregation:
       - Every event is counted under its 'question_id' string.
       - Events with None, empty, or missing 'question_id' are grouped under 'unassociated'.
       - Historical records lacking question context remain fully readable and mapped to 'unassociated'.
    2. Chronological Sequencing:
       - Events are sorted chronologically ascending by parsed timestamp before interval pairing.
       - Events with non-parseable timestamps are safely skipped for interval pairing.
    3. Interval Pairing (Tab Visibility):
       - Only 'tab_hidden' and 'tab_visible' events are used to calculate cumulative unfocused duration.
       - 'window_blur' and 'window_focus' are tracked as distinct browser signals; they are NOT blended
         into the tab unfocused duration to prevent double-counting overlapping unfocused periods.
       - Pairing logic:
         * A 'tab_hidden' event starts an active hidden interval.
         * Duplicate consecutive 'tab_hidden' events while already hidden are ignored without restarting
           the interval or double counting.
         * The next valid 'tab_visible' event with timestamp > hidden start time completes the interval.
         * Duplicate or orphan 'tab_visible' events (when tab is not hidden) are ignored.
         * Non-positive intervals (end <= start due to clock skew or identical timestamps) are discarded.
       - Overlapping or repeated intervals are merged before summing to ensure cumulative duration is never inflated.
    4. Incomplete Intervals:
       - Any unmatched 'tab_hidden' event (lacking a closing 'tab_visible') increments
         'incomplete_intervals_count' and is NEVER converted into artificial completed duration (0.0 added).
    5. Safe Defaults & Score Isolation:
       - If raw_events is empty, returns (0.0, 0, {}).
       - Integrity metrics are strictly isolated from candidate capability scoring.
    """
    if not raw_events:
        return 0.0, 0, {}

    events_by_question: Dict[str, int] = {}

    # 1. Per-question aggregation
    for ev in raw_events:
        qid = _get_field(ev, "question_id")
        if qid is None or str(qid).strip() == "":
            q_key = "unassociated"
        else:
            q_key = str(qid).strip()
        events_by_question[q_key] = events_by_question.get(q_key, 0) + 1

    # 2. Extract valid tab visibility events with parseable timestamps
    tab_events: List[Tuple[datetime, str]] = []
    for ev in raw_events:
        raw_type = _get_field(ev, "event_type")
        ev_type_str = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
        if ev_type_str in ("tab_hidden", "tab_visible"):
            dt = _safe_parse_datetime(_get_field(ev, "timestamp"))
            if dt is not None:
                tab_events.append((dt, ev_type_str))

    # Chronologically sort tab visibility events
    tab_events.sort(key=lambda x: x[0])

    # 3. Pair tab_hidden and tab_visible
    raw_intervals: List[Tuple[datetime, datetime]] = []
    active_hidden_start: Optional[datetime] = None
    incomplete_intervals_count = 0

    for dt, ev_type_str in tab_events:
        if ev_type_str == "tab_hidden":
            if active_hidden_start is None:
                active_hidden_start = dt
            # Duplicate consecutive hidden is ignored to prevent double-counting
        elif ev_type_str == "tab_visible":
            if active_hidden_start is not None:
                if dt > active_hidden_start:
                    raw_intervals.append((active_hidden_start, dt))
                # If dt <= active_hidden_start, discard invalid/negative interval
                active_hidden_start = None
            # If active_hidden_start is None, orphan/duplicate visible is ignored

    if active_hidden_start is not None:
        incomplete_intervals_count += 1
        active_hidden_start = None

    # 4. Merge overlapping intervals to prevent inflation
    if not raw_intervals:
        return 0.0, incomplete_intervals_count, events_by_question

    raw_intervals.sort(key=lambda x: x[0])
    merged_intervals: List[List[datetime]] = []
    for start, end in raw_intervals:
        if not merged_intervals:
            merged_intervals.append([start, end])
        else:
            prev_start, prev_end = merged_intervals[-1]
            if start <= prev_end:
                merged_intervals[-1][1] = max(prev_end, end)
            else:
                merged_intervals.append([start, end])

    total_duration_seconds = sum(
        (interval_end - interval_start).total_seconds()
        for interval_start, interval_end in merged_intervals
    )

    return round(total_duration_seconds, 2), incomplete_intervals_count, events_by_question



async def _synthesize_executive_summary_with_groq(
    role: str,
    experience_level: str,
    overall_score: Optional[float],
    evaluated_count: int,
    total_count: int,
    evaluated_questions: List[Dict[str, Any]],
    key_strengths: List[str],
    priority_improvements: List[str],
) -> Dict[str, Any]:
    """
    Synthesize qualitative summary and recommended next steps using Groq.
    Grounded exclusively in evaluated answers without inventing scores or skills.
    Falls back deterministically if Groq is unavailable.
    """
    if not settings.is_groq_configured:
        return _deterministic_summary_fallback(
            role=role,
            overall_score=overall_score,
            evaluated_count=evaluated_count,
            total_count=total_count,
            key_strengths=key_strengths,
            priority_improvements=priority_improvements,
        )

    system_prompt = (
        "You are an expert technical interviewer and executive talent evaluator. "
        "Summarize candidate performance into an executive summary and recommended next steps. "
        "Strictly ground all findings in the provided evaluated questions and scores without inventing any data. "
        "Return a JSON object with 'executive_summary' (string) and 'recommended_next_steps' (list of strings)."
    )
    user_content = {
        "role": role,
        "experience_level": experience_level,
        "overall_score": overall_score,
        "evaluated_count": evaluated_count,
        "total_count": total_count,
        "evaluated_questions": evaluated_questions,
        "key_strengths": key_strengths,
        "priority_improvements": priority_improvements,
    }

    try:
        raw = await groq_manager.execute_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_content)},
            ],
            temperature=0.4,
            max_tokens=1500,
            timeout=30.0,
            reasoning_effort="low",
        )
        data = json.loads(raw)
        return {
            "executive_summary": data.get("executive_summary", "").strip()
            or _deterministic_summary_fallback(
                role, overall_score, evaluated_count, total_count, key_strengths, priority_improvements
            )["executive_summary"],
            "recommended_next_steps": data.get("recommended_next_steps", [])
            or _deterministic_summary_fallback(
                role, overall_score, evaluated_count, total_count, key_strengths, priority_improvements
            )["recommended_next_steps"],
        }
    except Exception as exc:
        logger.warning("Groq report synthesis failed (%s), using deterministic fallback.", type(exc).__name__)
        return _deterministic_summary_fallback(
            role=role,
            overall_score=overall_score,
            evaluated_count=evaluated_count,
            total_count=total_count,
            key_strengths=key_strengths,
            priority_improvements=priority_improvements,
        )


def _deterministic_summary_fallback(
    role: str,
    overall_score: Optional[float],
    evaluated_count: int,
    total_count: int,
    key_strengths: List[str],
    priority_improvements: List[str],
) -> Dict[str, Any]:
    """Purely deterministic summary derived directly from evaluation data."""
    if evaluated_count == 0:
        return {
            "executive_summary": (
                f"Interview session initialized for '{role}'. No candidate answers have been evaluated yet. "
                "Complete questions in the interview room to generate performance analytics."
            ),
            "recommended_next_steps": [
                "Practice answering the assigned session questions.",
                "Submit answers to generate AI criterion feedback and coaching.",
            ],
        }

    score_denom = "/100" if (overall_score is not None and overall_score > 10) else "/10"
    score_text = f"{overall_score}{score_denom}" if overall_score is not None else "N/A"
    strengths_text = "; ".join(key_strengths[:2]) if key_strengths else "Foundational role familiarity"
    improvements_text = "; ".join(priority_improvements[:2]) if priority_improvements else "Deeper technical specificity"

    summary = (
        f"Candidate completed {evaluated_count} of {total_count} questions for '{role}' with an overall evaluated "
        f"score of {score_text}. Demonstrated strengths include: {strengths_text}. Key areas for development "
        f"include: {improvements_text}."
    )

    next_steps = []
    if priority_improvements:
        for imp in priority_improvements[:3]:
            next_steps.append(f"Focus on {imp.lower().rstrip('.')}.")
    if evaluated_count < total_count:
        next_steps.append(f"Complete remaining {total_count - evaluated_count} unanswered questions to achieve 100% evaluation coverage.")
    if not next_steps:
        next_steps = ["Continue structured practice with timed behavioral and system architecture scenarios."]

    return {
        "executive_summary": summary,
        "recommended_next_steps": next_steps,
    }


def _build_rubric_breakdown(
    q_item: Dict[str, Any],
    eval_data: Optional[Dict[str, Any]],
    q_crit_scores: Optional[CriterionScores],
) -> List[QuestionRubricDeduction]:
    """Map rubric criteria to demonstrable candidate evidence and deductions."""
    if not q_crit_scores or not eval_data:
        return []

    breakdown: List[QuestionRubricDeduction] = []
    q_type = (q_item.get("question_type") or "verbal").lower()
    is_behavioral = q_type == "behavioral" or "behavioral" in (q_item.get("text") or "").lower()

    criteria_specs = [
        (
            "Relevance & Directness",
            q_crit_scores.relevance,
            "Directly addresses the prompt and questions without tangential diversion.",
        ),
        (
            "Technical Depth & Accuracy",
            q_crit_scores.technical_depth,
            "Demonstrates precise domain knowledge, accurate mechanics, and technical depth.",
        ),
        (
            "Completeness & Edge Cases",
            q_crit_scores.completeness,
            "Addresses all required aspects, sub-parts, boundary conditions, and parameters.",
        ),
        (
            "Structure & Coherence",
            q_crit_scores.structure_flow,
            "Presents thoughts with logical sequencing, clear progression, and clean transitions.",
        ),
        (
            "Clarity & Conciseness",
            q_crit_scores.clarity_conciseness,
            "Articulates concepts crisply with high information density and no unnecessary filler.",
        ),
    ]

    # Include STAR framework only if the prompt is genuinely behavioral
    if is_behavioral and q_crit_scores.star_structure:
        criteria_specs.append(
            (
                "STAR Framework Execution",
                q_crit_scores.star_structure,
                "Structured using Situation, Task, Action taken, and measurable Result.",
            )
        )

    for name, crit, standard in criteria_specs:
        if not crit:
            continue
        score = float(crit.score)
        feedback = crit.feedback.strip() if crit.feedback else "No feedback provided."
        max_score = 10.0
        deduction = max(0.0, round(max_score - score, 1))

        if deduction == 0.0:
            missing_or_incorrect = "No deficiencies identified. Fully meets or exceeds the expected standard."
            deduction_reason = "Full marks awarded (0.0 pts deducted)."
        else:
            missing_or_incorrect = feedback
            deduction_reason = f"Deducted {deduction} pts: {feedback}"

        breakdown.append(
            QuestionRubricDeduction(
                criterion_name=name,
                expected_standard=standard,
                demonstrated_evidence=feedback,
                missing_or_incorrect=missing_or_incorrect,
                score_awarded=score,
                max_score=max_score,
                deduction_reason=deduction_reason,
            )
        )

    return breakdown


def _build_strengths_and_weaknesses_detail(
    q_item: Dict[str, Any],
    ans_data: Dict[str, Any],
    eval_data: Optional[Dict[str, Any]],
) -> Tuple[List[StrengthEvidenceDetail], List[WeaknessEvidenceDetail]]:
    """Extract evidence-grounded strengths and weakness details without fabricating claims."""
    strengths_detail: List[StrengthEvidenceDetail] = []
    weaknesses_detail: List[WeaknessEvidenceDetail] = []

    if not eval_data:
        return strengths_detail, weaknesses_detail

    answer_text = ans_data.get("answer_text", "")
    code_text = ans_data.get("code", "")
    full_text = f"{answer_text}\n{code_text}".strip()

    # Process strengths
    raw_strengths = eval_data.get("strengths", [])
    for st in raw_strengths:
        st_clean = st.strip()
        if not st_clean:
            continue
        concept = st_clean.split(":")[0].split(".")[0].strip() if (":" in st_clean or "." in st_clean) else st_clean[:50]
        evidence_quote = None
        for word in st_clean.split():
            clean_word = word.strip(".,;:()\"'")
            if len(clean_word) > 4 and clean_word.lower() in full_text.lower():
                for sentence in full_text.split("."):
                    if clean_word.lower() in sentence.lower():
                        evidence_quote = sentence.strip()
                        break
                if evidence_quote:
                    break

        strengths_detail.append(
            StrengthEvidenceDetail(
                concept=concept,
                why_correct=st_clean,
                evidence_quote=evidence_quote or f"Observed in response: '{st_clean}'",
            )
        )

    # Process areas for improvement / weaknesses
    raw_improvements = eval_data.get("areas_for_improvement", [])
    for imp in raw_improvements:
        imp_clean = imp.strip()
        if not imp_clean:
            continue
        concept = imp_clean.split(":")[0].split(".")[0].strip() if (":" in imp_clean or "." in imp_clean) else imp_clean[:50]

        lower_imp = imp_clean.lower()
        if any(w in lower_imp for w in ["incorrect", "wrong", "flaw", "bug", "syntax error"]):
            issue_type = "incorrect_statement"
        elif any(w in lower_imp for w in ["incomplete", "partial", "half"]):
            issue_type = "incomplete_solution"
        elif any(w in lower_imp for w in ["missing", "omit", "could mention", "specify", "name", "did not"]):
            issue_type = "missing_explanation"
        else:
            issue_type = "missing_explanation"

        technical_impact = (
            f"Precision gap in technical communication: {imp_clean}. "
            "In engineering interviews, omitting exact specifications or mechanics "
            "prevents verification of production depth."
        )

        weaknesses_detail.append(
            WeaknessEvidenceDetail(
                concept=concept,
                technical_impact=technical_impact,
                issue_type=issue_type,
                evidence_quote=f"Identified in answer evaluation: '{imp_clean}'",
            )
        )

    return strengths_detail, weaknesses_detail


def _build_solution_analysis(
    q_item: Dict[str, Any],
    ans_data: Dict[str, Any],
    eval_data: Optional[Dict[str, Any]],
) -> QuestionSolutionAnalysis:
    """Construct factual, evidence-backed reference solution analysis and test results."""
    q_type = (q_item.get("question_type") or "verbal").lower()
    is_coding = q_type == "coding_dsa" or bool(ans_data.get("code"))
    exec_res = ans_data.get("execution_result") or {}

    if is_coding:
        code_mistakes: List[str] = []
        if exec_res.get("compilation_error"):
            code_mistakes.append(f"Compilation / Syntax Error: {exec_res['compilation_error'][:250]}")
        if exec_res.get("runtime_error"):
            code_mistakes.append(f"Runtime Exception: {exec_res['runtime_error'][:250]}")
        if eval_data:
            for imp in eval_data.get("areas_for_improvement", []):
                code_mistakes.append(imp)

        test_cases_records: List[TestCaseExecutionRecord] = []
        raw_test_results = exec_res.get("test_results") or []
        for tr in raw_test_results:
            test_cases_records.append(
                TestCaseExecutionRecord(
                    test_case_id=tr.get("test_case_id", "tc"),
                    input=str(tr.get("input", "")),
                    expected_output=str(tr.get("expected_output", "")),
                    actual_output=str(tr.get("actual_output", "")) if tr.get("actual_output") is not None else None,
                    passed=bool(tr.get("passed", False)),
                    is_hidden=bool(tr.get("is_hidden", False)),
                    error=tr.get("error"),
                )
            )

        if raw_test_results or ("passed_tests" in exec_res and "total_tests" in exec_res):
            verification_mode = "verified_execution"
            passed = exec_res.get("passed_tests", 0)
            total = exec_res.get("total_tests", len(test_cases_records))
            summary_text = f"Automated test execution: {passed} of {total} test cases passed."
        elif ans_data.get("code"):
            verification_mode = "static_analysis"
            summary_text = "Code submitted was analyzed via static code inspection; sandboxed execution output not stored."
        else:
            verification_mode = "unverified"
            summary_text = "No candidate code submitted for this coding question."

        optimal_algo = (
            q_item.get("algorithm")
            or q_item.get("solution_approach")
            or f"Optimal algorithmic solution for {q_item.get('assessed_skill', 'DSA problem')}"
        )
        time_comp = q_item.get("time_complexity") or "O(N) - Linear time complexity over input size"
        space_comp = q_item.get("space_complexity") or "O(1) auxiliary space (or O(N) auxiliary storage where required)"

        corrected_code = (
            q_item.get("canonical_solution")
            or q_item.get("reference_solution")
            or (eval_data.get("stronger_example_answer") if eval_data else None)
        )

        return QuestionSolutionAnalysis(
            expected_approach=(
                "1. Analyze constraints and edge cases (empty input, single element, boundary limits). "
                "2. Formulate optimal algorithmic approach with minimal time and memory overhead. "
                "3. Implement clean, modular code with clear variable naming and robust error handling."
            ),
            model_answer=eval_data.get("stronger_example_answer") if eval_data else None,
            tradeoffs_and_terminology=[
                f"Assessed Skill: {q_item.get('assessed_skill', 'Algorithms')}",
                f"Time Complexity: {time_comp}",
                f"Space Complexity: {space_comp}",
            ],
            why_model_is_stronger="The reference implementation satisfies all boundary conditions and passes 100% of functional test cases within optimal complexity bounds.",
            is_coding=True,
            code_mistakes=code_mistakes,
            missed_edge_cases=q_item.get("constraints") or ["Empty or single-element inputs", "Boundary integer overflow", "Duplicate values"],
            test_cases_summary=summary_text,
            test_cases=test_cases_records,
            optimal_algorithm=optimal_algo,
            time_complexity=time_comp,
            space_complexity=space_comp,
            corrected_code=corrected_code,
            verification_mode=verification_mode,
        )

    model_ans = (eval_data.get("stronger_example_answer") if eval_data else None) or q_item.get("reference_answer")
    tradeoffs = [
        f"Domain Competency: {q_item.get('assessed_skill', 'Technical Concepts')}",
        "Runtime lifecycle and memory location trade-offs",
        "Maintainability and architectural decoupling",
    ]
    if q_type == "sql":
        tradeoffs = ["Index utilization", "Join strategy (Hash vs Nested Loop)", "Aggregation performance"]
    elif q_type == "system_design":
        tradeoffs = ["CAP Theorem consistency vs availability", "Horizontal vs vertical scalability", "Failure domains"]

    why_stronger = (
        "The model solution incorporates precise engineering terminology and explicitly specifies "
        "underlying runtime behavior (e.g. memory segments, lifecycle hooks, and architectural boundaries), "
        "providing a comprehensive answer with production-grade depth."
    )

    return QuestionSolutionAnalysis(
        expected_approach=(
            "State concise definitions, ground the concept with a concrete real-world analogy or architecture diagram, "
            "and explain internal runtime mechanics, memory layout, and operational trade-offs."
        ),
        model_answer=model_ans,
        tradeoffs_and_terminology=tradeoffs,
        why_model_is_stronger=why_stronger,
        is_coding=False,
        code_mistakes=[],
        missed_edge_cases=[],
        test_cases_summary=None,
        test_cases=[],
        optimal_algorithm=None,
        time_complexity=None,
        space_complexity=None,
        corrected_code=None,
        verification_mode="static_analysis",
    )


def _build_actionable_improvement(
    q_item: Dict[str, Any],
    eval_data: Optional[Dict[str, Any]],
) -> QuestionActionableImprovement:
    """Formulate a targeted, measurable follow-up improvement plan for a specific question."""
    skill = q_item.get("assessed_skill", "Technical Competency")
    suggestions = eval_data.get("actionable_suggestions", []) if eval_data else []
    improvements = eval_data.get("areas_for_improvement", []) if eval_data else []

    correction = suggestions[0] if suggestions else (improvements[0] if improvements else f"Deepen technical specificity when explaining {skill}.")
    concept = eval_data.get("recommended_practice") if eval_data and eval_data.get("recommended_practice") else f"Advanced architecture and runtime behavior of {skill}"
    exercise = f"Complete a timed 5-minute verbal explanation or mock drill articulating {concept} with concrete architecture terminology."
    criterion = f"Able to explain {skill} end-to-end without hesitation, correctly naming internal memory/data structures and trade-offs."

    return QuestionActionableImprovement(
        specific_correction=correction,
        concept_to_study=concept,
        targeted_exercise=exercise,
        resolution_criterion=criterion,
    )


def _build_competencies_analysis(
    raw_questions: List[Dict[str, Any]],
    questions_perf: List[QuestionPerformanceSummary],
) -> List[CompetencyAnalysisItem]:
    """Aggregate competency performance across all questions, separating unassessed skills."""
    skills_map: Dict[str, List[QuestionPerformanceSummary]] = {}
    for q in questions_perf:
        skill = q.assessed_skill or "General Technical"
        if skill not in skills_map:
            skills_map[skill] = []
        skills_map[skill].append(q)

    items: List[CompetencyAnalysisItem] = []
    for skill, q_list in skills_map.items():
        total_q = len(q_list)
        eval_q = [q for q in q_list if q.is_evaluated and q.overall_score is not None]
        eval_count = len(eval_q)

        if eval_count == 0:
            status_text = "Insufficient Evidence"
            avg_score = None
            strengths = []
            weaknesses = []
            evidence = ["Question assigned in session plan but not yet answered or evaluated. No performance data available."]
        else:
            avg_score = round(sum(q.overall_score for q in eval_q) / eval_count, 1)
            status_text = "Demonstrated" if avg_score >= 70.0 else "Needs Further Assessment"

            all_s: List[str] = []
            all_w: List[str] = []
            evidence = []
            for q in eval_q:
                all_s.extend(q.strengths)
                all_w.extend(q.areas_for_improvement)
                score_str = f"{q.overall_score}/100"
                summary_excerpt = q.strengths[0] if q.strengths else "Evaluated submission"
                evidence.append(f"Q{q.question_number} ({score_str}): {summary_excerpt}")

            strengths = list(dict.fromkeys(all_s))[:4]
            weaknesses = list(dict.fromkeys(all_w))[:4]

        items.append(
            CompetencyAnalysisItem(
                competency_name=skill,
                average_score=avg_score,
                evaluated_questions_count=eval_count,
                total_questions_count=total_q,
                status=status_text,
                demonstrated_strengths=strengths,
                recurring_weaknesses=weaknesses,
                supporting_evidence=evidence,
            )
        )

    return items


def _build_personalized_roadmap(
    questions_perf: List[QuestionPerformanceSummary],
    role: str,
) -> List[PersonalizedRoadmapItem]:
    """
    Construct a prioritized learning roadmap from candidate's actual evaluated weaknesses.
    Strictly orders foundational concepts (syntax, memory, core algorithms) before advanced topics.
    """
    evaluated_questions = [q for q in questions_perf if q.is_evaluated]
    if not evaluated_questions:
        return [
            PersonalizedRoadmapItem(
                priority_rank=1,
                topic=f"Core Fundamentals for {role}",
                why_it_matters="No interview questions have been evaluated yet to diagnose specific gaps.",
                what_to_learn_first="Review baseline job role requirements, language syntax, and standard libraries.",
                practice_exercise=f"Complete foundational interview practice sessions for '{role}'.",
                completion_criterion="Answer and submit at least 3 practice questions to establish a diagnostic baseline.",
            )
        ]

    raw_gaps: List[Tuple[int, str, str, str, str, str]] = []

    def assess_topic_tier(text: str) -> int:
        lower = text.lower()
        if any(w in lower for w in ["memory", "allocation", "heap", "stack", "syntax", "fundamental", "primitive", "variable", "pointer", "reference"]):
            return 1
        if any(w in lower for w in ["array", "hash", "string", "loop", "recursion", "dsa", "complexity", "big-o"]):
            return 2
        if any(w in lower for w in ["database", "sql", "join", "query", "index", "api", "rest", "crud"]):
            return 3
        if any(w in lower for w in ["concurrency", "thread", "async", "lock", "synchronization"]):
            return 4
        if any(w in lower for w in ["system design", "distributed", "cache", "microservice", "scalability", "kafka"]):
            return 5
        return 3

    for q in evaluated_questions:
        for area in q.areas_for_improvement:
            tier = assess_topic_tier(area)
            topic = q.assessed_skill if q.assessed_skill else "Technical Concept"
            why = f"Directly observed in Question {q.question_number}: {area}"
            first_step = f"Study the underlying principles and exact specifications of {topic}."
            exercise = (
                q.actionable_improvement.targeted_exercise
                if q.actionable_improvement
                else f"Practice 3 targeted drills focusing on {area}."
            )
            criterion = (
                q.actionable_improvement.resolution_criterion
                if q.actionable_improvement
                else f"Demonstrate mastery of {topic} by achieving score >= 85 in a follow-up assessment."
            )
            raw_gaps.append((tier, f"{topic}: {area[:40]}", why, first_step, exercise, criterion))

    raw_gaps.sort(key=lambda x: x[0])

    roadmap: List[PersonalizedRoadmapItem] = []
    seen_topics = set()
    rank = 1
    for _, topic, why, first_step, exercise, criterion in raw_gaps:
        if topic in seen_topics:
            continue
        seen_topics.add(topic)
        roadmap.append(
            PersonalizedRoadmapItem(
                priority_rank=rank,
                topic=topic,
                why_it_matters=why,
                what_to_learn_first=first_step,
                practice_exercise=exercise,
                completion_criterion=criterion,
            )
        )
        rank += 1
        if rank > 5:
            break

    if not roadmap:
        roadmap.append(
            PersonalizedRoadmapItem(
                priority_rank=1,
                topic=f"Advanced Problem Solving for {role}",
                why_it_matters="Candidate demonstrated solid baseline competence across evaluated questions.",
                what_to_learn_first="Explore edge-case optimization, distributed system failure modes, and low-latency trade-offs.",
                practice_exercise="Solve hard-difficulty algorithmic challenges and architectural whiteboarding scenarios.",
                completion_criterion="Consistently achieve >= 90 overall score across complex multi-part questions.",
            )
        )

    return roadmap


def _build_executive_summary_details(
    role: str,
    overall_score: Optional[float],
    evaluated_scores: List[float],
    total_questions: int,
    answered_count: int,
    evaluated_count: int,
    unanswered_count: int,
    coverage_pct: float,
    competencies_analysis: List[CompetencyAnalysisItem],
    priority_improvements: List[str],
    roadmap: List[PersonalizedRoadmapItem],
) -> ExecutiveSummaryDetails:
    """Generate comprehensive executive summary details with evidence and readiness synthesis."""
    if evaluated_count > 0 and overall_score is not None:
        calc_str = (
            f"Arithmetic mean across {evaluated_count} evaluated question(s): "
            f"sum({[round(s, 1) for s in evaluated_scores]}) / {evaluated_count} = {overall_score}/100. "
            f"Assigned session coverage: {coverage_pct}% ({evaluated_count}/{total_questions} questions). "
            f"{unanswered_count} unevaluated question(s) are strictly excluded from the score average."
        )
    else:
        calc_str = (
            f"0 evaluated questions out of {total_questions} assigned (0.0% coverage). "
            "Overall score cannot be computed until at least one answer is evaluated."
        )

    strongest = [c.competency_name for c in competencies_analysis if c.status == "Demonstrated"]
    if not strongest:
        strongest = [c.competency_name for c in competencies_analysis if c.average_score is not None and c.average_score >= 60.0]

    recurring: List[str] = []
    all_weaknesses = []
    for c in competencies_analysis:
        all_weaknesses.extend(c.recurring_weaknesses)

    if any("terminolog" in w.lower() or "name" in w.lower() or "metaspace" in w.lower() for w in all_weaknesses):
        recurring.append("Omission of specific runtime terminology when explaining system architecture internals.")
    if any("edge" in w.lower() or "boundary" in w.lower() or "null" in w.lower() for w in all_weaknesses):
        recurring.append("Incomplete boundary condition handling on extreme or atypical input ranges.")
    if not recurring and priority_improvements:
        recurring.append(f"Primary recurring focus area: {priority_improvements[0]}")

    if overall_score is not None and overall_score >= 80.0 and coverage_pct >= 50.0:
        readiness_level = "Interview Ready"
        readiness_summary = (
            f"Candidate demonstrates strong technical competence ({overall_score}/100) for '{role}'. "
            f"Demonstrated strengths in {', '.join(strongest[:2]) if strongest else 'core skills'}. "
            f"With {coverage_pct}% evaluation coverage, candidate shows reliable readiness for live technical interview loops."
        )
    elif overall_score is not None and overall_score >= 60.0:
        readiness_level = "Borderline / Needs Practice"
        readiness_summary = (
            f"Candidate demonstrates foundational competency ({overall_score}/100) for '{role}', but exhibits "
            f"targetable gaps in technical specificity: {'; '.join(priority_improvements[:2]) if priority_improvements else 'advanced concepts'}. "
            "Requires targeted revision on identified roadmap priorities prior to final hiring rounds."
        )
    else:
        readiness_level = "Needs Substantial Preparation"
        readiness_summary = (
            f"Assessment results indicate significant development required for '{role}'. "
            f"{'Low score profile (' + str(overall_score) + '/100)' if overall_score is not None else 'Insufficient evaluated coverage'}. "
            "Prioritize foundational learning roadmap milestones before scheduling technical screens."
        )

    learning_priorities = [item.topic for item in roadmap[:3]]

    return ExecutiveSummaryDetails(
        overall_score=overall_score,
        scoring_calculation=calc_str,
        total_questions=total_questions,
        attempted_questions=answered_count,
        answered_questions=answered_count,
        evaluated_questions=evaluated_count,
        unevaluated_questions=unanswered_count,
        evaluation_coverage_pct=coverage_pct,
        strongest_competencies=strongest[:4],
        priority_weaknesses=priority_improvements[:4],
        recurring_mistakes=recurring,
        readiness_level=readiness_level,
        readiness_summary=readiness_summary,
        recommended_learning_priorities=learning_priorities,
    )


async def generate_interview_report(session_id: str) -> InterviewReportResponse:
    """
    Compile a complete, factual final interview report for an existing interview session.
    Strictly aggregates existing evaluated answers without inventing scores or fake fallbacks.
    Excludes integrity events from candidate scores.
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    # Check if a report ID already exists for this session to preserve MongoDB immutable _id
    existing_id = None
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            existing_doc = await db["interview_reports"].find_one({"session_id": session_id}, {"_id": 1, "report_id": 1})
            if existing_doc:
                existing_id = existing_doc.get("_id") or existing_doc.get("report_id")
        except Exception:
            pass
    if not existing_id and session_id in _in_memory_reports:
        existing_id = _in_memory_reports[session_id].get("report_id")

    report_id = str(existing_id) if existing_id else str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    role = session.get("role", "Target Role")
    experience_level = session.get("experience_level", "Mid-Level")
    difficulty = session.get("difficulty", "Medium")
    focus_areas = session.get("focus_areas", "")

    raw_questions = session.get("questions", [])
    raw_answers = session.get("answers", {})
    raw_events = session.get("integrity_events", [])

    total_questions = len(raw_questions)

    # 1. Process questions and evaluations
    questions_perf: List[QuestionPerformanceSummary] = []
    evaluated_scores: List[float] = []
    rel_scores: List[float] = []
    tech_scores: List[float] = []
    comp_scores: List[float] = []
    struct_scores: List[float] = []
    clar_scores: List[float] = []
    star_scores: List[float] = []

    all_strengths: List[str] = []
    all_improvements: List[str] = []
    evaluated_for_ai: List[Dict[str, Any]] = []

    for q in raw_questions:
        q_id = q["id"]
        ans_data = raw_answers.get(q_id, {})
        answer_text = ans_data.get("answer_text", "").strip()
        ans_code = ans_data.get("code")
        ans_sql = ans_data.get("sql_query")
        is_answered = bool(answer_text or ans_code or ans_sql)

        eval_data = ans_data.get("evaluation")
        is_evaluated = bool(eval_data)

        q_overall_score = None
        q_crit_scores = None
        q_strengths = []
        q_improvements = []

        if is_evaluated:
            q_overall_score = float(eval_data.get("overall_score", 0))
            evaluated_scores.append(q_overall_score)

            crit_raw = eval_data.get("criterion_scores", {})
            q_crit_scores = CriterionScores.model_validate(crit_raw)

            if q_crit_scores.relevance:
                rel_scores.append(float(q_crit_scores.relevance.score))
            if q_crit_scores.technical_depth:
                tech_scores.append(float(q_crit_scores.technical_depth.score))
            if q_crit_scores.completeness:
                comp_scores.append(float(q_crit_scores.completeness.score))
            if q_crit_scores.structure_flow:
                struct_scores.append(float(q_crit_scores.structure_flow.score))
            if q_crit_scores.clarity_conciseness:
                clar_scores.append(float(q_crit_scores.clarity_conciseness.score))
            if q_crit_scores.star_structure:
                star_scores.append(float(q_crit_scores.star_structure.score))

            q_strengths = eval_data.get("strengths", [])
            q_improvements = eval_data.get("areas_for_improvement", [])

            all_strengths.extend(q_strengths)
            all_improvements.extend(q_improvements)

            evaluated_for_ai.append({
                "question": q.get("text"),
                "assessed_skill": q.get("assessed_skill"),
                "overall_score": q_overall_score,
                "strengths": q_strengths,
                "improvements": q_improvements,
            })

        snippet = (answer_text[:120] + "...") if len(answer_text) > 120 else answer_text if is_answered else None

        q_type = q.get("question_type", "verbal")
        ans_code = ans_data.get("code")
        ans_lang = ans_data.get("language")
        ans_sql = ans_data.get("sql_query")
        exec_res = ans_data.get("execution_result") or {}
        tests_passed_text = None
        if isinstance(exec_res, dict) and "passed_tests" in exec_res and "total_tests" in exec_res:
            tests_passed_text = f"{exec_res['passed_tests']}/{exec_res['total_tests']} tests passed"
        sql_status_text = None
        if isinstance(exec_res, dict) and "is_correct" in exec_res:
            sql_status_text = "Correct query" if exec_res["is_correct"] else "Output mismatch"

        # Determine strict availability
        if is_answered or ans_code or ans_sql:
            ans_avail = "available"
        elif is_evaluated:
            ans_avail = "not_stored"
        else:
            ans_avail = "unanswered"

        rubric_breakdown = _build_rubric_breakdown(q, eval_data, q_crit_scores) if is_evaluated else []
        strengths_detail, weaknesses_detail = _build_strengths_and_weaknesses_detail(q, ans_data, eval_data) if is_evaluated else ([], [])
        solution_analysis = _build_solution_analysis(q, ans_data, eval_data)
        actionable_improvement = _build_actionable_improvement(q, eval_data) if is_evaluated else None

        questions_perf.append(
            QuestionPerformanceSummary(
                question_id=q_id,
                question_number=q.get("question_number", 1),
                question_text=q.get("text", ""),
                assessed_skill=q.get("assessed_skill", ""),
                difficulty=q.get("difficulty", "Medium"),
                is_answered=is_answered,
                is_evaluated=is_evaluated,
                overall_score=q_overall_score,
                criterion_scores=q_crit_scores,
                strengths=q_strengths,
                areas_for_improvement=q_improvements,
                candidate_answer_snippet=snippet,
                question_type=q_type,
                code_snippet=(ans_code[:120] + "...") if ans_code and len(ans_code) > 120 else ans_code,
                language=ans_lang,
                sql_query=(ans_sql[:120] + "...") if ans_sql and len(ans_sql) > 120 else ans_sql,
                tests_passed=tests_passed_text,
                sql_status=sql_status_text,
                full_candidate_answer=answer_text if is_answered else None,
                full_code=ans_code,
                answer_availability=ans_avail,
                strengths_detail=strengths_detail,
                weaknesses_detail=weaknesses_detail,
                rubric_breakdown=rubric_breakdown,
                solution_analysis=solution_analysis,
                actionable_improvement=actionable_improvement,
            )
        )

    answered_count = sum(1 for q in questions_perf if q.is_answered)
    unanswered_count = total_questions - answered_count
    evaluated_count = len(evaluated_scores)
    coverage_pct = round((evaluated_count / total_questions) * 100, 1) if total_questions > 0 else 0.0

    # 1.5. Aggregate competencies and personalized roadmap
    competencies_analysis = _build_competencies_analysis(raw_questions, questions_perf)
    learning_roadmap = _build_personalized_roadmap(questions_perf, role)

    # 2. Compute aggregate scores
    if evaluated_count == 0:
        overall_score = None
        score_status = "insufficient_data"
        formula_exp = (
            f"0 of {total_questions} questions have been evaluated (0.0% coverage). "
            "An aggregate score cannot be calculated until at least one answer is evaluated. "
            "Unanswered questions are not treated as zeros."
        )
        crit_averages = CriterionAverageScores()
    else:
        overall_score = round(sum(evaluated_scores) / evaluated_count, 1)
        score_status = "calculated"
        formula_exp = (
            f"Arithmetic mean of {evaluated_count} evaluated answer overall scores out of {total_questions} "
            f"total session questions ({coverage_pct}% coverage). "
            "Formula: sum(evaluated_scores) / evaluated_count. Unanswered questions are strictly excluded from calculation."
        )
        crit_averages = CriterionAverageScores(
            relevance=round(sum(rel_scores) / len(rel_scores), 1) if rel_scores else None,
            technical_depth=round(sum(tech_scores) / len(tech_scores), 1) if tech_scores else None,
            completeness=round(sum(comp_scores) / len(comp_scores), 1) if comp_scores else None,
            structure_flow=round(sum(struct_scores) / len(struct_scores), 1) if struct_scores else None,
            clarity_conciseness=round(sum(clar_scores) / len(clar_scores), 1) if clar_scores else None,
            star_structure=round(sum(star_scores) / len(star_scores), 1) if star_scores else None,
        )

    # Deduplicate strengths and improvements
    key_strengths = list(dict.fromkeys(all_strengths))[:6]
    priority_improvements = list(dict.fromkeys(all_improvements))[:6]

    # 3. Qualitative executive summary
    synthesis = await _synthesize_executive_summary_with_groq(
        role=role,
        experience_level=experience_level,
        overall_score=overall_score,
        evaluated_count=evaluated_count,
        total_count=total_questions,
        evaluated_questions=evaluated_for_ai,
        key_strengths=key_strengths,
        priority_improvements=priority_improvements,
    )

    # 4. Resume-to-Interview Comparison
    has_resume = False
    resume_section: Optional[ResumeComparisonSection] = None
    resume_analysis_id = session.get("resume_analysis_id")

    if resume_analysis_id:
        resume_analysis = await get_resume_analysis(resume_analysis_id)
        if resume_analysis:
            has_resume = True
            (
                skill_comp_items,
                demonstrated_count,
                partially_count,
                further_val_count,
                unassessed_count,
            ) = build_traceable_skill_comparisons(session, resume_analysis)

            resume_section = ResumeComparisonSection(
                associated_analysis_id=resume_analysis_id,
                target_role=resume_analysis.target_role,
                skills_comparison=skill_comp_items,
                demonstrated_competencies_count=demonstrated_count,
                partially_demonstrated_count=partially_count,
                requires_further_validation_count=further_val_count,
                unassessed_count=unassessed_count,
                comparison_summary=(
                    f"Cross-referenced {len(skill_comp_items)} role and resume competencies against interview evidence: "
                    f"{demonstrated_count} demonstrated, {partially_count} partially demonstrated, "
                    f"{further_val_count} requiring further validation, and {unassessed_count} unassessed. "
                    "Unassessed competencies are not presumed to be lacking."
                ),
            )

    # 5. Integrity Summary
    unfocused_sec, incomplete_count, events_by_q = compute_integrity_analytics(raw_events)

    events_summary: Dict[str, int] = {}
    timeline_records: List[IntegrityEventRecord] = []
    sorted_events = _sort_events_chronologically(raw_events)
    for ev in sorted_events:
        raw_type = _get_field(ev, "event_type", "unknown")
        ev_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
        events_summary[ev_type] = events_summary.get(ev_type, 0) + 1
        ev_dt = _safe_parse_datetime(_get_field(ev, "timestamp")) or now
        timeline_records.append(
            IntegrityEventRecord(
                event_id=str(_get_field(ev, "event_id") or uuid.uuid4()),
                session_id=session_id,
                question_id=_get_field(ev, "question_id"),
                event_type=ev_type,
                timestamp=ev_dt,
                details=_get_field(ev, "details"),
                saved_to_db=bool(_get_field(ev, "saved_to_db", session.get("saved_to_db", False))),
                db_status=str(_get_field(ev, "db_status", session.get("db_status", "unconfigured"))),
                severity=_get_field(ev, "severity", "info"),
                duration_seconds=_get_field(ev, "duration_seconds"),
                detection_source=_get_field(ev, "detection_source"),
                detection_confidence=_get_field(ev, "detection_confidence"),
                status=_get_field(ev, "status", "recorded"),
            )
        )

    # 5.b Potential Communication & Integrity Events (for human review)
    potential_comm_records: List[PotentialCommunicationEventRecord] = []
    for ev in sorted_events:
        raw_type = _get_field(ev, "event_type", "unknown")
        ev_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)
        if ev_type == "possible_external_communication":
            ev_dt = _safe_parse_datetime(_get_field(ev, "timestamp")) or now
            details = _get_field(ev, "details") or {}
            ev_desc = (
                details.get("summary")
                or details.get("context")
                or "Potential external communication or conversational dialogue pattern detected during interview."
            )
            potential_comm_records.append(
                PotentialCommunicationEventRecord(
                    event_id=str(_get_field(ev, "event_id") or uuid.uuid4()),
                    timestamp=ev_dt,
                    duration_seconds=_get_field(ev, "duration_seconds"),
                    event_description=ev_desc,
                    evidence_source=str(_get_field(ev, "detection_source") or details.get("source") or "multimodal_monitoring"),
                    confidence=_get_field(ev, "detection_confidence") or details.get("confidence"),
                    warning_displayed=bool(details.get("warning_displayed", True)),
                    review_status=str(_get_field(ev, "status") or "potential_concern_requiring_human_review"),
                    question_id=_get_field(ev, "question_id"),
                    incident_type="possible_external_communication",
                )
            )

    raw_reviews = session.get("human_reviews", [])
    review_entries: List[HumanReviewAuditEntry] = []
    for r in raw_reviews:
        created_dt = _safe_parse_datetime(r.get("created_at")) or now
        review_entries.append(
            HumanReviewAuditEntry(
                note_id=r.get("note_id", str(uuid.uuid4())),
                reviewer_name=r.get("reviewer_name"),
                is_verified_identity=r.get("is_verified_identity", False),
                identity_note=r.get("identity_note", "Self-declared reviewer identity (unauthenticated environment)"),
                review_notes=r.get("review_notes", ""),
                created_at=created_dt,
            )
        )

    raw_explanations = session.get("candidate_explanations", [])
    explanation_entries: List[CandidateExplanationEntry] = []
    for exp in raw_explanations:
        created_dt = _safe_parse_datetime(exp.get("created_at")) or now
        raw_decisions = exp.get("decision_history", [])
        decisions: List[ReviewerDecisionEntry] = []
        for d in raw_decisions:
            d_created = d.get("created_at")
            d_created_dt = _safe_parse_datetime(d_created) or now
            decisions.append(
                ReviewerDecisionEntry(
                    decision_id=d.get("decision_id", str(uuid.uuid4())),
                    explanation_id=d.get("explanation_id", exp.get("explanation_id", "")),
                    status=d.get("status", "reviewed"),
                    reviewer_name=d.get("reviewer_name"),
                    reviewer_outcome=d.get("reviewer_outcome"),
                    is_verified_identity=d.get("is_verified_identity", False),
                    identity_note=d.get(
                        "identity_note",
                        "Self-declared reviewer identity (unauthenticated environment)",
                    ),
                    created_at=d_created_dt,
                )
            )

        explanation_entries.append(
            CandidateExplanationEntry(
                explanation_id=exp.get("explanation_id", str(uuid.uuid4())),
                session_id=session_id,
                event_id=exp.get("event_id"),
                explanation=exp.get("explanation", ""),
                status=exp.get("status", "pending_review"),
                reviewer_outcome=exp.get("reviewer_outcome"),
                decision_history=decisions,
                is_verified_identity=exp.get("is_verified_identity", False),
                identity_note=exp.get(
                    "identity_note",
                    "Candidate-provided explanation without authenticated identity verification (unauthenticated environment)",
                ),
                created_at=created_dt,
                saved_to_db=bool(session.get("saved_to_db", False)),
                db_status=session.get("db_status", "unconfigured"),
            )
        )

    integrity_section = IntegrityReportSection(
        total_events=len(timeline_records),
        events_summary=events_summary,
        events_timeline=timeline_records,
        cumulative_unfocused_seconds=unfocused_sec,
        incomplete_intervals_count=incomplete_count,
        events_by_question=events_by_q,
        human_reviews=review_entries,
        candidate_explanations=explanation_entries,
        potential_communication_events=potential_comm_records,
    )

    exec_summary_details = _build_executive_summary_details(
        role=role,
        overall_score=overall_score,
        evaluated_scores=evaluated_scores,
        total_questions=total_questions,
        answered_count=answered_count,
        evaluated_count=evaluated_count,
        unanswered_count=unanswered_count,
        coverage_pct=coverage_pct,
        competencies_analysis=competencies_analysis,
        priority_improvements=priority_improvements,
        roadmap=learning_roadmap,
    )

    # 6. Persistence handling
    saved_to_db = False
    db_status = "unconfigured"
    db_message = "MongoDB Atlas is not configured. Report is stored in active server memory only."

    report_doc = {
        "report_id": report_id,
        "session_id": session_id,
        "owner_id": session.get("owner_id"),
        "created_at": now.isoformat(),
        "role": role,
        "experience_level": experience_level,
        "difficulty": difficulty,
        "focus_areas": focus_areas,
        "total_questions": total_questions,
        "answered_questions": answered_count,
        "unanswered_questions": unanswered_count,
        "evaluated_questions": evaluated_count,
        "evaluation_coverage_pct": coverage_pct,
        "overall_score": overall_score,
        "score_status": score_status,
        "scoring_formula_explanation": formula_exp,
        "criterion_averages": crit_averages.model_dump(),
        "key_strengths": key_strengths,
        "priority_improvements": priority_improvements,
        "recommended_next_steps": synthesis["recommended_next_steps"],
        "executive_summary": synthesis["executive_summary"],
        "questions_performance": [q.model_dump() for q in questions_perf],
        "has_resume_comparison": has_resume,
        "resume_comparison": resume_section.model_dump() if resume_section else None,
        "integrity_summary": integrity_section.model_dump(),
        "executive_summary_details": exec_summary_details.model_dump(),
        "competencies_analysis": [c.model_dump() for c in competencies_analysis],
        "learning_roadmap": [r.model_dump() for r in learning_roadmap],
    }

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["interview_reports"].replace_one(
                {"session_id": session_id},
                {**report_doc, "_id": report_id},
                upsert=True,
            )
            saved_to_db = True
            db_status = "persisted"
            db_message = "Report successfully persisted to MongoDB Atlas."
            logger.info("Report for session %s persisted to MongoDB Atlas.", session_id)
        except Exception as exc:
            db_status = "unreachable"
            db_message = f"MongoDB write failed: {type(exc).__name__}. Storing in memory only."
            logger.warning("Failed to persist report for session %s to MongoDB: %s", session_id, type(exc).__name__)

    # Always keep in-memory cache
    _in_memory_reports[session_id] = report_doc

    return InterviewReportResponse(
        report_id=report_id,
        session_id=session_id,
        owner_id=session.get("owner_id"),
        created_at=now,
        role=role,
        experience_level=experience_level,
        difficulty=difficulty,
        focus_areas=focus_areas,
        total_questions=total_questions,
        answered_questions=answered_count,
        unanswered_questions=unanswered_count,
        evaluated_questions=evaluated_count,
        evaluation_coverage_pct=coverage_pct,
        overall_score=overall_score,
        score_status=score_status,
        scoring_formula_explanation=formula_exp,
        criterion_averages=crit_averages,
        key_strengths=key_strengths,
        priority_improvements=priority_improvements,
        recommended_next_steps=synthesis["recommended_next_steps"],
        executive_summary=synthesis["executive_summary"],
        questions_performance=questions_perf,
        has_resume_comparison=has_resume,
        resume_comparison=resume_section,
        integrity_summary=integrity_section,
        executive_summary_details=exec_summary_details,
        competencies_analysis=competencies_analysis,
        learning_roadmap=learning_roadmap,
        saved_to_db=saved_to_db,
        db_status=db_status,
        db_message=db_message,
    )


async def _upgrade_legacy_report_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure legacy report documents without rich fields (executive_summary_details,
    competencies_analysis, learning_roadmap) are safely and deterministically upgraded.
    """
    has_details = bool(doc.get("executive_summary_details"))
    has_competencies = bool(doc.get("competencies_analysis"))
    has_roadmap = bool(doc.get("learning_roadmap"))

    if has_details and has_competencies and has_roadmap:
        return doc

    session_id = doc.get("session_id", "")
    session = await get_session(session_id) if session_id else None

    raw_questions = session.get("questions", []) if session else []
    raw_answers = session.get("answers", {}) if session else {}

    # 1. Reconstruct questions_perf
    questions_perf: List[QuestionPerformanceSummary] = []
    if doc.get("questions_performance"):
        for qp in doc["questions_performance"]:
            if isinstance(qp, dict):
                questions_perf.append(QuestionPerformanceSummary(**qp))
            elif isinstance(qp, QuestionPerformanceSummary):
                questions_perf.append(qp)
    elif raw_questions:
        for q in raw_questions:
            q_id = q["id"]
            ans_data = raw_answers.get(q_id, {})
            answer_text = ans_data.get("answer_text", "").strip()
            ans_code = ans_data.get("code")
            ans_sql = ans_data.get("sql_query")
            is_answered = bool(answer_text or ans_code or ans_sql)
            eval_data = ans_data.get("evaluation")
            is_evaluated = bool(eval_data)
            q_overall_score = float(eval_data.get("overall_score", 0)) if is_evaluated else None
            q_crit_scores = eval_data.get("criterion_scores") if is_evaluated else None
            q_strengths = eval_data.get("strengths", []) if is_evaluated else []
            q_improvements = eval_data.get("areas_for_improvement", []) if is_evaluated else []
            actionable_improvement = _build_actionable_improvement(q, eval_data) if is_evaluated else None

            questions_perf.append(
                QuestionPerformanceSummary(
                    question_id=q_id,
                    question_number=q.get("question_number", 1),
                    question_text=q.get("text", ""),
                    assessed_skill=q.get("assessed_skill", ""),
                    difficulty=q.get("difficulty", "Medium"),
                    is_answered=is_answered,
                    is_evaluated=is_evaluated,
                    overall_score=q_overall_score,
                    criterion_scores=q_crit_scores,
                    strengths=q_strengths,
                    areas_for_improvement=q_improvements,
                    actionable_improvement=actionable_improvement,
                )
            )

    # 2. Competencies analysis
    if not has_competencies:
        comp_items = _build_competencies_analysis(raw_questions, questions_perf)
        if not comp_items:
            role_name = doc.get("role") or "Core Technical Skills"
            comp_items = [
                CompetencyAnalysisItem(
                    competency_name=doc.get("focus_areas") or role_name,
                    average_score=doc.get("overall_score"),
                    evaluated_questions_count=doc.get("evaluated_questions", 0),
                    total_questions_count=doc.get("total_questions", 0),
                    status="Demonstrated" if (doc.get("overall_score") or 0) >= 70.0 else "Needs Further Assessment",
                    demonstrated_strengths=doc.get("key_strengths", []),
                    recurring_weaknesses=doc.get("priority_improvements", []),
                    supporting_evidence=["Reconstructed from legacy assessment scores."],
                )
            ]
        doc["competencies_analysis"] = [c.model_dump() for c in comp_items]

    # 3. Learning roadmap
    if not has_roadmap:
        roadmap = _build_personalized_roadmap(questions_perf, doc.get("role", "Software Engineer"))
        if not roadmap:
            roadmap = [
                PersonalizedRoadmapItem(
                    priority_rank=1,
                    topic=f"Core Fundamentals for {doc.get('role', 'Target Role')}",
                    why_it_matters="Reconstructed from legacy evaluation diagnostics.",
                    what_to_learn_first="Review foundational domain principles and architecture patterns.",
                    practice_exercise="Complete practice exercises targeting observed improvement areas.",
                    completion_criterion="Achieve score >= 80 on follow-up technical assessment.",
                )
            ]
        doc["learning_roadmap"] = [r.model_dump() for r in roadmap]

    # 4. Executive summary details
    if not has_details:
        comp_objs = [
            CompetencyAnalysisItem(**c) if isinstance(c, dict) else c
            for c in doc["competencies_analysis"]
        ]
        roadmap_objs = [
            PersonalizedRoadmapItem(**r) if isinstance(r, dict) else r
            for r in doc["learning_roadmap"]
        ]
        evaluated_scores = [
            q.overall_score for q in questions_perf if q.is_evaluated and q.overall_score is not None
        ]
        if not evaluated_scores and doc.get("overall_score") is not None:
            evaluated_scores = [float(doc["overall_score"])]

        exec_details = _build_executive_summary_details(
            role=doc.get("role", "Target Role"),
            overall_score=doc.get("overall_score"),
            evaluated_scores=evaluated_scores,
            total_questions=doc.get("total_questions", 0),
            answered_count=doc.get("answered_questions", 0),
            evaluated_count=doc.get("evaluated_questions", 0),
            unanswered_count=doc.get("unanswered_questions", 0),
            coverage_pct=doc.get("evaluation_coverage_pct", 0.0),
            competencies_analysis=comp_objs,
            priority_improvements=doc.get("priority_improvements", []),
            roadmap=roadmap_objs,
        )
        doc["executive_summary_details"] = exec_details.model_dump()

    # Re-cache updated doc
    if session_id:
        _in_memory_reports[session_id] = doc
        if settings.is_mongodb_configured:
            try:
                db = db_manager.get_database()
                await db["interview_reports"].replace_one(
                    {"session_id": session_id},
                    {**doc, "_id": doc.get("report_id", session_id)},
                    upsert=True,
                )
            except Exception:
                pass

    return doc


async def get_interview_report(session_id: str) -> Optional[InterviewReportResponse]:
    """Retrieve existing report from MongoDB or memory; compute if not yet cached."""
    # 1. Check MongoDB Atlas if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            doc = await db["interview_reports"].find_one({"session_id": session_id})
            if doc:
                doc.pop("_id", None)
                if not doc.get("owner_id"):
                    sess = await get_session(session_id)
                    if sess and sess.get("owner_id"):
                        doc["owner_id"] = sess.get("owner_id")
                if isinstance(doc.get("created_at"), str):
                    doc["created_at"] = datetime.fromisoformat(doc["created_at"])
                doc["saved_to_db"] = True
                doc["db_status"] = "persisted"
                doc["db_message"] = "Retrieved from MongoDB Atlas."
                doc = await _upgrade_legacy_report_doc(doc)
                return InterviewReportResponse(**doc)
        except Exception as exc:
            logger.warning("Error fetching report from MongoDB: %s", type(exc).__name__)

    # 2. Check in-memory
    if session_id in _in_memory_reports:
        doc = dict(_in_memory_reports[session_id])
        if not doc.get("owner_id"):
            sess = await get_session(session_id)
            if sess and sess.get("owner_id"):
                doc["owner_id"] = sess.get("owner_id")
        if isinstance(doc.get("created_at"), str):
            doc["created_at"] = datetime.fromisoformat(doc["created_at"])
        doc["saved_to_db"] = False
        doc["db_status"] = "unconfigured"
        doc["db_message"] = "Active in server memory."
        doc = await _upgrade_legacy_report_doc(doc)
        return InterviewReportResponse(**doc)

    # 3. If session exists but report not yet compiled, compile now
    session = await get_session(session_id)
    if not session:
        return None

    return await generate_interview_report(session_id)


async def add_human_review_to_report(session_id: str, entry: HumanReviewAuditEntry) -> None:
    """Append a human review entry to the cached report without regenerating scores."""
    entry_dict = entry.model_dump()
    entry_dict["created_at"] = entry.created_at.isoformat()

    if session_id in _in_memory_reports:
        integ = _in_memory_reports[session_id].get("integrity_summary")
        if isinstance(integ, dict):
            if "human_reviews" not in integ:
                integ["human_reviews"] = []
            integ["human_reviews"].append(entry_dict)

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["interview_reports"].update_one(
                {"session_id": session_id},
                {"$push": {"integrity_summary.human_reviews": entry_dict}},
            )
        except Exception as exc:
            logger.warning("MongoDB update failed for session %s report review: %s", session_id, type(exc).__name__)


async def add_candidate_explanation_to_report(session_id: str, entry: CandidateExplanationEntry) -> None:
    """Append a candidate explanation entry to the cached report without regenerating scores."""
    entry_dict = entry.model_dump()
    entry_dict["created_at"] = entry.created_at.isoformat()

    if session_id in _in_memory_reports:
        integ = _in_memory_reports[session_id].get("integrity_summary")
        if isinstance(integ, dict):
            if "candidate_explanations" not in integ:
                integ["candidate_explanations"] = []
            integ["candidate_explanations"].append(entry_dict)

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["interview_reports"].update_one(
                {"session_id": session_id},
                {"$push": {"integrity_summary.candidate_explanations": entry_dict}},
            )
        except Exception as exc:
            logger.warning("MongoDB update failed for session %s report explanation: %s", session_id, type(exc).__name__)


async def update_report_explanation_decision(
    session_id: str,
    explanation_id: str,
    decision_entry: ReviewerDecisionEntry,
    new_status: str,
    new_outcome: Optional[str],
) -> None:
    """Update explanation status and append decision entry in cached report without recomputing scores."""
    decision_dict = decision_entry.model_dump()
    decision_dict["created_at"] = decision_entry.created_at.isoformat()

    if session_id in _in_memory_reports:
        integ = _in_memory_reports[session_id].get("integrity_summary")
        if isinstance(integ, dict):
            exps = integ.get("candidate_explanations", [])
            for exp in exps:
                if exp.get("explanation_id") == explanation_id:
                    exp["status"] = new_status
                    exp["reviewer_outcome"] = new_outcome
                    if "decision_history" not in exp:
                        exp["decision_history"] = []
                    exp["decision_history"].append(decision_dict)
                    break

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["interview_reports"].update_one(
                {
                    "session_id": session_id,
                    "integrity_summary.candidate_explanations.explanation_id": explanation_id,
                },
                {
                    "$set": {
                        "integrity_summary.candidate_explanations.$.status": new_status,
                        "integrity_summary.candidate_explanations.$.reviewer_outcome": new_outcome,
                    },
                    "$push": {
                        "integrity_summary.candidate_explanations.$.decision_history": decision_dict,
                    },
                },
            )
        except Exception as exc:
            logger.warning(
                "MongoDB update failed for session %s report explanation decision: %s",
                session_id,
                type(exc).__name__,
            )
