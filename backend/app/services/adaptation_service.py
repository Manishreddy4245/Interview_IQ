import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
import groq

from app.core.config import settings
from app.core.groq_client import groq_manager
from app.schemas.interview import (
    QuestionItem,
    NextQuestionResponse,
    CompetencyStatus,
    CompetencySkillState,
    SessionCompetencyState,
)
from app.services.session_service import (
    get_session,
    append_session_question,
    compute_session_time_status,
)

logger = logging.getLogger("interviewiq.adaptation_service")

DIFFICULTY_TIERS = ["Easy", "Medium", "Hard"]

_session_locks: Dict[str, asyncio.Lock] = {}


def _get_session_lock(session_id: str) -> asyncio.Lock:
    """Return an asyncio Lock tied to the specific session to serialize next-question generation."""
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


def compute_session_competency_state(session: Dict[str, Any]) -> SessionCompetencyState:
    """
    Compute structured competency state across all session focus areas and questions.
    Uses exclusively actual questions, answers, and evaluations stored in the session.
    Does NOT invent competencies or hallucinate evidence.
    """
    session_id = session.get("session_id", "")
    focus_raw = session.get("focus_areas", "")
    focus_skills = [s.strip() for s in focus_raw.split(",") if s.strip()]

    questions = session.get("questions", [])
    answers = session.get("answers", {})

    # Collect all skill names from focus areas and question metadata
    skill_names: List[str] = list(focus_skills)
    for q in questions:
        q_skill = q.get("assessed_skill", "").strip()
        if q_skill and not any(s.lower() == q_skill.lower() for s in skill_names):
            skill_names.append(q_skill)

    skills_dict: Dict[str, CompetencySkillState] = {}
    total_evaluated_count = 0

    for skill in skill_names:
        matching_questions = [
            q for q in questions
            if q.get("assessed_skill", "").strip().lower() == skill.lower()
        ]

        evaluated_scores: List[float] = []
        evidence_snippets: List[str] = []

        for q in matching_questions:
            q_id = q.get("id")
            ans_record = answers.get(q_id, {})
            evaluation = ans_record.get("evaluation")
            if evaluation and evaluation.get("overall_score") is not None:
                evaluated_scores.append(float(evaluation["overall_score"]))
                total_evaluated_count += 1
                # Collect concrete evidence snippets from evaluation feedback
                strengths = evaluation.get("strengths", [])
                if strengths:
                    evidence_snippets.append(f"Strength: {strengths[0]}")
                improvements = evaluation.get("areas_for_improvement", [])
                if improvements:
                    evidence_snippets.append(f"Gap: {improvements[0]}")

        q_count = len(matching_questions)
        eval_count = len(evaluated_scores)

        if eval_count > 0:
            avg_score = round(sum(evaluated_scores) / eval_count, 1)
            latest_score = evaluated_scores[-1]
            if avg_score >= 60.0:
                skill_status = CompetencyStatus.DEMONSTRATED
            else:
                skill_status = CompetencyStatus.NEEDS_FURTHER_ASSESSMENT
            evidence_summary = "; ".join(evidence_snippets[:2]) if evidence_snippets else f"Average score: {avg_score}/100"
        elif q_count > 0:
            # Asked, but answer unsubmitted or unevaluated
            avg_score = None
            latest_score = None
            skill_status = CompetencyStatus.NEEDS_FURTHER_ASSESSMENT
            evidence_summary = f"Assessed in question but pending evaluated evidence."
        else:
            avg_score = None
            latest_score = None
            skill_status = CompetencyStatus.NOT_ASSESSED
            evidence_summary = None

        skills_dict[skill] = CompetencySkillState(
            skill_name=skill,
            status=skill_status,
            questions_evaluated=eval_count,
            average_score=avg_score,
            latest_score=latest_score,
            evidence_summary=evidence_summary,
        )

    current_difficulty = determine_adaptive_difficulty(session)

    return SessionCompetencyState(
        session_id=session_id,
        skills=skills_dict,
        current_difficulty=current_difficulty,
        total_evaluated_count=total_evaluated_count,
        updated_at=datetime.now(timezone.utc),
    )


