import json
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
import groq
from app.core.config import settings
from app.core.groq_client import groq_manager
from app.schemas.interview import QuestionItem
from app.schemas.evaluation import AIEvaluationRaw

logger = logging.getLogger("interviewiq.evaluation_service")


async def evaluate_candidate_answer(
    question: QuestionItem,
    answer_text: str,
    role: str = "Candidate",
    experience_level: str = "Mid-Level",
) -> AIEvaluationRaw:
    """
    Evaluate candidate's answer using the Groq LLM against the question rubric.
    Enforces evidence-based feedback without inferring voice, delivery, or personality.
    Returns validated AIEvaluationRaw structure.
    """
    if not settings.is_groq_configured:
        logger.error("Answer evaluation requested but GROQ_API_KEY is not configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Groq API key is not configured. Please set GROQ_API_KEY in backend/.env "
                "to enable AI answer evaluation."
            ),
        )

    clean_answer = answer_text.strip()
    if not clean_answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot evaluate an empty answer. Please provide a response before requesting evaluation.",
        )

    try:
        client = groq_manager.get_client()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to initialize Groq client: {type(exc).__name__}",
        ) from exc

    system_prompt = (
        "You are an expert technical interview evaluator and communication coach. "
        "Your role is to rigorously and objectively evaluate a candidate's spoken or written interview response "
        "against the provided question and evaluation rubric.\n\n"
        "EVALUATION RULES:\n"
        "1. Base all scores and feedback strictly on textual evidence present in the candidate's answer.\n"
        "2. Do NOT speculate on or infer candidate personality, emotional state, honesty, or acoustic vocal delivery (such as pitch, volume, or voice tone).\n"
        "3. Criterion scores MUST be integers between 1 and 10 (1=Unsatisfactory, 5=Average, 10=Exemplary).\n"
        "4. Overall score MUST be an integer between 1 and 100.\n"
        "5. Provide concrete, actionable coaching suggestions on structure, clarity, evidence, and conciseness.\n"
        "6. If the question is behavioral or experiential, evaluate STAR framework adherence (Situation, Task, Action, Result).\n"
        "7. Provide a stronger example answer demonstrating ideal structure, and recommended follow-up practice.\n\n"
        "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "overall_score": 82,\n'
        '  "criterion_scores": {\n'
        '    "relevance": {"score": 8, "feedback": "Evidence from text..."},\n'
        '    "technical_depth": {"score": 8, "feedback": "Evidence from text..."},\n'
        '    "completeness": {"score": 7, "feedback": "Evidence from text..."},\n'
        '    "structure_flow": {"score": 9, "feedback": "Evidence from text..."},\n'
        '    "clarity_conciseness": {"score": 8, "feedback": "Evidence from text..."},\n'
        '    "star_structure": {"score": 8, "feedback": "Evidence from text..."}\n'
        "  },\n"
        '  "strengths": ["Clear definition of X", "Included concrete metrics for Y"],\n'
        '  "areas_for_improvement": ["Did not address edge case Z", "Could be more concise in introduction"],\n'
        '  "actionable_suggestions": ["Lead with the outcome before detailing the implementation"],\n'
        '  "coaching_summary": "Focus on tightening the opening explanation and explicitly citing tradeoffs.",\n'
        '  "stronger_example_answer": "In my previous role, I addressed this by...",\n'
        '  "recommended_practice": "Practice quantitative impact articulation and system boundary constraints."\n'
        "}\n"
        "Do not include any conversational preamble, markdown fences, or text outside the JSON object."
    )

    user_prompt = (
        f"INTERVIEW CONTEXT:\n"
        f"- Target Role: {role}\n"
        f"- Experience Level: {experience_level}\n\n"
        f"QUESTION:\n"
        f"- Number: Question {question.question_number}\n"
        f"- Assessed Skill: {question.assessed_skill}\n"
        f"- Difficulty: {question.difficulty}\n"
        f"- Question Text: {question.text}\n"
        f"- Evaluation Rubric: {question.rubric}\n\n"
        f"CANDIDATE'S SUBMITTED ANSWER:\n"
        f'"""\n{clean_answer}\n"""\n\n'
        f"Provide your rigorous evaluation JSON strictly adhering to the schema."
    )

    raw_content = await groq_manager.execute_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2048,
        timeout=30.0,
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse evaluation response as JSON: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model returned invalid JSON during answer evaluation.",
        ) from exc

    # Defensive normalization for schema fields
    if not data.get("strengths"):
        data["strengths"] = [
            cs.get("feedback")
            for cs in (data.get("criterion_scores") or {}).values()
            if isinstance(cs, dict) and cs.get("score", 0) >= 7 and cs.get("feedback")
        ] or ["Demonstrated solid grasp of core technical principles."]

    if not data.get("areas_for_improvement"):
        data["areas_for_improvement"] = [
            cs.get("feedback")
            for cs in (data.get("criterion_scores") or {}).values()
            if isinstance(cs, dict) and cs.get("score", 0) < 7 and cs.get("feedback")
        ] or ["Explore deeper runtime edge cases and explicit latency tradeoffs."]

    if not data.get("actionable_suggestions"):
        data["actionable_suggestions"] = [
            f"Elaborate on {k.replace('_', ' ')} with concrete quantitative examples."
            for k in (data.get("criterion_scores") or {}).keys()
        ][:2] or ["Lead with the architectural conclusion before detailing mechanics."]

    if not data.get("coaching_summary"):
        data["coaching_summary"] = "Structured technical explanation addressing core criteria with clear baseline reasoning."

    try:
        validated = AIEvaluationRaw.model_validate(data)
    except Exception as exc:
        logger.error("Evaluation response schema validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model evaluation response did not match the expected schema: {str(exc)}",
        ) from exc

    return validated


