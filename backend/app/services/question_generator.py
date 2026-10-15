import json
import logging
from typing import List
from fastapi import HTTPException, status
import groq
from app.core.config import settings
from app.core.groq_client import groq_manager
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    AIQuestionList,
)

logger = logging.getLogger("interviewiq.question_generator")


async def generate_adaptive_questions(setup: InterviewSetupRequest) -> List[QuestionItem]:
    """
    Generate interview questions via Groq LLM using structured JSON output.
    Validates output structure and question count using Pydantic.
    Does NOT use mock questions or fake fallbacks.
    """
    # 1. Verify Groq credentials
    if not settings.is_groq_configured:
        logger.error("Question generation requested but GROQ_API_KEY is not configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Groq API key is not configured. Please provide GROQ_API_KEY in the backend "
                "environment to generate interview questions."
            ),
        )

    # 2. Get client
    try:
        client = groq_manager.get_client()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to initialize Groq client: {type(exc).__name__}",
        ) from exc

    mode = (getattr(setup, "interview_mode", None) or "VERBAL").strip().upper()
    if mode not in ("CODING", "VERBAL"):
        mode = "VERBAL"

    # 3. Construct system prompt and user specification branched strictly by mode
    if mode == "CODING":
        system_prompt = (
            "You are an expert technical coding interviewer. "
            "Your task is to generate realistic, executable LeetCode-style algorithmic coding challenges "
            "tailored to the candidate's target role, experience level, difficulty, and focus areas.\n"
            "CRITICAL RULES FOR CODING MODE:\n"
            "1. Every question MUST be an executable programming problem with a specific function to implement.\n"
            "2. Provide function_name, input_format, output_format, constraints, examples, test_cases, AND reference_solution.\n"
            "3. 'reference_solution' MUST be a complete, optimal, bug-free Python 3 implementation inside `class Solution` implementing `function_name`.\n"
            "4. You MUST NEVER generate open-ended verbal discussion questions, behavioral prompts, or conceptual essays.\n"
            "5. 'question_type' MUST be 'coding'.\n"
            "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "id": "q_1",\n'
            '      "question_number": 1,\n'
            '      "title": "Problem Title",\n'
            '      "text": "Detailed algorithmic problem description...",\n'
            '      "assessed_skill": "Data Structures & Algorithms",\n'
            '      "difficulty": "Easy|Medium|Hard",\n'
            '      "rubric": "Correctness across edge cases, time/space complexity, clean algorithm structure",\n'
            '      "question_type": "coding",\n'
            '      "function_name": "functionName",\n'
            '      "input_format": "`nums`: integer array, `target`: integer",\n'
            '      "output_format": "Return array of indices",\n'
            '      "constraints": ["1 <= nums.length <= 10^4"],\n'
            '      "examples": [{"example_number": 1, "input": "...", "output": "...", "explanation": "..."}],\n'
            '      "test_cases": [\n'
            '        {"id": "tc_1", "input": "...", "expected_output": "...", "is_hidden": false}\n'
            '      ],\n'
            '      "reference_solution": "class Solution:\\n    def functionName(self, ...):\\n        ..."\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Do not include conversational filler, markdown fences, or text outside the JSON object."
        )
        user_prompt = (
            f"Generate exactly {setup.question_count} algorithmic coding interview problems for candidate profile:\n"
            f"- Target Role: {setup.role}\n"
            f"- Experience Level: {setup.experience_level}\n"
            f"- Difficulty Level: {setup.difficulty}\n"
            f"- Focus Areas & DSA Skills: {setup.focus_areas}\n\n"
            "Ensure each problem requires code implementation in an IDE with automated test cases. "
            "Assign sequential IDs ('q_1', 'q_2', ...) and accurate question numbers."
        )
    else:
        system_prompt = (
            "You are an expert technical verbal/spoken interviewer and communication coach. "
            "Your task is to generate realistic, insightful verbal interview questions about "
            "technical concepts, architecture, project experience, behavioral scenarios, and trade-offs "
            "tailored to the candidate's target role, experience level, difficulty, and focus areas.\n"
            "CRITICAL RULES FOR VERBAL MODE:\n"
            "1. Every question MUST be answerable through spoken or written natural language explanation.\n"
            "2. You MUST NEVER ask the candidate to write, execute, or submit source code or functions.\n"
            "3. Do NOT provide test cases, starter code templates, or function stubs.\n"
            "4. 'question_type' MUST be 'verbal' (or 'system_design' for architecture).\n"
            "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "id": "q_1",\n'
            '      "question_number": 1,\n'
            '      "text": "Full verbal question text...",\n'
            '      "assessed_skill": "Assessed technical capability or communication",\n'
            '      "difficulty": "Easy|Medium|Hard",\n'
            '      "rubric": "Conceptual correctness, structured reasoning, concrete examples, and clear delivery",\n'
            '      "question_type": "verbal"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Do not include conversational filler, markdown fences, or text outside the JSON object."
        )
        user_prompt = (
            f"Generate exactly {setup.question_count} verbal interview questions for candidate profile:\n"
            f"- Target Role: {setup.role}\n"
            f"- Experience Level: {setup.experience_level}\n"
            f"- Difficulty Level: {setup.difficulty}\n"
            f"- Focus Areas & Concepts: {setup.focus_areas}\n\n"
            "Ensure the questions test technical reasoning, conceptual depth, and verbal communication. "
            "Assign sequential IDs ('q_1', 'q_2', ...) and accurate question numbers."
        )

    raw_content = await groq_manager.execute_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4096,
        timeout=45.0,
        reasoning_effort="low",
    )

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Groq response as JSON: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model returned invalid JSON that could not be parsed.",
        ) from exc

    # 6. Validate with Pydantic
    if isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], dict) and "questions" in data[0]:
            data = data[0]
        elif len(data) > 0 and isinstance(data[0], dict) and ("text" in data[0] or "assessed_skill" in data[0]):
            data = {"questions": data}

    try:
        parsed_list = AIQuestionList.model_validate(data)
    except Exception as exc:
        logger.error("AI question schema validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model returned questions that did not conform to the required schema.",
        ) from exc

    # 7. Validate count
    if len(parsed_list.questions) < 3 or len(parsed_list.questions) > 5:
        logger.error("Invalid question count returned: %d", len(parsed_list.questions))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model generated an unexpected question count ({len(parsed_list.questions)}). Expected between 3 and 5.",
        )

    # Enforce strict session mode on all questions and verify coding questions against oracle
    verified_questions: List[QuestionItem] = []
    from app.services.oracle_service import verify_and_repair_coding_question
    from app.core.problem_catalog import BENCHMARK_PROBLEMS
    from app.core.topic_validator import parse_focus_area_topics, validate_question_topic

    allowed_topics = parse_focus_area_topics(setup.focus_areas)

    for idx, q in enumerate(parsed_list.questions):
        q.ensure_classification_and_modes(session_mode=mode)
        if mode == "CODING":
            q_dict = q.model_dump()
            is_valid_topic, topic_err = validate_question_topic(q_dict, allowed_topics)
            if not is_valid_topic:
                logger.warning("Generated question '%s' failed topic validation: %s", q.title, topic_err)
            v_dict = await verify_and_repair_coding_question(q_dict)
            if v_dict.get("quarantined") or not is_valid_topic:
                # Only use benchmark fallback if the benchmark problem genuinely satisfies the allowed topic
                matching_bm = None
                for bm_k, bm_v in BENCHMARK_PROBLEMS.items():
                    valid_bm, _ = validate_question_topic(bm_v, allowed_topics)
                    if valid_bm:
                        matching_bm = (bm_k, bm_v)
                        break

                if matching_bm:
                    fallback_key, bm_v = matching_bm
                    bench_data = dict(bm_v)
                    bench_data["id"] = q.id
                    bench_data["question_number"] = q.question_number
                    bench_data["oracle_verified"] = True
                    bench_data["oracle_provenance"] = "benchmark_catalog_fallback"
                    logger.warning(
                        "Generated coding problem '%s' failed validation. Replaced with matching benchmark '%s'.",
                        q.title, fallback_key,
                    )
                    verified_questions.append(QuestionItem.model_validate(bench_data))
                else:
                    if not is_valid_topic:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Generated coding problem failed topic constraints: {topic_err}",
                        )
                    verified_questions.append(QuestionItem.model_validate(v_dict))
            else:
                verified_questions.append(QuestionItem.model_validate(v_dict))
        else:
            verified_questions.append(q)

    return verified_questions