def compute_adaptive_decision(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Compute deterministic adaptive decision and action using the ML Text Assessment Model
    refactored from Text_Assessment_Model.ipynb (Cell 45).
    """
    baseline_difficulty = session.get("difficulty", "Medium")
    questions = session.get("questions", [])
    answers = session.get("answers", {})

    latest_question = None
    latest_evaluation = None

    for q in reversed(questions):
        q_id = q.get("id")
        ans_record = answers.get(q_id, {})
        evaluation = ans_record.get("evaluation")
        if evaluation and evaluation.get("overall_score") is not None:
            latest_question = q
            latest_evaluation = evaluation
            break

    if not latest_question or not latest_evaluation:
        return None

    from app.services.text_assessment_service import text_assessment_service
    asked_topics = [
        q.get("assessed_skill") or q.get("topic")
        for q in questions
        if q.get("assessed_skill") or q.get("topic")
    ]
    return text_assessment_service.choose_next_action(
        question=latest_question,
        evaluation=latest_evaluation,
        asked_topics=asked_topics,
    )


def determine_adaptive_difficulty(session: Dict[str, Any]) -> str:
    """
    Deterministically adapt interview difficulty based on demonstrated evaluation evidence
    and the ML Text Assessment Model (choose_next_action from Cell 45).
    """
    baseline_difficulty = session.get("difficulty", "Medium")
    if baseline_difficulty not in DIFFICULTY_TIERS:
        baseline_difficulty = "Medium"

    decision = compute_adaptive_decision(session)
    if decision is None:
        return baseline_difficulty

    # Check for important unresolved weaknesses / criterion gaps before escalating to Hard
    questions = session.get("questions", [])
    answers = session.get("answers", {})
    latest_evaluated_score = float(decision.get("percentage", 0.0))
    latest_evaluation = None
    latest_question_difficulty = baseline_difficulty

    for q in reversed(questions):
        q_id = q.get("id")
        ans_record = answers.get(q_id, {})
        ev = ans_record.get("evaluation")
        if ev and ev.get("overall_score") is not None:
            latest_evaluation = ev
            latest_question_difficulty = q.get("difficulty", baseline_difficulty)
            break

    if latest_question_difficulty not in DIFFICULTY_TIERS:
        latest_question_difficulty = baseline_difficulty

    current_idx = DIFFICULTY_TIERS.index(latest_question_difficulty)

    # Deterministic adaptation policy:
    # >= 75.0 escalates difficulty (+1 tier)
    # < 50.0 de-escalates difficulty (-1 tier)
    # 50.0 to 74.9 maintains current difficulty
    if latest_evaluated_score >= 75.0:
        target_diff = DIFFICULTY_TIERS[min(len(DIFFICULTY_TIERS) - 1, current_idx + 1)]
    elif latest_evaluated_score < 50.0:
        target_diff = DIFFICULTY_TIERS[max(0, current_idx - 1)]
    else:
        target_diff = DIFFICULTY_TIERS[current_idx]

    has_unresolved_weakness = False
    if latest_evaluation:
        crit_scores = latest_evaluation.get("criterion_scores") or {}
        for c_key, c_val in crit_scores.items():
            c_score = None
            if isinstance(c_val, dict):
                c_score = c_val.get("score")
            elif isinstance(c_val, (int, float)):
                c_score = c_val
            if c_score is not None:
                if c_score <= 10:
                    if c_score <= 6:
                        has_unresolved_weakness = True
                        break
                elif c_score < 60:
                    has_unresolved_weakness = True
                    break

        areas = latest_evaluation.get("areas_for_improvement") or []
        if len(areas) >= 2 and latest_evaluated_score < 85.0:
            has_unresolved_weakness = True

    if target_diff == "Hard" and has_unresolved_weakness:
        return latest_question_difficulty

    return target_diff


def select_target_competency(session: Dict[str, Any], competency_state: SessionCompetencyState) -> str:
    """
    Select the optimal competency for the next question:
    1. Prioritize focus skills that have not yet been assessed (CompetencyStatus.NOT_ASSESSED).
    2. If all have been touched, target skills that need further assessment (CompetencyStatus.NEEDS_FURTHER_ASSESSMENT).
    3. Avoid testing the exact same skill as the immediately preceding question unless it is the sole focus area.
    """
    questions = session.get("questions", [])
    last_skill = questions[-1].get("assessed_skill", "").strip().lower() if questions else ""

    unassessed = [
        s.skill_name for s in competency_state.skills.values()
        if s.status == CompetencyStatus.NOT_ASSESSED
    ]
    if unassessed:
        # Choose first unassessed skill that isn't identical to last skill
        for s in unassessed:
            if s.lower() != last_skill:
                return s
        return unassessed[0]

    needs_further = [
        s.skill_name for s in competency_state.skills.values()
        if s.status == CompetencyStatus.NEEDS_FURTHER_ASSESSMENT
    ]
    if needs_further:
        for s in needs_further:
            if s.lower() != last_skill:
                return s
        return needs_further[0]

    # If all skills demonstrated, rotate through skills
    all_skills = list(competency_state.skills.keys())
    for s in all_skills:
        if s.lower() != last_skill:
            return s
    return all_skills[0] if all_skills else session.get("role", "Core Competency")


def is_duplicate_question(new_text: str, existing_questions: List[Dict[str, Any]]) -> bool:
    """
    Check if the candidate question text is functionally identical or semantically duplicate
    of any previously asked question in the session using the SentenceTransformer neural model.
    """
    if not new_text or not new_text.strip():
        return False

    norm_new = " ".join(new_text.strip().lower().split())

    for eq in existing_questions:
        eq_text = eq.get("text", "")
        if not eq_text:
            continue
        norm_existing = " ".join(eq_text.strip().lower().split())

        # Exact match
        if norm_new == norm_existing:
            return True

        # Substring containment for questions of substantial length
        if len(norm_new) > 30 and (norm_new in norm_existing or norm_existing in norm_new):
            return True

    # Neural semantic duplicate check using SentenceTransformer ("all-MiniLM-L6-v2") and cosine similarity
    try:
        from app.services.text_assessment_service import text_assessment_service
        semantic_res = text_assessment_service.find_semantic_duplicate(
            candidate_question=new_text,
            history=existing_questions,
            threshold=0.78,
        )
        if semantic_res.get("is_duplicate"):
            logger.info(
                "Neural semantic duplicate detected (similarity=%.4f, matched='%s')",
                semantic_res.get("similarity", 0.0),
                str(semantic_res.get("matched_question", ""))[:60],
            )
            return True
    except Exception as exc:
        logger.warning("Neural semantic duplicate check encountered error: %s", str(exc))

    return False


def generate_time_aware_fallback_question(
    skill: str,
    difficulty: str,
    time_band: str,
    next_q_id: str,
    next_q_number: int,
    existing_questions: List[Dict[str, Any]],
    role: str = "Software Engineer",
    job_description: Optional[str] = None,
    session_mode: str = "VERBAL",
) -> QuestionItem:
    """
    Deterministically generate a high-quality, time-aware fallback question if AI generation
    yields a duplicate or unparseable output.
    Tailored strictly to the requested competency, difficulty tier, time band, and session_mode constraint.
    """
    skill_clean = skill.strip()
    s_mode = session_mode.upper() if session_mode else "VERBAL"

    if s_mode == "CODING":
        from app.core.problem_catalog import BENCHMARK_PROBLEMS
        from app.core.topic_validator import validate_question_topic

        existing_texts = [q.get("text", "").lower() for q in existing_questions]
        existing_titles = [q.get("title", "").lower() for q in existing_questions if q.get("title")]

        candidate_bm = None
        for bm_key, bm_val in BENCHMARK_PROBLEMS.items():
            if bm_val.get("question_type") == "coding":
                is_valid_topic, _ = validate_question_topic(bm_val, [skill_clean])
                if is_valid_topic:
                    bm_title = (bm_val.get("title") or "").lower()
                    if not any(bm_title in et for et in existing_titles) and not any(bm_title in et for et in existing_texts):
                        candidate_bm = bm_val
                        break

        if not candidate_bm:
            for bm_key, bm_val in BENCHMARK_PROBLEMS.items():
                if bm_val.get("question_type") == "coding":
                    is_valid_topic, _ = validate_question_topic(bm_val, [skill_clean])
                    if is_valid_topic:
                        candidate_bm = bm_val
                        break

        if not candidate_bm:
            logger.warning(
                "No benchmark problem matches topic constraint '%s'. Refusing to substitute unrelated problem.",
                skill_clean,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unable to generate or find a fallback coding challenge satisfying topic constraint '{skill_clean}'. Never substituting an unrelated problem.",
            )

        bm_copy = dict(candidate_bm)
        bm_copy["id"] = next_q_id
        bm_copy["question_number"] = next_q_number
        bm_copy["time_band"] = time_band
        bm_copy["difficulty"] = difficulty
        bm_copy["assessed_skill"] = skill_clean
        bm_copy["selection_rationale"] = (
            f"Coding challenge selected to evaluate algorithmic problem-solving for '{skill_clean}' at {difficulty} tier."
        )
        if not bm_copy.get("text"):
            bm_title = bm_copy.get("title", "Coding Problem")
            in_fmt = bm_copy.get("input_format", "")
            out_fmt = bm_copy.get("output_format", "")
            bm_copy["text"] = f"Implement the function `{bm_copy.get('function_name', 'solution')}` for {bm_title}. Input: {in_fmt}. Output: {out_fmt}."
        if not bm_copy.get("rubric"):
            bm_copy["rubric"] = "Algorithmic correctness, edge case handling, and time/space complexity."
        q = QuestionItem.model_validate(bm_copy)
        q.ensure_classification_and_modes(session_mode="CODING")
        return q

    if time_band == "concise":
        templates = [
            (
                f"In 2 to 3 minutes, succinctly explain the core architectural purpose of {skill_clean} and identify one primary anti-pattern to avoid when using it.",
                f"Concise conceptual precision, identification of valid anti-pattern, structured brief delivery."
            ),
            (
                f"What is the single most critical trade-off when implementing {skill_clean} in production? Provide a specific 1-minute example.",
                f"Clear articulation of primary trade-off (performance, maintainability, or latency) and concise real-world example."
            ),
            (
                f"How would you quickly diagnose a latency or concurrency bottleneck in a component utilizing {skill_clean}?",
                f"Rapid diagnostic triage steps, tooling reference, and targeted remediation approach."
            ),
        ]
        rationale_time = "Kept concise and single-focused due to less than 5 minutes remaining in the interview."
    elif time_band == "focused":
        templates = [
            (
                f"Walk through how you would handle fault tolerance, edge cases, and error recovery within {skill_clean} at a {difficulty} level. What concrete trade-offs do you balance?",
                f"Identifies realistic error scenarios, discusses fallback mechanisms, and justifies architectural trade-offs."
            ),
            (
                f"When scaling an application relying on {skill_clean}, what are the primary throughput bottlenecks and how do you optimize them?",
                f"Discusses bottleneck analysis, profiling techniques, caching/pooling strategies, and benchmark measurements."
            ),
            (
                f"Compare two alternative design approaches for implementing {skill_clean} in a {role} context. In what scenario would you choose each?",
                f"Structured comparison covering scalability, developer ergonomics, operational complexity, and decision criteria."
            ),
        ]
        rationale_time = "Focused on core trade-offs and unresolved competency gaps tailored for the 5-10 minute window."
    else:  # comprehensive
        templates = [
            (
                f"Design a robust, end-to-end architecture leveraging {skill_clean} for a high-availability production service. Explain your data flow, state management, and isolation boundaries at {difficulty} depth.",
                f"Comprehensive architectural breakdown, component interactions, scalability strategies, operational monitoring, and resilience."
            ),
            (
                f"In the context of modern {role} systems, how do you architect and evolve systems utilizing {skill_clean} to maintain backwards compatibility, zero downtime, and strict performance SLAs?",
                f"In-depth discussion of migration strategies, SLA monitoring, contract versioning, testing regimes, and deployment patterns."
            ),
            (
                f"Deep-dive into the internal execution model and lifecycle of {skill_clean}. How does runtime behavior differ between {difficulty} edge cases and standard usage?",
                f"Deep technical accuracy regarding runtime mechanics, memory/concurrency behavior, edge-case mitigation, and defensive coding."
            ),
        ]
        rationale_time = "Comprehensive architectural depth exploring end-to-end design with more than 10 minutes remaining."

    selected_text = ""
    selected_rubric = ""
    for text_candidate, rubric_candidate in templates:
        if not is_duplicate_question(text_candidate, existing_questions):
            selected_text = text_candidate
            selected_rubric = rubric_candidate
            break

    if not selected_text:
        selected_text = f"Analyze an advanced scenario in {skill_clean} for a {role} role (Scenario {next_q_number}): how do you ensure high performance, security, and maintainability under {difficulty} constraints?"
        selected_rubric = f"Demonstrates structured problem decomposition for {skill_clean}, clear reasoning, and technical depth."

    jd_note = " aligned with target role requirements" if job_description else ""
    rationale = f"Selected to assess competency '{skill_clean}' at {difficulty} difficulty{jd_note}. {rationale_time}"

    q = QuestionItem(
        id=next_q_id,
        question_number=next_q_number,
        text=selected_text,
        assessed_skill=skill_clean,
        difficulty=difficulty,
        rubric=selected_rubric,
        selection_rationale=rationale,
        time_band=time_band,
    )
    q.ensure_classification_and_modes(session_mode="VERBAL")
    return q


async def generate_next_adaptive_question(
    session_id: str,
    client_remaining_seconds: Optional[int] = None,
    current_session: Optional[Dict[str, Any]] = None,
) -> NextQuestionResponse:
    """
    Generate the next-best question dynamically using candidate's prior answers,
    evaluation evidence, and authoritative session timing.
    Serializes requests per session to prevent race conditions.
    """
    async with _get_session_lock(session_id):
        return await _generate_next_adaptive_question_locked(
            session_id,
            client_remaining_seconds=client_remaining_seconds,
            current_session=current_session,
        )


async def _generate_next_adaptive_question_locked(
    session_id: str,
    client_remaining_seconds: Optional[int] = None,
    current_session: Optional[Dict[str, Any]] = None,
) -> NextQuestionResponse:
    # 1. Fetch session (reuse provided current_session to avoid redundant DB round-trip)
    session = current_session or await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    # 2. Check session status
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

    session_mode = (session.get("interview_mode") or "VERBAL").upper()
    if session_mode not in ("CODING", "VERBAL"):
        session_mode = "VERBAL"

    # 3. Check authoritative session timing & expiry
    time_status = compute_session_time_status(session, client_hint_seconds=client_remaining_seconds)
    if time_status["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session has expired. No further questions can be generated.",
        )

    effective_remaining = time_status["effective_remaining_seconds"]
    time_band = time_status["time_band"]
    remaining_minutes = max(0.1, round(effective_remaining / 60, 1))

    existing_questions = session.get("questions", [])
    target_count = session.get("target_question_count", session.get("question_count", 3))

    if len(existing_questions) >= target_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Interview session has already reached its target question count ({target_count}). "
                "You may complete the session and view the final decision report."
            ),
        )

    # 4. Compute competency state, adapted difficulty, and target skill strictly constrained by Focus Areas
    from app.core.topic_validator import (
        parse_focus_area_topics,
        validate_question_topic,
        select_next_topic_from_focus_areas,
    )
    from app.services.oracle_service import verify_and_repair_coding_question
    from app.core.problem_catalog import BENCHMARK_PROBLEMS

    focus_areas_str = session.get("focus_areas", "")
    allowed_topics = parse_focus_area_topics(focus_areas_str) if focus_areas_str else []

    competency_state = compute_session_competency_state(session)
    adapted_difficulty = determine_adaptive_difficulty(session)

    if allowed_topics:
        covered_topics = [
            q.get("assessed_skill") or q.get("topic") or ""
            for q in existing_questions
            if q.get("assessed_skill") or q.get("topic")
        ]
        target_skill = select_next_topic_from_focus_areas(allowed_topics, covered_topics)
    else:
        target_skill = select_target_competency(session, competency_state)

    next_q_number = len(existing_questions) + 1
    next_q_id = f"q_{next_q_number}"

    # 5. Check Groq credentials
    if not settings.is_groq_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Groq API key is not configured. Please provide GROQ_API_KEY in backend/.env "
                "to generate adaptive interview questions."
            ),
        )

    try:
        client = groq_manager.get_client()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to initialize Groq client: {type(exc).__name__}",
        ) from exc

    # 6. Build context from prior questions, submitted answers, evaluations, and job description
    role = session.get("role", "Software Engineer")
    experience_level = session.get("experience_level", "Mid-Level")
    job_description = session.get("job_description")

    prior_context_items = []
    answers = session.get("answers", {})

    for idx, q in enumerate(existing_questions, 1):
        q_id = q.get("id")
        q_skill = q.get("assessed_skill", "Unknown")
        q_diff = q.get("difficulty", "Unknown")
        q_text = q.get("text", "")

        ans_data = answers.get(q_id, {})
        evaluation = ans_data.get("evaluation") or {}

        answer_text = (
            ans_data.get("answer_text")
            or ans_data.get("code")
            or ans_data.get("sql_query")
            or ""
        )

        score = evaluation.get("overall_score")
        score_str = (
            f"{score}/100" if score is not None else "Not evaluated"
        )

        strengths = evaluation.get("strengths") or []
        improvements = evaluation.get("areas_for_improvement") or []
        suggestions = evaluation.get("actionable_suggestions") or []
        coaching = evaluation.get("coaching_summary") or ""
        criterion_scores = evaluation.get("criterion_scores") or {}

        evidence_parts = []
        if criterion_scores:
            crit_parts = []
            for c_k, c_v in criterion_scores.items():
                c_sc = c_v.get("score") if isinstance(c_v, dict) else c_v
                if c_sc is not None:
                    crit_parts.append(f"{c_k}: {c_sc}")
            if crit_parts:
                evidence_parts.append("Criterion scores: " + ", ".join(crit_parts[:6]))

        if strengths:
            evidence_parts.append("Strengths: " + "; ".join(str(x) for x in strengths[:2]))
        if improvements:
            evidence_parts.append("Improvement gaps: " + "; ".join(str(x) for x in improvements[:3]))
        if coaching:
            evidence_parts.append("Evaluation summary: " + str(coaching)[:200])

        evidence = " | ".join(evidence_parts) or "No evaluation feedback available"
        candidate_ans_display = (
            answer_text[:300]
            if answer_text
            else "No candidate answer text stored."
        )

        prior_context_items.append(
            f"- Q{idx} | Skill: {q_skill} | Difficulty: {q_diff}\n"
            f"  Question: {q_text[:200]}\n"
            f"  Candidate answer: {candidate_ans_display}\n"
            f"  Score: {score_str}\n"
            f"  Evaluation evidence: {evidence[:350]}"
        )

    prior_summary = (
        "\n".join(prior_context_items)
        if prior_context_items
        else "No previous questions in this session."
    )

    if time_band == "concise":
        time_band_instruction = (
            "TIME CONSTRAINT: Less than 5 minutes remaining ('concise' band).\n"
            "- Generate a concise, single-focus question assessing a critical core concept, scenario, or mechanism.\n"
            "- The question MUST be focused enough to be reasonably answered by the candidate in 2 to 3 minutes.\n"
            "- Avoid multi-part prompts or sprawling architectural design scenarios."
        )
        rationale_time_guidance = f"concise single-focus format for under 5 minutes remaining (~{remaining_minutes} min left)"
    elif time_band == "focused":
        time_band_instruction = (
            "TIME CONSTRAINT: Between 5 and 10 minutes remaining ('focused' band).\n"
            "- Prefer focused questions that efficiently assess unresolved competencies and core trade-offs.\n"
            "- Keep the scope targeted on specific mechanisms, decision rationale, or edge cases rather than broad open-ended exploration."
        )
        rationale_time_guidance = f"focused scope for the 5-10 minute time window (~{remaining_minutes} min left)"
    else:
        time_band_instruction = (
            "TIME CONSTRAINT: More than 10 minutes remaining ('comprehensive' band).\n"
            "- Retain comprehensive competency-driven adaptive depth exploring architecture, design trade-offs, and practical reasoning."
        )
        rationale_time_guidance = f"comprehensive depth with more than 10 minutes remaining (~{remaining_minutes} min left)"

    evidence_adaptation_instruction = (
        "ADAPTATION RULES BASED ON ACTUAL EVALUATION EVIDENCE:\n"
        "1. Read prior candidate answers and evaluation feedback before selecting the next question.\n"
        "2. Use explicitly recorded improvement gaps to target concepts that need further assessment.\n"
        "3. If performance is strong, increase depth according to the adapted difficulty.\n"
        "4. If performance is weak, test foundational understanding at the adapted difficulty.\n"
        "5. Do not claim a concept is missing unless prior answers or evaluation feedback support it.\n"
        "6. Do not repeat a prior question or test the same knowledge in nearly the same way.\n"
        "7. Preserve the session's interview mode and the required question format.\n"
    )

    jd_context_str = ""
    if job_description and job_description.strip():
        jd_context_str = f"\nTARGET JOB DESCRIPTION CONTEXT:\n\"{job_description.strip()}\"\n(Incorporate relevant requirements where applicable; do NOT invent unstated requirements.)\n"

    # 7. Groq Prompts strictly branched by session_mode
    if session_mode == "CODING":
        system_prompt = (
            "You are an expert technical coding interviewer. "
            "Generate the SINGLE NEXT BEST executable LeetCode-style algorithmic coding challenge for the IDE.\n"
            f"{time_band_instruction}\n\n"
            f"{evidence_adaptation_instruction}\n"
            "CRITICAL RULES FOR CODING MODE:\n"
            f"1. Target DSA competency: '{target_skill}' at adapted difficulty '{adapted_difficulty}'.\n"
            f"   CRITICAL TOPIC CONSTRAINT: The problem MUST be strictly focused on '{target_skill}'.\n"
            f"   The underlying algorithmic approach must inherently require '{target_skill}' "
            f"   (e.g., recursive subproblem decomposition for recursion). Do NOT generate unrelated problems (e.g., array lookup or Two Sum).\n"
            "2. MUST be an executable programming challenge with a specific function to implement.\n"
            "3. Provide function_name, input_format, output_format, constraints, examples, test_cases, AND reference_solution.\n"
            "4. 'reference_solution' MUST be a complete, optimal, bug-free Python 3 implementation inside `class Solution` implementing `function_name`.\n"
            + (
                f"   For '{target_skill}', 'reference_solution' MUST genuinely use recursive problem decomposition (base cases and recursive step).\n"
                if "recursion" in target_skill.lower()
                else ""
            )
            + "5. Strictly NEVER generate verbal discussion questions or conceptual essays.\n"
            "6. DO NOT duplicate, rephrase, or re-ask any previously asked question.\n"
            "7. 'question_type' MUST be 'coding'.\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            f'  "id": "{next_q_id}",\n'
            f'  "question_number": {next_q_number},\n'
            '  "title": "Problem Title",\n'
            '  "text": "Detailed algorithmic problem description...",\n'
            f'  "assessed_skill": "{target_skill}",\n'
            f'  "difficulty": "{adapted_difficulty}",\n'
            '  "rubric": "Correctness across edge cases, algorithm efficiency, and code organization",\n'
            '  "question_type": "coding",\n'
            '  "function_name": "functionName",\n'
            '  "input_format": "Input parameters description",\n'
            '  "output_format": "Return type description",\n'
            '  "constraints": ["Constraint 1"],\n'
            '  "examples": [{"example_number": 1, "input": "...", "output": "...", "explanation": "..."}],\n'
            '  "test_cases": [\n'
            '    {"id": "tc_1", "input": "...", "expected_output": "...", "is_hidden": false}\n'
            '  ],\n'
            '  "reference_solution": "class Solution:\\n    def functionName(self, ...):\\n        ...",\n'
            '  "selection_rationale": "Transparent explanation of why this coding problem was selected based on candidate performance and competency coverage.",\n'
            f'  "time_band": "{time_band}"\n'
            "}\n"
            "Do not include conversational preamble, markdown fences, or text outside the JSON object."
        )
        user_prompt = (
            f"INTERVIEW CONTEXT (CODING MODE):\n"
            f"- Target Role: {role}\n"
            f"- Experience Level: {experience_level}\n"
            f"- Target Competency to Assess: {target_skill}\n"
            f"- Allowed Focus Topics: {', '.join(allowed_topics) if allowed_topics else target_skill}\n"
            f"- Adapted Target Difficulty: {adapted_difficulty}\n"
            f"- Time Constraint: {time_band.capitalize()} band ({effective_remaining}s remaining, ~{remaining_minutes} min)\n"
            f"- Question Index: Question {next_q_number} of {target_count}\n"
            f"{jd_context_str}\n"
            f"PRIOR QUESTIONS IN THIS SESSION (DO NOT DUPLICATE THESE):\n"
            f"{prior_summary}\n\n"
            f"Generate Question {next_q_number} strictly focused on '{target_skill}' with an executable coding problem for the {time_band} time band."
        )
    else:
        system_prompt = (
            "You are an expert technical interviewer and adaptive assessment engine. "
            "Your task is to generate the SINGLE NEXT BEST verbal interview question tailored to the candidate's "
            "demonstrated answers, evidence gaps, adapted difficulty level, and remaining interview time.\n\n"
            f"{time_band_instruction}\n\n"
            f"{evidence_adaptation_instruction}\n"
            "CRITICAL RULES FOR VERBAL MODE:\n"
            f"1. Focus specifically on target competency: '{target_skill}' at adapted difficulty '{adapted_difficulty}'.\n"
            "2. MUST be answerable through spoken or written natural language explanation.\n"
            "3. You MUST NEVER ask the candidate to write, execute, or submit code.\n"
            "4. Do NOT provide test cases, starter code templates, or function stubs.\n"
            "5. DO NOT duplicate, rephrase, or re-ask any previously asked question.\n"
            "6. 'question_type' MUST be 'verbal' (or 'system_design').\n"
            "Return ONLY a valid JSON object matching this exact schema:\n"
            "{\n"
            f'  "id": "{next_q_id}",\n'
            f'  "question_number": {next_q_number},\n'
            '  "text": "Full question text...",\n'
            f'  "assessed_skill": "{target_skill}",\n'
            f'  "difficulty": "{adapted_difficulty}",\n'
            '  "rubric": "Concrete criteria and indicators for an exemplary answer",\n'
            '  "question_type": "verbal",\n'
            '  "selection_rationale": "Transparent explanation of why this question was selected based on candidate performance and competency coverage.",\n'
            f'  "time_band": "{time_band}"\n'
            "}\n"
            "Do not include conversational preamble, markdown fences, or text outside the JSON object."
        )
        user_prompt = (
            f"INTERVIEW CONTEXT (VERBAL MODE):\n"
            f"- Target Role: {role}\n"
            f"- Experience Level: {experience_level}\n"
            f"- Target Competency to Assess: {target_skill}\n"
            f"- Allowed Focus Topics: {', '.join(allowed_topics) if allowed_topics else target_skill}\n"
            f"- Adapted Target Difficulty: {adapted_difficulty}\n"
            f"- Time Constraint: {time_band.capitalize()} band ({effective_remaining}s remaining, ~{remaining_minutes} min)\n"
            f"- Question Index: Question {next_q_number} of {target_count}\n"
            f"{jd_context_str}\n"
            f"PRIOR QUESTIONS IN THIS SESSION (DO NOT DUPLICATE THESE):\n"
            f"{prior_summary}\n\n"
            f"Generate Question {next_q_number} addressing unresolved evidence in '{target_skill}' with appropriate depth for the {time_band} time band."
        )

    max_adaptive_attempts = 3
    last_adaptive_error: Optional[str] = None
    final_q_data: Optional[Dict[str, Any]] = None

    for attempt in range(max_adaptive_attempts):
        current_u_prompt = user_prompt
        if attempt > 0 and last_adaptive_error:
            current_u_prompt += f"\n\nPREVIOUS ATTEMPT REJECTED: {last_adaptive_error}. Generate a challenge strictly for '{target_skill}'."

        raw_content = await groq_manager.execute_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": current_u_prompt},
            ],
            temperature=0.35 + (attempt * 0.1),
            max_tokens=1100 if session_mode == "CODING" else 750,
            timeout=25.0,
            reasoning_effort="low",
        )

        try:
            q_data = json.loads(raw_content)
        except Exception as exc:
            last_adaptive_error = f"invalid JSON: {type(exc).__name__}"
            continue

        q_data["id"] = next_q_id
        q_data["question_number"] = next_q_number
        q_data["difficulty"] = adapted_difficulty
        q_data["time_band"] = time_band
        q_data["assessed_skill"] = target_skill

        # Duplicate Question Prevention (Exact + Neural Semantic)
        if is_duplicate_question(q_data.get("text", ""), existing_questions):
            last_adaptive_error = "Question was duplicate of previously asked question in session."
            continue

        if session_mode == "CODING":
            if allowed_topics:
                is_valid_topic, topic_err = validate_question_topic(q_data, allowed_topics)
                if not is_valid_topic:
                    last_adaptive_error = topic_err
                    logger.warning("Adaptive generation attempt %d failed topic constraint: %s", attempt + 1, topic_err)
                    continue

            v_dict = await verify_and_repair_coding_question(q_data)
            if v_dict.get("quarantined"):
                last_adaptive_error = f"Oracle verification quarantined question: {v_dict.get('validation_error')}"
                logger.warning("Adaptive question quarantined by oracle on attempt %d: %s", attempt + 1, v_dict.get("validation_error"))
                continue

            final_q_data = v_dict
            break
        else:
            final_q_data = q_data
            break

    if not final_q_data:
        # Check if an existing benchmark problem matches the allowed topic set
        matching_bm = None
        for bm_k, bm_v in BENCHMARK_PROBLEMS.items():
            valid_bm, _ = validate_question_topic(bm_v, allowed_topics if allowed_topics else [target_skill])
            if valid_bm:
                bm_title = (bm_v.get("title") or "").lower()
                existing_titles = [eq.get("title", "").lower() for eq in existing_questions if eq.get("title")]
                if not any(bm_title in et for et in existing_titles):
                    matching_bm = (bm_k, bm_v)
                    break

        if matching_bm:
            fallback_key, bm_v = matching_bm
            bench_data = dict(bm_v)
            bench_data["id"] = next_q_id
            bench_data["question_number"] = next_q_number
            bench_data["difficulty"] = adapted_difficulty
            bench_data["assessed_skill"] = target_skill
            bench_data["oracle_verified"] = True
            bench_data["oracle_provenance"] = "benchmark_catalog_fallback"
            bench_data["selection_rationale"] = f"Adaptive challenge matched to candidate focus topic '{target_skill}'."
            bench_data["time_band"] = time_band
            final_q_data = bench_data
        else:
            logger.error("Failed to generate adaptive question for %s: %s", allowed_topics or target_skill, last_adaptive_error)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"Unable to dynamically generate an adaptive coding problem strictly satisfying topic constraints: "
                    f"'{', '.join(allowed_topics) if allowed_topics else target_skill}'. "
                    f"Rejection reason: {last_adaptive_error or 'Topic validation failed'}."
                ),
            )

    q_data = final_q_data

    # Extract concept metadata (concept, angle)
    if session_mode == "VERBAL":
        q_data["concept"] = q_data.get("concept") or target_skill
        q_data["angle"] = q_data.get("angle") or "Core principles and trade-offs"

    # Attach ML adaptive decision metadata
    adaptive_dec = compute_adaptive_decision(session)
    if adaptive_dec:
        q_data["adaptive_action"] = adaptive_dec.get("action")
        q_data["adaptive_reason"] = adaptive_dec.get("reason")

    # Ensure transparent selection rationale preserves AI reasoning and includes time constraint
    current_rationale = (q_data.get("selection_rationale") or "").strip()
    time_marker = time_band.lower()
    if not current_rationale:
        q_data["selection_rationale"] = (
            f"Selected to evaluate competency '{target_skill}' at adapted '{adapted_difficulty}' difficulty; "
            f"structured with {rationale_time_guidance}."
        )
    elif time_marker not in current_rationale.lower() and "minute" not in current_rationale.lower():
        q_data["selection_rationale"] = (
            f"{current_rationale} [{time_band.capitalize()} band: ~{remaining_minutes}m remaining]."
        )

    try:
        new_question = QuestionItem.model_validate(q_data)
        new_question.ensure_classification_and_modes(session_mode=session_mode)
    except Exception as exc:
        logger.error("QuestionItem validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Generated adaptive question did not meet schema constraints: {str(exc)}",
        ) from exc

    # 8. Persist to session
    updated_session = await append_session_question(session_id, new_question, current_session=session)

    # 9. Re-compute competency state
    updated_competency = compute_session_competency_state(updated_session)

    is_last = (next_q_number >= target_count)

    return NextQuestionResponse(
        session_id=session_id,
        question=new_question,
        active_question_id=new_question.id,
        current_difficulty=adapted_difficulty,
        question_number=next_q_number,
        target_question_count=target_count,
        is_last_question=is_last,
        competency_state=updated_competency,
        time_remaining_seconds=effective_remaining,
        time_band=time_band,
        saved_to_db=updated_session.get("saved_to_db", False),
        db_status=updated_session.get("db_status", "unconfigured"),
        db_message=updated_session.get("db_message"),
        adaptive_decision=adaptive_dec,
    )
