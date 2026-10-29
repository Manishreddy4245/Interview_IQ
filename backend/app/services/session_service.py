import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.database import db_manager
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    InterviewSessionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    SaveDraftRequest,
    SaveDraftResponse,
    SessionDraftsResponse,
)
from app.schemas.evaluation import (
    AIEvaluationRaw,
    AnswerEvaluationResponse,
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

logger = logging.getLogger("interviewiq.session_service")

# Fallback in-memory store when MongoDB Atlas is unconfigured or unreachable
_in_memory_sessions: Dict[str, Dict[str, Any]] = {}


def compute_session_time_status(
    session: Dict[str, Any],
    client_hint_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Authoritatively calculate session timing:
    - total duration from session configuration (default 30 min)
    - server elapsed time based on session created_at
    - server remaining seconds
    - validated effective remaining seconds (guards against client-side inflation)
    - active time band ('comprehensive', 'focused', 'concise', 'expired')
    - is_expired boolean flag
    """
    duration_minutes = session.get("duration_minutes") or 30
    total_seconds = int(duration_minutes * 60)

    created_raw = session.get("created_at")
    if created_raw:
        if isinstance(created_raw, str):
            try:
                created_dt = datetime.fromisoformat(created_raw)
            except Exception:
                created_dt = datetime.now(timezone.utc)
        elif isinstance(created_raw, datetime):
            created_dt = created_raw
        else:
            created_dt = datetime.now(timezone.utc)
    else:
        created_dt = datetime.now(timezone.utc)

    if created_dt.tzinfo is None:
        created_dt = created_dt.replace(tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)
    elapsed_seconds = max(0, int((now_utc - created_dt).total_seconds()))
    server_remaining = max(0, total_seconds - elapsed_seconds)

    # Validate client hint: client cannot inflate remaining time beyond server authority
    if server_remaining <= 0:
        effective_remaining = 0
    elif client_hint_seconds is not None:
        if client_hint_seconds < 0:
            effective_remaining = 0
        else:
            effective_remaining = min(server_remaining, int(client_hint_seconds))
    else:
        effective_remaining = server_remaining

    is_expired = (effective_remaining <= 0)

    # Classify time band
    if is_expired:
        time_band = "expired"
    elif effective_remaining > 600:
        time_band = "comprehensive"
    elif effective_remaining >= 300:
        time_band = "focused"
    else:
        time_band = "concise"

    return {
        "duration_minutes": duration_minutes,
        "total_seconds": total_seconds,
        "elapsed_seconds": elapsed_seconds,
        "server_remaining_seconds": server_remaining,
        "effective_remaining_seconds": effective_remaining,
        "time_band": time_band,
        "is_expired": is_expired,
    }


async def create_interview_session(
    setup: InterviewSetupRequest,
    questions: List[QuestionItem],
    resume_analysis_id: Optional[str] = None,
    is_adaptive: Optional[bool] = None,
    target_question_count: Optional[int] = None,
    prioritized_competencies: Optional[List[str]] = None,
    owner_id: Optional[str] = None,
) -> InterviewSessionResponse:
    """
    Create a new interview session.
    Persists to MongoDB Atlas if configured and reachable;
    falls back cleanly to in-memory session tracking without claiming DB persistence.
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    adaptive_flag = is_adaptive if is_adaptive is not None else getattr(setup, "adaptive", False)
    target_count = target_question_count or getattr(setup, "question_count", len(questions))
    duration_minutes = getattr(setup, "duration_minutes", 30) or 30
    job_description = getattr(setup, "job_description", None)

    active_q_id = questions[0].id if questions else None
    session_mode = getattr(setup, "interview_mode", None) or "VERBAL"
    session_mode = session_mode.strip().upper() if isinstance(session_mode, str) else "VERBAL"
    if session_mode not in ("CODING", "VERBAL"):
        session_mode = "VERBAL"

    session_doc = {
        "session_id": session_id,
        "owner_id": owner_id,
        "role": setup.role,
        "experience_level": setup.experience_level,
        "difficulty": setup.difficulty,
        "focus_areas": setup.focus_areas,
        "duration_minutes": duration_minutes,
        "job_description": job_description,
        "interview_mode": session_mode,
        "is_unreliable_mode": False,
        "questions": [q.model_dump() for q in questions],
        "active_question_id": active_q_id,
        "answers": {},
        "drafts": {},
        "integrity_events": [],
        "human_reviews": [],
        "candidate_explanations": [],
        "resume_analysis_id": resume_analysis_id,
        "prioritized_competencies": prioritized_competencies,
        "target_question_count": target_count,
        "is_adaptive": adaptive_flag,
        "status": "in_progress",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    # Attempt database persistence
    saved_to_db = False
    db_status = "unconfigured"
    db_message = "MongoDB Atlas is not configured in the environment. Session is active in-memory only."

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["interview_sessions"].insert_one({**session_doc, "_id": session_id})
            saved_to_db = True
            db_status = "persisted"
            db_message = "Session successfully persisted to MongoDB Atlas."
            logger.info("Session %s persisted to MongoDB Atlas.", session_id)
        except Exception as exc:
            db_status = "unreachable"
            db_message = f"MongoDB Atlas write failed: {type(exc).__name__}. Falling back to in-memory session."
            logger.warning("MongoDB Atlas write failed for session %s: %s", session_id, type(exc).__name__)

    # Always keep in-memory reference for local session continuity
    _in_memory_sessions[session_id] = session_doc

    return InterviewSessionResponse(
        session_id=session_id,
        role=setup.role,
        experience_level=setup.experience_level,
        difficulty=setup.difficulty,
        focus_areas=setup.focus_areas,
        interview_mode=session_mode,
        is_unreliable_mode=False,
        questions=questions,
        active_question_id=active_q_id,
        target_question_count=target_count,
        is_adaptive=adaptive_flag,
        resume_analysis_id=resume_analysis_id,
        prioritized_competencies=prioritized_competencies,
        owner_id=owner_id,
        duration_minutes=duration_minutes,
        job_description=job_description,
        time_remaining_seconds=duration_minutes * 60,
        is_expired=False,
        created_at=now,
        saved_to_db=saved_to_db,
        db_status=db_status,
        db_message=db_message,
        drafts=session_doc.get("drafts", {}),
    )


async def append_session_question(
    session_id: str,
    question: QuestionItem,
    current_session: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Append a dynamically generated question to an existing interview session.
    Persists to MongoDB Atlas if reachable; updates in-memory copy.
    Guarantees idempotency and enforces target question count limit.
    """
    now = datetime.now(timezone.utc)
    q_dict = question.model_dump()

    session = current_session or await get_session(session_id)
    if not session:
        raise ValueError(f"Session '{session_id}' not found.")

    existing_questions = session.get("questions", [])
    target_count = session.get("target_question_count", session.get("question_count", 3))

    # Guard 1: Idempotency - skip duplicate question IDs
    existing_q_ids = [q["id"] for q in existing_questions]
    if question.id in existing_q_ids:
        logger.warning(
            "Question '%s' already exists in session '%s'. Skipping duplicate append.",
            question.id,
            session_id,
        )
        session["saved_to_db"] = session.get("saved_to_db", True if settings.is_mongodb_configured else False)
        session["db_status"] = session.get("db_status", "persisted" if session.get("saved_to_db") else "unconfigured")
        session["db_message"] = "Question already exists in session (idempotent duplicate)."
        return session

    # Guard 2: Enforce target question count
    if len(existing_questions) >= target_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interview session has already reached its target question count ({target_count}).",
        )

    saved_to_db = False
    db_status = "unconfigured"
    db_message = "Question appended in server memory."

    # In-memory update
    if session_id in _in_memory_sessions:
        _in_memory_sessions[session_id].setdefault("questions", []).append(q_dict)
        _in_memory_sessions[session_id]["active_question_id"] = q_dict["id"]
        _in_memory_sessions[session_id]["updated_at"] = now.isoformat()
        session = _in_memory_sessions[session_id]

    # MongoDB Atlas update with duplicate guard
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            result = await db["interview_sessions"].update_one(
                {
                    "session_id": session_id,
                    "questions.id": {"$ne": q_dict["id"]},
                },
                {
                    "$push": {"questions": q_dict},
                    "$set": {
                        "updated_at": now.isoformat(),
                        "active_question_id": q_dict["id"],
                    },
                },
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
                db_message = "Adaptive question persisted to MongoDB Atlas."
            else:
                # Check if session exists in db to distinguish duplicate vs not found
                exists = await db["interview_sessions"].find_one({"session_id": session_id}, {"_id": 1})
                if exists:
                    saved_to_db = True
                    db_status = "persisted"
                    db_message = "Question already present in MongoDB Atlas session."
                else:
                    saved_to_db = False
                    db_status = "not_found_in_db"
                    db_message = "Session not found in MongoDB Atlas, updated in active memory."
        except Exception as exc:
            db_status = "unreachable"
            db_message = f"MongoDB Atlas write failed: {type(exc).__name__}."
            logger.warning("Failed to append question to MongoDB Atlas for session %s: %s", session_id, type(exc).__name__)

    session["saved_to_db"] = saved_to_db
    session["db_status"] = db_status
    session["db_message"] = db_message
    session["active_question_id"] = q_dict["id"]
    return session


async def complete_session(session_id: str) -> None:
    """Mark session as completed."""
    now = datetime.now(timezone.utc)
    if session_id in _in_memory_sessions:
        _in_memory_sessions[session_id]["status"] = "completed"
        _in_memory_sessions[session_id]["updated_at"] = now.isoformat()

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {"$set": {"status": "completed", "updated_at": now.isoformat()}},
            )
        except Exception:
            pass


async def submit_answer(
    session_id: str,
    answer_data: SubmitAnswerRequest,
    current_session: Optional[Dict[str, Any]] = None,
) -> SubmitAnswerResponse:
    """
    Submit an answer for a specific question within a session.
    Persists answer to MongoDB Atlas if reachable; updates in-memory copy.
    Rejects submissions if session time has expired.
    """
    now = datetime.now(timezone.utc)
    saved_to_db = False
    db_status = "unconfigured"
    message = "Answer recorded in-memory for active session."

    session = current_session or await get_session(session_id)
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

    if session.get("is_unreliable_mode") or session.get("interview_mode") == "AMBIGUOUS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session mode is ambiguous or unreliable due to inconsistent question history. Please restart a new Coding or Verbal interview session.",
        )

    timing = compute_session_time_status(session)
    if timing["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session time has expired. Cannot submit additional answers.",
        )

    # Validate that question was actually issued to this session
    question_ids = [q["id"] for q in session.get("questions", [])]
    if answer_data.question_id not in question_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Question '{answer_data.question_id}' was never issued to this interview session. "
                f"Skipping forward to unissued questions is rejected. Issued questions: {question_ids}"
            ),
        )

    # Update session dictionary directly
    if "answers" not in session:
        session["answers"] = {}
    existing_q = session["answers"].get(answer_data.question_id, {})
    session["answers"][answer_data.question_id] = {
        **existing_q,
        "answer_text": answer_data.answer_text or "",
        "answer_mode": answer_data.answer_mode,
        "code": answer_data.code,
        "language": answer_data.language,
        "sql_query": answer_data.sql_query,
        "execution_result": answer_data.execution_result,
        "submitted_at": now.isoformat(),
    }
    session["updated_at"] = now.isoformat()

    # Update in-memory cache
    if session_id in _in_memory_sessions:
        _in_memory_sessions[session_id] = session

    # Attempt MongoDB update if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            update_fields = {
                f"answers.{answer_data.question_id}.answer_text": answer_data.answer_text or "",
                f"answers.{answer_data.question_id}.submitted_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            if answer_data.answer_mode is not None:
                update_fields[f"answers.{answer_data.question_id}.answer_mode"] = answer_data.answer_mode
            if answer_data.code is not None:
                update_fields[f"answers.{answer_data.question_id}.code"] = answer_data.code
            if answer_data.language is not None:
                update_fields[f"answers.{answer_data.question_id}.language"] = answer_data.language
            if answer_data.sql_query is not None:
                update_fields[f"answers.{answer_data.question_id}.sql_query"] = answer_data.sql_query
            if answer_data.execution_result is not None:
                update_fields[f"answers.{answer_data.question_id}.execution_result"] = answer_data.execution_result

            result = await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {"$set": update_fields},
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
                message = "Answer successfully saved to MongoDB Atlas."
            else:
                db_status = "not_found_in_db"
                message = "Session not found in MongoDB Atlas, but recorded in active memory."
        except Exception as exc:
            db_status = "unreachable"
            message = f"MongoDB Atlas update failed: {type(exc).__name__}. Recorded in active memory."
            logger.warning("MongoDB update failed for session %s: %s", session_id, type(exc).__name__)

    return SubmitAnswerResponse(
        session_id=session_id,
        question_id=answer_data.question_id,
        answer_mode=answer_data.answer_mode,
        submitted_at=now,
        saved_to_db=saved_to_db,
        db_status=db_status,
        message=message,
    )


async def save_evaluation(
    session_id: str,
    question_id: str,
    evaluation: AIEvaluationRaw,
    current_session: Optional[Dict[str, Any]] = None,
) -> AnswerEvaluationResponse:
    """
    Persist evaluation results into the interview session.
    Persists to MongoDB Atlas if reachable; updates active in-memory session otherwise.
    """
    now = datetime.now(timezone.utc)
    saved_to_db = False
    db_status = "unconfigured"
    db_message = "MongoDB Atlas is not configured in the environment. Evaluation is held in active memory only."

    eval_dict = evaluation.model_dump()

    # Update in-memory session
    target_session = current_session or _in_memory_sessions.get(session_id)
    if target_session:
        if "answers" not in target_session:
            target_session["answers"] = {}
        if question_id not in target_session["answers"]:
            target_session["answers"][question_id] = {}
        target_session["answers"][question_id]["evaluation"] = eval_dict
        target_session["answers"][question_id]["evaluated_at"] = now.isoformat()
        target_session["updated_at"] = now.isoformat()
        _in_memory_sessions[session_id] = target_session

    # Attempt MongoDB update if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            result = await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        f"answers.{question_id}.evaluation": eval_dict,
                        f"answers.{question_id}.evaluated_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                    }
                },
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
                db_message = "Evaluation successfully persisted to MongoDB Atlas."
            else:
                db_status = "not_found_in_db"
                db_message = "Session not found in MongoDB Atlas, but recorded in active memory."
        except Exception as exc:
            db_status = "unreachable"
            db_message = f"MongoDB Atlas write failed: {type(exc).__name__}. Recorded in active memory."
            logger.warning(
                "MongoDB update failed for session %s evaluation: %s", session_id, type(exc).__name__
            )

    return AnswerEvaluationResponse(
        session_id=session_id,
        question_id=question_id,
        overall_score=evaluation.overall_score,
        criterion_scores=evaluation.criterion_scores,
        strengths=evaluation.strengths,
        areas_for_improvement=evaluation.areas_for_improvement,
        actionable_suggestions=evaluation.actionable_suggestions,
        coaching_summary=evaluation.coaching_summary,
        stronger_example_answer=getattr(evaluation, "stronger_example_answer", None),
        recommended_practice=getattr(evaluation, "recommended_practice", None),
        acoustic_disclaimer=getattr(
            evaluation,
            "acoustic_disclaimer",
            (
                "Pronunciation, pitch, vocal confidence, and acoustic voice-quality analysis "
                "were not performed. Evaluation is strictly based on the recognized transcript text."
            ),
        ),
        evaluated_at=now,
        saved_to_db=saved_to_db,
        db_status=db_status,
        db_message=db_message,
    )


async def record_answer_and_evaluation(
    session_id: str,
    answer_data: Optional[SubmitAnswerRequest] = None,
    evaluation: Optional[AIEvaluationRaw] = None,
    current_session: Optional[Dict[str, Any]] = None,
    answer_payload: Optional[SubmitAnswerRequest] = None,
) -> Tuple[SubmitAnswerResponse, AnswerEvaluationResponse, Dict[str, Any]]:
    """
    Combined atomic submission and evaluation persistence.
    Reduces MongoDB network round-trips by performing a single combined update.
    Returns (SubmitAnswerResponse, AnswerEvaluationResponse, updated_session).
    """
    actual_answer = answer_payload or answer_data
    if actual_answer is None:
        raise ValueError("answer_data or answer_payload is required")
    answer_data = actual_answer
    if evaluation is None:
        raise ValueError("evaluation is required")

    now = datetime.now(timezone.utc)
    saved_to_db = False
    db_status = "unconfigured"
    db_message = "Answer and evaluation recorded in-memory for active session."

    session = current_session or await get_session(session_id)
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

    if session.get("is_unreliable_mode") or session.get("interview_mode") == "AMBIGUOUS":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session mode is ambiguous or unreliable due to inconsistent question history. Please restart a new Coding or Verbal interview session.",
        )

    timing = compute_session_time_status(session)
    if timing["is_expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview session time has expired. Cannot submit additional answers.",
        )

    question_ids = [q["id"] for q in session.get("questions", [])]
    if answer_data.question_id not in question_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question '{answer_data.question_id}' was never issued to this interview session. Issued: {question_ids}",
        )

    eval_dict = evaluation.model_dump()
    answer_entry: Dict[str, Any] = {
        "answer_text": answer_data.answer_text or "",
        "submitted_at": now.isoformat(),
        "evaluation": eval_dict,
        "evaluated_at": now.isoformat(),
    }
    if answer_data.answer_mode is not None:
        answer_entry["answer_mode"] = answer_data.answer_mode
    if answer_data.code is not None:
        answer_entry["code"] = answer_data.code
    if answer_data.language is not None:
        answer_entry["language"] = answer_data.language
    if answer_data.sql_query is not None:
        answer_entry["sql_query"] = answer_data.sql_query
    if answer_data.execution_result is not None:
        answer_entry["execution_result"] = answer_data.execution_result

    # Update in-memory session directly
    if "answers" not in session:
        session["answers"] = {}
    session["answers"][answer_data.question_id] = answer_entry
    session["updated_at"] = now.isoformat()
    _in_memory_sessions[session_id] = session

    # Single combined write to MongoDB Atlas
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            update_fields: Dict[str, Any] = {
                f"answers.{answer_data.question_id}": answer_entry,
                "updated_at": now.isoformat(),
            }
            result = await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {"$set": update_fields},
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
                db_message = "Answer and evaluation persisted to MongoDB Atlas."
            else:
                db_status = "not_found_in_db"
                db_message = "Session not found in MongoDB Atlas, recorded in active memory."
        except Exception as exc:
            db_status = "unreachable"
            db_message = f"MongoDB Atlas write failed: {type(exc).__name__}. Recorded in active memory."
            logger.warning("MongoDB combined write failed for session %s: %s", session_id, type(exc).__name__)

    ans_resp = SubmitAnswerResponse(
        session_id=session_id,
        question_id=answer_data.question_id,
        answer_mode=answer_data.answer_mode,
        submitted_at=now,
        saved_to_db=saved_to_db,
        db_status=db_status,
        message=db_message,
    )

    eval_resp = AnswerEvaluationResponse(
        session_id=session_id,
        question_id=answer_data.question_id,
        overall_score=evaluation.overall_score,
        criterion_scores=evaluation.criterion_scores,
        strengths=evaluation.strengths,
        areas_for_improvement=evaluation.areas_for_improvement,
        actionable_suggestions=evaluation.actionable_suggestions,
        coaching_summary=evaluation.coaching_summary,
        stronger_example_answer=getattr(evaluation, "stronger_example_answer", None),
        recommended_practice=getattr(evaluation, "recommended_practice", None),
        acoustic_disclaimer=getattr(
            evaluation,
            "acoustic_disclaimer",
            "Evaluated based on textual and algorithmic assessment criteria.",
        ),
        evaluated_at=now,
        saved_to_db=saved_to_db,
        db_status=db_status,
        db_message=db_message,
    )

    return ans_resp, eval_resp, session


async def record_integrity_event(
    session_id: str,
    event_data: IntegrityEventCreate,
) -> IntegrityEventRecord:
    """
    Record an observable browser or device integrity event for an active session.
    Persists to MongoDB Atlas if configured; updates in-memory session.
    """
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    timestamp = event_data.timestamp or now

    saved_to_db = False
    db_status = "unconfigured"

    # Deduplication & throttling for continuous incidents
    existing_events = []
    if session_id in _in_memory_sessions:
        existing_events = _in_memory_sessions[session_id].get("integrity_events", [])

    ev_type_str = event_data.event_type.value if hasattr(event_data.event_type, "value") else str(event_data.event_type)

    # Check if last event was identical active event within 3 seconds (deduplicate)
    if existing_events:
        last_ev = existing_events[-1]
        last_type = last_ev.get("event_type")
        last_ts_str = last_ev.get("timestamp")
        try:
            last_ts = datetime.fromisoformat(last_ts_str) if isinstance(last_ts_str, str) else last_ts_str
            diff_sec = (timestamp - last_ts).total_seconds()
        except Exception:
            diff_sec = 100.0

        if last_type == ev_type_str and diff_sec < 3.0 and last_ev.get("status") == "active" and event_data.status == "active":
            # Update existing event duration rather than adding duplicate
            if event_data.duration_seconds is not None:
                last_ev["duration_seconds"] = event_data.duration_seconds
            if event_data.details:
                last_ev["details"] = {**(last_ev.get("details") or {}), **event_data.details}
            return IntegrityEventRecord(
                event_id=last_ev["event_id"],
                session_id=session_id,
                question_id=last_ev.get("question_id"),
                event_type=last_ev["event_type"],
                timestamp=last_ts,
                details=last_ev.get("details"),
                saved_to_db=bool(last_ev.get("saved_to_db", False)),
                db_status=last_ev.get("db_status", "unconfigured"),
                severity=last_ev.get("severity", "info"),
                duration_seconds=last_ev.get("duration_seconds"),
                detection_source=last_ev.get("detection_source"),
                detection_confidence=last_ev.get("detection_confidence"),
                status=last_ev.get("status", "recorded"),
            )

    event_record_dict = {
        "event_id": event_id,
        "session_id": session_id,
        "question_id": event_data.question_id,
        "event_type": ev_type_str,
        "timestamp": timestamp.isoformat(),
        "details": event_data.details,
        "severity": event_data.severity or "info",
        "duration_seconds": event_data.duration_seconds,
        "detection_source": event_data.detection_source,
        "detection_confidence": event_data.detection_confidence,
        "status": event_data.status or "recorded",
    }

    # Record in active in-memory session
    if session_id in _in_memory_sessions:
        if "integrity_events" not in _in_memory_sessions[session_id]:
            _in_memory_sessions[session_id]["integrity_events"] = []
        _in_memory_sessions[session_id]["integrity_events"].append(event_record_dict)
        _in_memory_sessions[session_id]["updated_at"] = now.isoformat()

    # Attempt MongoDB update if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            result = await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$push": {"integrity_events": event_record_dict},
                    "$set": {"updated_at": now.isoformat()},
                },
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
            else:
                db_status = "not_found_in_db"
        except Exception as exc:
            db_status = "unreachable"
            logger.warning(
                "MongoDB append failed for session %s integrity event: %s",
                session_id,
                type(exc).__name__,
            )

    event_record_dict["saved_to_db"] = saved_to_db
    event_record_dict["db_status"] = db_status

    return IntegrityEventRecord(
        event_id=event_id,
        session_id=session_id,
        question_id=event_data.question_id,
        event_type=event_data.event_type,
        timestamp=timestamp,
        details=event_data.details,
        saved_to_db=saved_to_db,
        db_status=db_status,
        severity=event_data.severity or "info",
        duration_seconds=event_data.duration_seconds,
        detection_source=event_data.detection_source,
        detection_confidence=event_data.detection_confidence,
        status=event_data.status or "recorded",
    )


async def get_integrity_events(session_id: str) -> IntegrityEventsResponse:
    """
    Retrieve all recorded integrity events for a session as a chronological timeline.
    """
    saved_to_db = False
    db_status = "unconfigured"
    db_message = "Events retrieved from active runtime memory (MongoDB Atlas unconfigured)."
    events_raw = []

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            doc = await db["interview_sessions"].find_one({"session_id": session_id})
            if doc:
                saved_to_db = True
                db_status = "persisted"
                db_message = "Timeline events retrieved from MongoDB Atlas."
                events_raw = doc.get("integrity_events", [])
        except Exception as exc:
            db_status = "unreachable"
            db_message = f"MongoDB query failed: {type(exc).__name__}. Falling back to memory."

    if not events_raw and session_id in _in_memory_sessions:
        events_raw = _in_memory_sessions[session_id].get("integrity_events", [])

    records = [
        IntegrityEventRecord(
            event_id=item["event_id"],
            session_id=session_id,
            question_id=item.get("question_id"),
            event_type=item["event_type"],
            timestamp=datetime.fromisoformat(item["timestamp"]) if isinstance(item["timestamp"], str) else item["timestamp"],
            details=item.get("details"),
            saved_to_db=item.get("saved_to_db", saved_to_db),
            db_status=item.get("db_status", db_status),
            severity=item.get("severity", "info"),
            duration_seconds=item.get("duration_seconds"),
            detection_source=item.get("detection_source"),
            detection_confidence=item.get("detection_confidence"),
            status=item.get("status", "recorded"),
        )
        for item in events_raw
    ]

    return IntegrityEventsResponse(
        session_id=session_id,
        events=records,
        total_events=len(records),
        saved_to_db=saved_to_db,
        db_status=db_status,
        db_message=db_message,
    )


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session by ID from MongoDB Atlas or active memory, ensuring questions are canonically classified."""
    session_data = None
    db_status_on_fetch = "unconfigured"
    db_message_on_fetch = "MongoDB Atlas is not configured in the environment."

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            doc = await db["interview_sessions"].find_one({"session_id": session_id})
            if doc:
                doc.pop("_id", None)
                session_data = doc
                session_data["saved_to_db"] = True
                session_data["db_status"] = "persisted"
                session_data["db_message"] = "Session retrieved from MongoDB Atlas."
            else:
                db_status_on_fetch = "not_found_in_db"
                db_message_on_fetch = "Session not found in MongoDB Atlas, found in active memory."
        except Exception as exc:
            db_status_on_fetch = "unreachable"
            db_message_on_fetch = f"MongoDB Atlas query failed: {type(exc).__name__}."
            logger.warning("MongoDB query failed for session %s: %s", session_id, type(exc).__name__)

    if session_data is None and session_id in _in_memory_sessions:
        session_data = _in_memory_sessions[session_id]
        session_data.setdefault("saved_to_db", False)
        session_data.setdefault("db_status", db_status_on_fetch)
        session_data.setdefault("db_message", db_message_on_fetch)

    if session_data:
        # Check and resolve interview_mode safely
        s_mode = session_data.get("interview_mode")
        if not s_mode or s_mode not in ("CODING", "VERBAL"):
            qs = session_data.get("questions", [])
            if not qs:
                session_data["interview_mode"] = "VERBAL"
                session_data["is_unreliable_mode"] = False
            else:
                has_coding = any(
                    q.get("question_type") == "coding" or bool(q.get("test_cases"))
                    for q in qs
                )
                has_verbal = any(
                    q.get("question_type") in ("verbal", "behavioral", "conceptual")
                    or (not q.get("test_cases") and q.get("question_type") != "coding")
                    for q in qs
                )
                if has_coding and not has_verbal:
                    session_data["interview_mode"] = "CODING"
                    session_data["is_unreliable_mode"] = False
                elif has_verbal and not has_coding:
                    session_data["interview_mode"] = "VERBAL"
                    session_data["is_unreliable_mode"] = False
                else:
                    # Inconsistent/mixed question history: require safe restart
                    session_data["interview_mode"] = "AMBIGUOUS"
                    session_data["is_unreliable_mode"] = True
        else:
            session_data.setdefault("is_unreliable_mode", False)

        from app.core.problem_catalog import normalize_and_classify_question
        active_mode = session_data["interview_mode"] if not session_data.get("is_unreliable_mode") else None
        if "questions" in session_data:
            session_data["questions"] = [
                normalize_and_classify_question(q, session_mode=active_mode) for q in session_data["questions"]
            ]
            session_data = audit_and_heal_session_coding_questions(session_data)

    return session_data


def audit_and_heal_session_coding_questions(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely inspect and heal stored or cached coding questions:
    - If question matches benchmark problem catalog, enriches with verified test cases and oracle provenance.
    - If custom question has a reference solution, verifies test cases against oracle.
    - If test cases or oracle disagree or fail verification, marks quarantined without deleting candidate history or reports.
    """
    from app.core.problem_catalog import find_benchmark_problem
    from app.services.oracle_service import run_oracle_on_test_cases

    questions = session_data.get("questions", [])
    for q in questions:
        if q.get("question_type") == "coding":
            # Normalize any existing test case field names
            if q.get("test_cases"):
                for tc in q["test_cases"]:
                    if isinstance(tc, dict) and not str(tc.get("expected_output", "")).strip():
                        for alt_k in ("output", "expected", "result"):
                            if str(tc.get(alt_k, "")).strip():
                                tc["expected_output"] = str(tc[alt_k]).strip()
                                break

            has_missing_expected = (
                not q.get("test_cases")
                or any(not str(tc.get("expected_output", "")).strip() for tc in q.get("test_cases", []))
            )

            if q.get("oracle_verified") and not has_missing_expected:
                continue

            # Check benchmark problem catalog
            benchmark = find_benchmark_problem(q.get("text", ""), title=q.get("title"), q_id=q.get("id"))
            if benchmark:
                q["title"] = q.get("title") or benchmark.get("title")
                q["text"] = q.get("text") or benchmark.get("text")
                q["reference_solution"] = benchmark.get("reference_solution")
                q["test_cases"] = benchmark.get("test_cases")
                q["function_name"] = q.get("function_name") or benchmark.get("function_name")
                q["oracle_verified"] = True
                q["oracle_provenance"] = "benchmark_catalog"
                q["comparison_policy"] = benchmark.get("comparison_policy", "strict_structural")
                q["quarantined"] = False
                q["validation_error"] = None
            elif q.get("reference_solution") and q.get("function_name") and q.get("test_cases"):
                # Attempt oracle verification
                success, verified_tests, err = run_oracle_on_test_cases(
                    q["reference_solution"],
                    q["function_name"],
                    q["test_cases"],
                )
                if success:
                    q["test_cases"] = verified_tests
                    q["oracle_verified"] = True
                    q["oracle_provenance"] = "oracle_healed_v1"
                    q["quarantined"] = False
                    q["validation_error"] = None
                else:
                    q["oracle_verified"] = False
                    q["quarantined"] = True
                    q["validation_error"] = err
            else:
                q["oracle_verified"] = False
                q["quarantined"] = True
                q["validation_error"] = "Unverified legacy question lacking authoritative reference solution"

    return session_data


async def record_human_review(
    session_id: str,
    review_data: HumanReviewAuditRequest,
) -> HumanReviewAuditEntry:
    """
    Record an auditable human review note for an interview session.
    Preserved separately from candidate scores. Reviewer identity is flagged as self-declared.
    """
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    reviewer_name = (review_data.reviewer_name or "").strip() or "Anonymous Reviewer"

    entry = HumanReviewAuditEntry(
        note_id=note_id,
        reviewer_name=reviewer_name,
        is_verified_identity=False,
        identity_note="Self-declared reviewer identity (unauthenticated environment)",
        review_notes=review_data.review_notes.strip(),
        created_at=now,
    )

    entry_dict = entry.model_dump()
    entry_dict["created_at"] = now.isoformat()

    # Record in active memory session
    if session_id in _in_memory_sessions:
        if "human_reviews" not in _in_memory_sessions[session_id]:
            _in_memory_sessions[session_id]["human_reviews"] = []
        _in_memory_sessions[session_id]["human_reviews"].append(entry_dict)
        _in_memory_sessions[session_id]["updated_at"] = now.isoformat()

    # Attempt MongoDB update if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$push": {"human_reviews": entry_dict},
                    "$set": {"updated_at": now.isoformat()},
                },
            )
        except Exception as exc:
            logger.warning("MongoDB update failed for session %s human review: %s", session_id, type(exc).__name__)

    # Update active cached report if exists
    from app.services.report_service import add_human_review_to_report
    await add_human_review_to_report(session_id, entry)

    return entry


async def get_human_reviews(session_id: str) -> List[HumanReviewAuditEntry]:
    """Retrieve all human review audit entries for a session."""
    raw_reviews: List[Dict[str, Any]] = []

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            doc = await db["interview_sessions"].find_one({"session_id": session_id})
            if doc:
                raw_reviews = doc.get("human_reviews", [])
        except Exception as exc:
            logger.warning("MongoDB query failed for session %s human reviews: %s", session_id, type(exc).__name__)

    if not raw_reviews and session_id in _in_memory_sessions:
        raw_reviews = _in_memory_sessions[session_id].get("human_reviews", [])

    results: List[HumanReviewAuditEntry] = []
    for r in raw_reviews:
        created = r["created_at"]
        if isinstance(created, str):
            created_dt = datetime.fromisoformat(created)
        else:
            created_dt = created
        results.append(
            HumanReviewAuditEntry(
                note_id=r["note_id"],
                reviewer_name=r.get("reviewer_name"),
                is_verified_identity=r.get("is_verified_identity", False),
                identity_note=r.get("identity_note", "Self-declared reviewer identity (unauthenticated environment)"),
                review_notes=r["review_notes"],
                created_at=created_dt,
            )
        )
    return results


async def record_candidate_explanation(
    session_id: str,
    explanation_data: CandidateExplanationRequest,
) -> CandidateExplanationEntry:
    """
    Record an auditable candidate contextual explanation or dispute note for an interview session.
    Preserved separately from candidate scores. Candidate identity is flagged as unverified.
    """
    explanation_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    saved_to_db = False
    db_status = "unconfigured"

    entry = CandidateExplanationEntry(
        explanation_id=explanation_id,
        session_id=session_id,
        event_id=explanation_data.event_id,
        explanation=explanation_data.explanation.strip(),
        status="pending_review",
        reviewer_outcome=None,
        is_verified_identity=False,
        identity_note="Candidate-provided explanation without authenticated identity verification (unauthenticated environment)",
        created_at=now,
        saved_to_db=False,
        db_status="unconfigured",
    )

    entry_dict = entry.model_dump()
    entry_dict["created_at"] = now.isoformat()

    # Record in active memory session
    if session_id in _in_memory_sessions:
        if "candidate_explanations" not in _in_memory_sessions[session_id]:
            _in_memory_sessions[session_id]["candidate_explanations"] = []
        _in_memory_sessions[session_id]["candidate_explanations"].append(entry_dict)
        _in_memory_sessions[session_id]["updated_at"] = now.isoformat()

    # Attempt MongoDB update if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            result = await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$push": {"candidate_explanations": entry_dict},
                    "$set": {"updated_at": now.isoformat()},
                },
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
            else:
                db_status = "not_found_in_db"
        except Exception as exc:
            db_status = "unreachable"
            logger.warning(
                "MongoDB update failed for session %s candidate explanation: %s",
                session_id,
                type(exc).__name__,
            )

    entry.saved_to_db = saved_to_db
    entry.db_status = db_status

    # Update active cached report if exists
    from app.services.report_service import add_candidate_explanation_to_report
    await add_candidate_explanation_to_report(session_id, entry)

    return entry


async def get_candidate_explanations(session_id: str) -> List[CandidateExplanationEntry]:
    """Retrieve all candidate explanation entries for a session."""
    raw_explanations: List[Dict[str, Any]] = []
    saved_to_db = False
    db_status = "unconfigured"

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            doc = await db["interview_sessions"].find_one({"session_id": session_id})
            if doc:
                saved_to_db = True
                db_status = "persisted"
                raw_explanations = doc.get("candidate_explanations", [])
        except Exception as exc:
            db_status = "unreachable"
            logger.warning(
                "MongoDB query failed for session %s candidate explanations: %s",
                session_id,
                type(exc).__name__,
            )

    if not raw_explanations and session_id in _in_memory_sessions:
        raw_explanations = _in_memory_sessions[session_id].get("candidate_explanations", [])

    results: List[CandidateExplanationEntry] = []
    for item in raw_explanations:
        created = item["created_at"]
        if isinstance(created, str):
            created_dt = datetime.fromisoformat(created)
        else:
            created_dt = created

        raw_decisions = item.get("decision_history", [])
        decisions: List[ReviewerDecisionEntry] = []
        for d in raw_decisions:
            d_created = d.get("created_at")
            if isinstance(d_created, str):
                d_created_dt = datetime.fromisoformat(d_created)
            else:
                d_created_dt = d_created or datetime.now(timezone.utc)
            decisions.append(
                ReviewerDecisionEntry(
                    decision_id=d.get("decision_id", str(uuid.uuid4())),
                    explanation_id=d.get("explanation_id", item["explanation_id"]),
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

        results.append(
            CandidateExplanationEntry(
                explanation_id=item["explanation_id"],
                session_id=session_id,
                event_id=item.get("event_id"),
                explanation=item["explanation"],
                status=item.get("status", "pending_review"),
                reviewer_outcome=item.get("reviewer_outcome"),
                decision_history=decisions,
                is_verified_identity=item.get("is_verified_identity", False),
                identity_note=item.get(
                    "identity_note",
                    "Candidate-provided explanation without authenticated identity verification (unauthenticated environment)",
                ),
                created_at=created_dt,
                saved_to_db=item.get("saved_to_db", saved_to_db),
                db_status=item.get("db_status", db_status),
            )
        )
    return results


async def record_reviewer_decision(
    session_id: str,
    explanation_id: str,
    decision_data: ReviewerDecisionRequest,
) -> CandidateExplanationEntry:
    """
    Record an append-only reviewer decision for a candidate explanation.
    Preserves original candidate explanation verbatim.
    Reviewer attribution is flagged as self-declared.
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )

    # Locate the target explanation
    raw_explanations = session.get("candidate_explanations", [])
    target_exp_dict: Optional[Dict[str, Any]] = None
    for exp in raw_explanations:
        if exp.get("explanation_id") == explanation_id:
            target_exp_dict = exp
            break

    if not target_exp_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate explanation '{explanation_id}' not found in session '{session_id}'.",
        )

    decision_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    reviewer_name = (decision_data.reviewer_name or "").strip() or "Anonymous Reviewer"
    reviewer_outcome = decision_data.reviewer_outcome.strip() if decision_data.reviewer_outcome else None
    new_status = decision_data.status.value

    decision_entry = ReviewerDecisionEntry(
        decision_id=decision_id,
        explanation_id=explanation_id,
        status=new_status,
        reviewer_name=reviewer_name,
        reviewer_outcome=reviewer_outcome,
        is_verified_identity=False,
        identity_note="Self-declared reviewer identity (unauthenticated environment)",
        created_at=now,
    )
    decision_dict = decision_entry.model_dump()
    decision_dict["created_at"] = now.isoformat()

    # Update in-memory session (preserving candidate explanation text verbatim)
    target_exp_dict["status"] = new_status
    target_exp_dict["reviewer_outcome"] = reviewer_outcome
    if "decision_history" not in target_exp_dict:
        target_exp_dict["decision_history"] = []
    target_exp_dict["decision_history"].append(decision_dict)

    if session_id in _in_memory_sessions:
        _in_memory_sessions[session_id]["updated_at"] = now.isoformat()

    # Attempt MongoDB update if configured
    saved_to_db = target_exp_dict.get("saved_to_db", False)
    db_status = target_exp_dict.get("db_status", "unconfigured")
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            result = await db["interview_sessions"].update_one(
                {"session_id": session_id, "candidate_explanations.explanation_id": explanation_id},
                {
                    "$set": {
                        "candidate_explanations.$.status": new_status,
                        "candidate_explanations.$.reviewer_outcome": reviewer_outcome,
                        "updated_at": now.isoformat(),
                    },
                    "$push": {
                        "candidate_explanations.$.decision_history": decision_dict,
                    },
                },
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
        except Exception as exc:
            db_status = "unreachable"
            logger.warning(
                "MongoDB update failed for session %s explanation %s decision: %s",
                session_id,
                explanation_id,
                type(exc).__name__,
            )

    target_exp_dict["saved_to_db"] = saved_to_db
    target_exp_dict["db_status"] = db_status

    # Synchronize with cached report if it exists
    from app.services.report_service import update_report_explanation_decision
    await update_report_explanation_decision(
        session_id=session_id,
        explanation_id=explanation_id,
        decision_entry=decision_entry,
        new_status=new_status,
        new_outcome=reviewer_outcome,
    )

    # Return reconstructed CandidateExplanationEntry
    decisions = [
        ReviewerDecisionEntry(
            decision_id=d.get("decision_id", str(uuid.uuid4())),
            explanation_id=d.get("explanation_id", explanation_id),
            status=d.get("status", "reviewed"),
            reviewer_name=d.get("reviewer_name"),
            reviewer_outcome=d.get("reviewer_outcome"),
            is_verified_identity=d.get("is_verified_identity", False),
            identity_note=d.get("identity_note", "Self-declared reviewer identity (unauthenticated environment)"),
            created_at=datetime.fromisoformat(d["created_at"]) if isinstance(d["created_at"], str) else d["created_at"],
        )
        for d in target_exp_dict.get("decision_history", [])
    ]

    exp_created = target_exp_dict["created_at"]
    exp_created_dt = datetime.fromisoformat(exp_created) if isinstance(exp_created, str) else exp_created

    return CandidateExplanationEntry(
        explanation_id=target_exp_dict["explanation_id"],
        session_id=session_id,
        event_id=target_exp_dict.get("event_id"),
        explanation=target_exp_dict["explanation"],
        status=target_exp_dict["status"],
        reviewer_outcome=target_exp_dict.get("reviewer_outcome"),
        decision_history=decisions,
        is_verified_identity=target_exp_dict.get("is_verified_identity", False),
        identity_note=target_exp_dict.get(
            "identity_note",
            "Candidate-provided explanation without authenticated identity verification (unauthenticated environment)",
        ),
        created_at=exp_created_dt,
        saved_to_db=saved_to_db,
        db_status=db_status,
    )


async def save_question_draft(
    session_id: str,
    question_id: str,
    draft_data: SaveDraftRequest,
) -> SaveDraftResponse:
    """
    Autosave candidate code or SQL draft for a specific question and language.
    Guarantees out-of-order write protection via sequential version tracking.
    Persists to MongoDB Atlas if configured, and active in-memory session.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

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

    # Validate that question belongs to session
    valid_q_ids = [q["id"] for q in session.get("questions", [])]
    if valid_q_ids and question_id not in valid_q_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question '{question_id}' does not belong to session '{session_id}'.",
        )

    lang_key = draft_data.language.strip().lower()
    version = max(1, draft_data.version)
    updated_at = draft_data.updated_at or now_iso

    # Sequence / out-of-order check: prevent slow earlier request from overwriting a newer draft
    existing_drafts = session.get("drafts", {})
    existing_lang_draft = existing_drafts.get(question_id, {}).get(lang_key)
    if existing_lang_draft and isinstance(existing_lang_draft, dict):
        existing_version = existing_lang_draft.get("version", 0)
        if existing_version > version:
            logger.warning(
                "Ignoring stale draft write for session %s, question %s, lang %s (incoming v%s < existing v%s)",
                session_id, question_id, lang_key, version, existing_version,
            )
            return SaveDraftResponse(
                session_id=session_id,
                question_id=question_id,
                language=lang_key,
                version=existing_version,
                updated_at=existing_lang_draft.get("updated_at", updated_at),
                saved_to_db=session.get("saved_to_db", False),
                db_status=session.get("db_status", "unconfigured"),
                message="Stale draft version ignored in favor of newer draft.",
            )

    draft_record = {
        "code": draft_data.code,
        "language": lang_key,
        "version": version,
        "updated_at": updated_at,
    }

    # 1. Update active memory store
    if session_id in _in_memory_sessions:
        _in_memory_sessions[session_id].setdefault("drafts", {}).setdefault(question_id, {})[lang_key] = draft_record
        _in_memory_sessions[session_id]["updated_at"] = now_iso

    # 2. Update MongoDB Atlas if configured
    saved_to_db = False
    db_status = "unconfigured"
    msg = "Draft autosaved to active session memory."

    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            result = await db["interview_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        f"drafts.{question_id}.{lang_key}": draft_record,
                        "updated_at": now_iso,
                    }
                },
            )
            if result.matched_count > 0:
                saved_to_db = True
                db_status = "persisted"
                msg = "Draft autosaved and persisted to MongoDB Atlas."
            else:
                db_status = "not_found_in_db"
                msg = "Session not found in MongoDB Atlas, draft saved to active memory."
        except Exception as exc:
            db_status = "unreachable"
            msg = f"MongoDB write failed: {type(exc).__name__}. Saved to active memory."
            logger.warning("MongoDB draft save failed for session %s: %s", session_id, type(exc).__name__)

    return SaveDraftResponse(
        session_id=session_id,
        question_id=question_id,
        language=lang_key,
        version=version,
        updated_at=updated_at,
        saved_to_db=saved_to_db,
        db_status=db_status,
        message=msg,
    )


async def get_session_drafts(session_id: str) -> Dict[str, Dict[str, Any]]:
    """Retrieve all saved question drafts for an interview session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview session '{session_id}' not found.",
        )
    return session.get("drafts", {})