async def generate_initial_adaptive_question(setup: InterviewSetupRequest) -> List[QuestionItem]:
    """
    Generate the initial Question 1 for a dynamic adaptive interview session.
    Subsequent questions will be generated dynamically based on candidate performance.
    Branched strictly by setup.interview_mode (CODING vs VERBAL).
    """
    if not settings.is_groq_configured:
        logger.error("Initial adaptive question requested but GROQ_API_KEY is not configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Groq API key is not configured. Please provide GROQ_API_KEY in the backend "
                "environment to generate interview questions."
            ),
        )

    try:
        client = groq_manager.get_client()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to initialize Groq client: {type(exc).__name__}",
        ) from exc

    from app.core.topic_validator import (
        parse_focus_area_topics,
        validate_question_topic,
        select_next_topic_from_focus_areas,
    )
    from app.services.oracle_service import verify_and_repair_coding_question
    from app.core.problem_catalog import BENCHMARK_PROBLEMS

    allowed_topics = parse_focus_area_topics(setup.focus_areas)
    first_skill = select_next_topic_from_focus_areas(allowed_topics, [])
    mode = (getattr(setup, "interview_mode", None) or "VERBAL").strip().upper()
    if mode not in ("CODING", "VERBAL"):
        mode = "VERBAL"

    jd_prompt = f"\n- Target Job Description: {setup.job_description.strip()}" if getattr(setup, "job_description", None) else ""

    if mode == "CODING":
        system_prompt = (
            "You are an expert technical coding interviewer. "
            "Generate the SINGLE INITIAL BASELINE coding problem (Question 1) for this session.\n"
            "CRITICAL RULES FOR CODING MODE:\n"
            "1. MUST be an executable LeetCode-style programming challenge with a specific function to implement.\n"
            f"2. CRITICAL TOPIC CONSTRAINT: The problem MUST be strictly focused on the candidate's chosen topic: '{first_skill}'.\n"
            f"   The underlying algorithmic approach must inherently require and demonstrate mastery of '{first_skill}' "
            f"   (e.g., recursive subproblem decomposition, base cases, and return flow for recursion).\n"
            "   DO NOT generate unrelated problems such as array lookups or Two Sum; unrelated problems will be automatically rejected.\n"
            "3. Provide function_name, input_format, output_format, constraints, examples, test_cases, AND reference_solution.\n"
            "4. 'reference_solution' MUST be a complete, optimal, bug-free Python 3 implementation inside `class Solution` implementing `function_name`.\n"
            + (
                f"   For '{first_skill}', 'reference_solution' MUST genuinely use recursive problem decomposition (base cases and recursive step).\n"
                if "recursion" in first_skill.lower()
                else ""
            )
            + "5. MUST NOT be an open-ended verbal discussion or behavioral question.\n"
            "6. 'question_type' MUST be 'coding'.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "id": "q_1",\n'
            '  "question_number": 1,\n'
            '  "title": "Problem Title",\n'
            '  "text": "Detailed algorithmic problem description...",\n'
            f'  "assessed_skill": "{first_skill}",\n'
            f'  "difficulty": "{setup.difficulty}",\n'
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
            f'  "selection_rationale": "Initial baseline coding problem selected to assess core competency \'{first_skill}\' for {setup.role} at {setup.difficulty} difficulty."\n'
            "}\n"
            "Do not include conversational preamble, markdown fences, or text outside the JSON object."
        )
        user_prompt = (
            f"Generate the starting baseline coding problem for candidate profile:\n"
            f"- Target Role: {setup.role}\n"
            f"- Experience Level: {setup.experience_level}\n"
            f"- Starting Difficulty: {setup.difficulty}\n"
            f"- Allowed Focus Topics: {', '.join(allowed_topics)}{jd_prompt}\n\n"
            f"Strictly target the primary competency '{first_skill}'. The algorithmic solution must inherently require '{first_skill}'."
        )
    else:
        system_prompt = (
            "You are an expert technical interviewer and adaptive interview intelligence system. "
            "Generate the SINGLE INITIAL BASELINE verbal question (Question 1) for this interview session.\n"
            "CRITICAL RULES FOR VERBAL MODE:\n"
            "1. MUST be answerable through spoken or written natural language explanation.\n"
            "2. You MUST NEVER ask the candidate to write, execute, or submit code.\n"
            "3. Do NOT provide test cases, function stubs, or starter code templates.\n"
            "4. 'question_type' MUST be 'verbal' (or 'system_design').\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "id": "q_1",\n'
            '  "question_number": 1,\n'
            '  "text": "Full verbal question text...",\n'
            f'  "assessed_skill": "{first_skill}",\n'
            f'  "difficulty": "{setup.difficulty}",\n'
            '  "rubric": "Evaluation rubric indicators",\n'
            '  "question_type": "verbal",\n'
            f'  "selection_rationale": "Initial baseline question selected to assess core competency \'{first_skill}\' for {setup.role} at {setup.difficulty} difficulty."\n'
            "}\n"
            "Do not include conversational preamble, markdown fences, or text outside the JSON object."
        )
        user_prompt = (
            f"Generate the starting baseline verbal question for candidate profile:\n"
            f"- Target Role: {setup.role}\n"
            f"- Experience Level: {setup.experience_level}\n"
            f"- Starting Difficulty: {setup.difficulty}\n"
            f"- Allowed Focus Topics: {', '.join(allowed_topics)}{jd_prompt}\n\n"
            f"Target the core competency '{first_skill}'."
        )

    max_attempts = 3
    last_error: Optional[str] = None
    final_data: Optional[Dict[str, Any]] = None

    for attempt in range(max_attempts):
        current_user_prompt = user_prompt
        if attempt > 0 and last_error:
            current_user_prompt += f"\n\nPREVIOUS GENERATION REJECTED: {last_error}. Ensure problem strictly requires '{first_skill}' and includes an executable Python 3 reference_solution."

        raw_content = await groq_manager.execute_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": current_user_prompt},
            ],
            temperature=0.6 + (attempt * 0.1),
            max_tokens=2500,
            timeout=30.0,
            reasoning_effort="low",
        )

        try:
            data = json.loads(raw_content)
        except Exception as exc:
            last_error = f"JSON parse error: {type(exc).__name__}"
            continue

        duration_min = getattr(setup, "duration_minutes", 30) or 30
        initial_band = "comprehensive" if duration_min > 10 else ("focused" if duration_min >= 5 else "concise")

        data["id"] = "q_1"
        data["question_number"] = 1
        data["difficulty"] = setup.difficulty
        data["time_band"] = data.get("time_band") or initial_band
        data["assessed_skill"] = first_skill
        if not data.get("selection_rationale"):
            data["selection_rationale"] = (
                f"Initial baseline question selected to assess core competency '{first_skill}' for {setup.role} at {setup.difficulty} difficulty."
            )

        if mode == "CODING":
            is_valid_topic, topic_reason = validate_question_topic(data, allowed_topics)
            if not is_valid_topic:
                last_error = topic_reason
                logger.warning("Attempt %d generated coding question failed topic constraint: %s", attempt + 1, topic_reason)
                continue

            v_dict = await verify_and_repair_coding_question(data)
            if v_dict.get("quarantined"):
                last_error = f"Oracle verification quarantined question: {v_dict.get('validation_error')}"
                logger.warning("Attempt %d question quarantined by oracle: %s", attempt + 1, v_dict.get("validation_error"))
                continue

            final_data = v_dict
            break
        else:
            final_data = data
            break

    if not final_data:
        # Check if an existing benchmark problem genuinely satisfies the requested topic
        matching_bm = None
        for bm_k, bm_v in BENCHMARK_PROBLEMS.items():
            valid_bm, _ = validate_question_topic(bm_v, allowed_topics)
            if valid_bm:
                matching_bm = (bm_k, bm_v)
                break

        if matching_bm:
            fallback_key, bm_v = matching_bm
            bench_data = dict(bm_v)
            bench_data["id"] = "q_1"
            bench_data["question_number"] = 1
            bench_data["difficulty"] = setup.difficulty
            bench_data["assessed_skill"] = first_skill
            bench_data["oracle_verified"] = True
            bench_data["oracle_provenance"] = "benchmark_catalog_fallback"
            bench_data["selection_rationale"] = f"Benchmark question matched to candidate focus topic '{first_skill}'."
            final_data = bench_data
        else:
            logger.error("Failed to generate topic-constrained question for %s after %d retries: %s", allowed_topics, max_attempts, last_error)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"Unable to dynamically generate a verified coding challenge strictly matching topic constraints: "
                    f"'{', '.join(allowed_topics)}'. Rejection reason: {last_error or 'Topic validation failed'}. "
                    "Please adjust your focus areas or try again."
                ),
            )

    q = QuestionItem.model_validate(final_data)
    q.ensure_classification_and_modes(session_mode=mode)
    return [q]
