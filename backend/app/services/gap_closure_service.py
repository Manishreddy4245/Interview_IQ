"""
InterviewIQ — Closed-Loop Gap Closure & Traceable Evidence Reporting Service
Module 04, Checkpoint 4.

Provides deterministic post-interview competency status resolution based on persisted
candidate answers and evaluations, maintaining a verifiable evidence chain from resume
to live interview performance without score modification.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.schemas.report import ResumeSkillComparisonItem
from app.schemas.resume import ResumeAnalysisResult, SkillEvidenceItem, SkillEvidenceCategory
from app.services.skill_normalizer import (
    canonical_skill_key,
    normalize_skill_name,
    skills_match,
)
from app.services.gap_prioritizer import prioritize_skill_gaps, PrioritizedGapItem

logger = logging.getLogger("interviewiq.gap_closure_service")


def resolve_post_interview_status(
    item: SkillEvidenceItem,
    matching_q: Optional[Dict[str, Any]],
    answer_data: Optional[Dict[str, Any]],
    target_role: str,
) -> Tuple[str, str, str, str, bool, Optional[float], Optional[Dict[str, Any]], List[str], List[str]]:
    """
    Deterministic resolution of post-interview competency status based on actual persisted evidence.

    Rubric Alignment & Threshold Documentation:
    -------------------------------------------
    - Scale Normalization:
      Historical evaluations use a 10-point scale (1.0-10.0), while current evaluations use a
      100-point scale (0.0-100.0). If raw_score <= 10.0, it is scaled by 10.0 to normalize to percentage.
    - Demonstrated in Interview:
      Requires overall normalized score >= 70.0% AND passing all evaluated key criteria:
        * relevance >= 6.5 / 10.0 (ensures response directly addressed competency requirements)
        * technical_depth >= 6.5 / 10.0 (ensures candidate articulated implementation mechanics)
        * completeness >= 6.0 / 10.0 (ensures required question facets were covered)
      A high overall score CANNOT override a failed mandatory technical depth criterion.
    - Partially Demonstrated:
      Assigned when overall score is between 50.0% and 69.9%, OR when overall score >= 70.0% but
      one or more mandatory criteria (relevance < 6.5, depth < 6.5, completeness < 6.0) failed.
      Acknowledges foundational concept awareness while clearly flagging deficient criteria.
    - Requires Further Validation:
      Assigned when overall score < 50.0%, OR when an answer was submitted but evaluation is
      pending, incomplete, or failed.
      Explicit fairness guarantee: A low score is framed as insufficient technical depth in this
      specific response and does NOT imply personal candidate inability.
    - Not Assessed:
      Assigned when no interview question was targeted, or when a targeted question was unanswered.
      Original resume evidence is preserved and not overwritten.

    Limitation Disclosure:
    ----------------------
    These numerical thresholds (70%, 50%, 6.5/10) are calibrated against InterviewIQ's 5-dimensional
    scoring rubric (1-10) and standard engineering evaluation baselines. They serve as deterministic
    heuristic cutoffs rather than empirically validated psychometric thresholds.

    Returns:
        (interview_status, post_interview_status, status_rationale, details, requires_further_validation,
         eval_score, criterion_feedback, strengths, improvements)
    """
    q_num = matching_q.get("question_number", 1) if matching_q else None
    q_id = matching_q.get("id") if matching_q else None

    # Case 1: No interview question targeted this competency
    if not matching_q:
        req_val = bool(item.requires_interview_validation or item.is_expected_for_role)
        # Preserve legacy naming convention for resume skills not tested in session
        legacy_status = "Claimed in Resume (Not Evaluated in Session)"
        rationale = (
            f"Competency was not targeted by an interview question in this session. "
            f"Resume classification '{item.category.value if hasattr(item.category, 'value') else str(item.category)}' "
            "remains the active source of evidence."
        )
        details = "Skill was not evaluated in this interview session."
        return (legacy_status, "Not Assessed", rationale, details, req_val, None, None, [], [])

    # Case 2: Question was targeted, but candidate submitted no answer
    answer_text = (answer_data.get("answer_text") or "").strip() if answer_data else ""
    if not answer_text:
        rationale = (
            f"Question {q_num} ('{matching_q.get('text', '')[:60]}...') was targeted for this competency, "
            "but the candidate did not submit an answer."
        )
        details = f"Question {q_num} was unanswered in session."
        return ("Not Assessed", "Not Assessed", rationale, details, True, None, None, [], [])

    # Case 3: Answer was submitted, but evaluation is missing or incomplete
    eval_data = answer_data.get("evaluation") if answer_data else None
    if not eval_data or not isinstance(eval_data, dict) or eval_data.get("overall_score") is None:
        rationale = (
            f"Candidate submitted an answer for Question {q_num}, but evaluation is pending or could not be completed. "
            "Competency remains unverified."
        )
        details = f"Answer submitted for Question {q_num}; evaluation pending or unverified."
        return ("Requires Further Validation", "Requires Further Validation", rationale, details, True, None, None, [], [])

    # Case 4: Answer was evaluated
    raw_score = float(eval_data.get("overall_score", 0.0))
    # Normalize legacy 10-point scale to 100-point scale for thresholding
    score_pct = raw_score * 10.0 if raw_score <= 10.0 else raw_score

    crit_scores = eval_data.get("criterion_scores", {})
    strengths = eval_data.get("strengths", [])
    improvements = eval_data.get("areas_for_improvement", [])

    # Extract relevant criterion scores
    rel_score: Optional[float] = None
    tech_score: Optional[float] = None
    comp_score: Optional[float] = None

    if isinstance(crit_scores, dict):
        for k, v in crit_scores.items():
            s_val = v.get("score") if isinstance(v, dict) else getattr(v, "score", None)
            if s_val is not None:
                try:
                    f_val = float(s_val)
                    if k == "relevance":
                        rel_score = f_val
                    elif k == "technical_depth":
                        tech_score = f_val
                    elif k == "completeness":
                        comp_score = f_val
                except (ValueError, TypeError):
                    pass

    # Threshold 1: Demonstrated in Interview
    # Criteria: overall score >= 70 AND key criteria (relevance, depth) >= 6.5 (if present)
    criteria_passing = (
        (rel_score is None or rel_score >= 6.5)
        and (tech_score is None or tech_score >= 6.5)
        and (comp_score is None or comp_score >= 6.0)
    )

    if score_pct >= 70.0 and criteria_passing:
        status = "Demonstrated in Interview"
        rationale = (
            f"Evaluated in Question {q_num} with score {raw_score}/100. "
            "Evaluated answer demonstrated required technical depth and relevance, "
            "satisfying the evidence threshold."
        )
        details = f"Evaluated in Question {q_num} with score {raw_score}/100."
        return (status, status, rationale, details, False, raw_score, crit_scores, strengths, improvements)

    # Threshold 2: Partially Demonstrated
    # Criteria: 50.0 <= overall score < 70.0 OR overall score >= 70.0 but missed depth/completeness criteria
    if score_pct >= 50.0:
        status = "Partially Demonstrated"
        missed_crits = []
        if tech_score is not None and tech_score < 6.5:
            missed_crits.append(f"technical depth ({tech_score}/10)")
        if comp_score is not None and comp_score < 6.0:
            missed_crits.append(f"completeness ({comp_score}/10)")
        if rel_score is not None and rel_score < 6.5:
            missed_crits.append(f"relevance ({rel_score}/10)")

        missed_detail = f" Areas needing depth: {', '.join(missed_crits)}." if missed_crits else ""
        rationale = (
            f"Evaluated in Question {q_num} with score {raw_score}/100. "
            f"Demonstrated foundational concept awareness, but did not satisfy all evaluation criteria.{missed_detail}"
        )
        details = f"Evaluated in Question {q_num} with score {raw_score}/100; partially demonstrated."
        return (status, status, rationale, details, True, raw_score, crit_scores, strengths, improvements)

    # Threshold 3: Requires Further Validation
    # Criteria: score < 50.0 (note: low score is not proof of candidate inability)
    status = "Requires Further Validation"
    rationale = (
        f"Evaluated in Question {q_num} with score {raw_score}/100. "
        "Candidate response did not provide sufficient technical depth to substantiate practical competency. "
        "Further live validation or project-based assessment recommended. (Low score does not imply personal inability)."
    )
    details = f"Evaluated in Question {q_num} with score {raw_score}/100; additional practice recommended."
    return (status, status, rationale, details, True, raw_score, crit_scores, strengths, improvements)


def build_traceable_skill_comparisons(
    session: Dict[str, Any],
    resume_analysis: ResumeAnalysisResult,
) -> Tuple[List[ResumeSkillComparisonItem], int, int, int, int]:
    """
    Construct complete traceable closed-loop evidence items linking:
    Resume Analysis -> Role Competency -> Question -> Candidate Answer -> Evaluation -> Post-Interview Status.
    """
    target_role = resume_analysis.target_role
    questions = session.get("questions", [])
    answers = session.get("answers", {})

    # Benchmark importance map
    benchmark_map = {}
    if resume_analysis.target_role_benchmark:
        for comp in resume_analysis.target_role_benchmark.expected_competencies:
            benchmark_map[canonical_skill_key(comp.skill_name)] = comp.importance
            if comp.normalized_skill:
                benchmark_map[canonical_skill_key(comp.normalized_skill)] = comp.importance

    # Prioritized gaps map
    prioritized_gaps = prioritize_skill_gaps(resume_analysis)
    gap_map: Dict[str, PrioritizedGapItem] = {
        canonical_skill_key(g.skill_name): g
        for g in prioritized_gaps
    }
    for g in prioritized_gaps:
        if g.normalized_skill:
            gap_map[canonical_skill_key(g.normalized_skill)] = g

    items: List[ResumeSkillComparisonItem] = []
    seen_skills = set()

    for item in resume_analysis.skill_evaluations:
        s_key = canonical_skill_key(item.skill_name)
        if s_key in seen_skills:
            continue
        seen_skills.add(s_key)

        norm_skill = item.normalized_skill or normalize_skill_name(item.skill_name)
        role_importance = benchmark_map.get(s_key, "Core" if item.is_expected_for_role else "Recommended")
        prioritized_item = gap_map.get(s_key)

        # Match to exact question using canonical skills_match (strictly avoiding substring collisions)
        matching_q = None
        for q in questions:
            q_assessed = q.get("assessed_skill", "")
            q_norm = q.get("normalized_skill", "")
            if skills_match(item.skill_name, q_assessed) or (q_norm and skills_match(norm_skill, q_norm)):
                matching_q = q
                break

        # Look up candidate answer
        answer_data = None
        if matching_q:
            answer_data = answers.get(matching_q.get("id"))

        # Deterministic status resolution
        (
            interview_status,
            post_interview_status,
            status_rationale,
            details,
            requires_further_validation,
            eval_score,
            crit_feedback,
            strengths,
            improvements,
        ) = resolve_post_interview_status(
            item=item,
            matching_q=matching_q,
            answer_data=answer_data,
            target_role=target_role,
        )

        # Build candidate answer excerpt
        ans_excerpt = None
        ans_ref = None
        if answer_data and answer_data.get("answer_text"):
            raw_ans = answer_data["answer_text"].strip()
            ans_excerpt = (raw_ans[:140] + "...") if len(raw_ans) > 140 else raw_ans
            ans_ref = f"Session Answer Q{matching_q.get('question_number', 1)}"

        # Grounded resume excerpt
        resume_excerpt = item.source_excerpt or (item.evidence if item.is_source_grounded else None)

        cat_str = item.category.value if hasattr(item.category, "value") else str(item.category)

        items.append(
            ResumeSkillComparisonItem(
                skill_name=item.skill_name,
                normalized_skill=norm_skill,
                target_role=target_role,
                role_importance=role_importance,
                resume_evidence_category=cat_str,
                resume_evidence=item.evidence,
                resume_is_grounded=item.is_source_grounded,
                resume_source_excerpt=resume_excerpt,
                gap_priority_tier=prioritized_item.priority_tier if prioritized_item else None,
                selection_reason=prioritized_item.priority_reason if prioritized_item else None,
                question_id=matching_q.get("id") if matching_q else None,
                question_text=matching_q.get("text") if matching_q else None,
                candidate_answer_reference=ans_ref,
                candidate_answer_excerpt=ans_excerpt,
                evaluation_overall_score=eval_score,
                criterion_feedback=crit_feedback,
                strengths=strengths,
                areas_for_improvement=improvements,
                interview_status=interview_status,
                post_interview_status=post_interview_status,
                status_rationale=status_rationale,
                requires_further_validation=requires_further_validation,
                details=details,
            )
        )

    # Calculate status counts
    demonstrated_cnt = sum(1 for i in items if i.post_interview_status == "Demonstrated in Interview")
    partially_cnt = sum(1 for i in items if i.post_interview_status == "Partially Demonstrated")
    further_val_cnt = sum(1 for i in items if i.post_interview_status == "Requires Further Validation")
    unassessed_cnt = sum(1 for i in items if i.post_interview_status == "Not Assessed")

    return items, demonstrated_cnt, partially_cnt, further_val_cnt, unassessed_cnt