async def evaluate_system_design_answer(
    question: QuestionItem,
    answer_text: str,
    role: str = "Systems Architect",
    experience_level: str = "Senior",
) -> AIEvaluationRaw:
    """
    Evaluate candidate's system design specification using Groq LLM against architecture criteria:
    - Scope & Requirements (Functional & Non-Functional, QPS, Storage)
    - Component Architecture & Data Flow
    - Database Choices, Relational vs NoSQL Schemas, and Caching
    - Scalability, Load Balancing, Partitioning, and Bottlenecks
    - High Availability, Resilience, and Explicit Engineering Trade-offs
    """
    if not settings.is_groq_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key is not configured. Please set GROQ_API_KEY to enable AI evaluation.",
        )

    clean_answer = answer_text.strip()
    if not clean_answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot evaluate an empty architectural design answer.",
        )

    try:
        client = groq_manager.get_client()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to initialize Groq client: {type(exc).__name__}",
        ) from exc

    system_prompt = (
        "You are a Principal Systems Architect and Staff Engineer interviewer. "
        "Your task is to rigorously evaluate a candidate's structured System Design proposal. "
        "Evaluate across 5 core pillars:\n"
        "1. Scope, scale estimation, functional/non-functional requirements.\n"
        "2. High-level architecture, components, and API boundaries.\n"
        "3. Data layer: storage engines (SQL vs NoSQL), schema modeling, caching (Redis/Memcached), indexing.\n"
        "4. Scalability: horizontal scaling, partitioning/sharding, asynchronous message queues.\n"
        "5. Resilience and trade-offs: CAP theorem decisions, single-points-of-failure, circuit breakers, recovery.\n\n"
        "EVALUATION RULES:\n"
        "1. Base scores strictly on textual evidence present in the candidate's proposal.\n"
        "2. Criterion scores MUST be integers between 1 and 10.\n"
        "3. Overall score MUST be an integer between 1 and 100.\n"
        "4. Identify concrete architectural strengths and specific unaddressed bottlenecks or trade-offs.\n\n"
        "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "overall_score": 85,\n'
        '  "criterion_scores": {\n'
        '    "relevance": {"score": 9, "feedback": "Directly designs the requested distributed system."},\n'
        '    "technical_depth": {"score": 8, "feedback": "Detailed database choices, sharding keys, and cache tiers."},\n'
        '    "completeness": {"score": 8, "feedback": "Addresses both functional requirements and failure modes."},\n'
        '    "structure_flow": {"score": 9, "feedback": "Logical progression from scope to components to trade-offs."},\n'
        '    "clarity_conciseness": {"score": 8, "feedback": "Structured headers and clear component explanations."}\n'
        "  },\n"
        '  "strengths": ["Well-reasoned data store choices", "Addressed hot-partition mitigation via consistent hashing"],\n'
        '  "areas_for_improvement": ["Did not calculate write throughput memory saturation", "Lacks details on cross-region failover"],\n'
        '  "actionable_suggestions": ["Include concrete QPS calculations before picking replication factor"],\n'
        '  "coaching_summary": "Strong architectural framework. Deepen quantitative capacity planning and edge failure recovery.",\n'
        '  "stronger_example_answer": "An exemplary architecture would explicitly include API gateway rate limiting, Kafka event streaming, and Read-replica failover.",\n'
        '  "recommended_practice": "Practice designing distributed consensus, idempotent consumers, and backpressure mechanisms."\n'
        "}\n"
        "Do not include any conversational preamble, markdown fences, or text outside the JSON object."
    )

    user_prompt = (
        f"INTERVIEW CONTEXT:\n"
        f"- Target Role: {role}\n"
        f"- Experience Level: {experience_level}\n\n"
        f"SYSTEM DESIGN QUESTION:\n"
        f"- Question Number: Question {question.question_number}\n"
        f"- Focus Area: {question.assessed_skill}\n"
        f"- Difficulty: {question.difficulty}\n"
        f"- Prompt Text: {question.text}\n"
        f"- Evaluation Rubric: {question.rubric}\n\n"
        f"CANDIDATE'S SYSTEM DESIGN PROPOSAL:\n"
        f'"""\n{clean_answer}\n"""\n\n'
        f"Provide your rigorous architectural evaluation JSON."
    )

    raw_content = await groq_manager.execute_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=2048,
        timeout=30.0,
        reasoning_effort="low",
    )

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse system design evaluation JSON: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model returned invalid JSON during system design evaluation.",
        ) from exc

    try:
        validated = AIEvaluationRaw.model_validate(data)
    except Exception as exc:
        logger.error("System design evaluation schema validation failed: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model evaluation response did not match expected schema: {str(exc)}",
        ) from exc

    return validated
