import pytest
from datetime import datetime, timezone
from app.schemas.interview import InterviewSetupRequest, QuestionItem, QuestionType
from app.schemas.integrity import (
    IntegrityEventType,
    IntegrityEventCreate,
    IntegrityEventRecord,
)
from app.schemas.report import PotentialCommunicationEventRecord
from app.services.session_service import (
    create_interview_session,
    record_integrity_event,
    get_integrity_events,
    get_session,
    _in_memory_sessions,
)
from app.services.report_service import generate_interview_report


def test_integrity_event_types_and_payload_serialization():
    """Verify that all new proctoring and integrity event types serialize and persist with rich metadata."""
    create_payload = IntegrityEventCreate(
        event_type=IntegrityEventType.MULTIPLE_FACES_DETECTED,
        question_id="q_101",
        details={"faces_count": 2, "bounding_boxes": [[10, 10, 50, 50], [70, 70, 50, 50]]},
        severity="warning",
        duration_seconds=5.2,
        detection_source="browser_face_detector",
        detection_confidence=0.88,
        status="active",
    )
    data = create_payload.model_dump()
    assert data["event_type"] == "multiple_faces_detected"
    assert data["severity"] == "warning"
    assert data["duration_seconds"] == 5.2
    assert data["detection_source"] == "browser_face_detector"
    assert data["detection_confidence"] == 0.88
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_deduplication_and_rich_metadata_persistence():
    """Verify that continuous identical active events are debounced/deduplicated while preserving duration."""
    setup = InterviewSetupRequest(
        role="Frontend Engineer",
        experience_level="Mid-Level",
        duration_minutes=30,
        interview_mode="VERBAL",
        question_count=3,
        focus_areas="React, TypeScript",
    )
    questions = [
        QuestionItem(
            id="q_1",
            text="Explain the virtual DOM diffing algorithm.",
            difficulty="medium",
            topic="React",
            question_type=QuestionType.VERBAL,
        )
    ]
    session = await create_interview_session(setup=setup, questions=questions)
    sess_id = session.session_id

    # First event: candidate not visible
    ev1 = await record_integrity_event(
        sess_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.FACE_NOT_DETECTED,
            question_id="q_1",
            details={"reason": "sustained_absence"},
            severity="warning",
            duration_seconds=5.0,
            detection_source="canvas_cascade_analyzer",
            detection_confidence=0.9,
            status="active",
        ),
    )
    assert ev1.event_type == IntegrityEventType.FACE_NOT_DETECTED
    assert ev1.duration_seconds == 5.0
    assert ev1.status == "active"

    # Rapid repeated active event within 3 seconds (simulating 600ms tick updates)
    ev2 = await record_integrity_event(
        sess_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.FACE_NOT_DETECTED,
            question_id="q_1",
            details={"reason": "sustained_absence"},
            severity="warning",
            duration_seconds=6.2,
            detection_source="canvas_cascade_analyzer",
            detection_confidence=0.9,
            status="active",
        ),
    )
    # Deduplication updates the existing active incident rather than creating another DB record
    assert ev2.event_id == ev1.event_id
    assert ev2.duration_seconds == 6.2

    # Recovery event
    ev3 = await record_integrity_event(
        sess_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.CANDIDATE_VISIBILITY_RECOVERED,
            question_id="q_1",
            details={"return_delay_seconds": 6.2},
            severity="info",
            duration_seconds=6.2,
            detection_source="canvas_cascade_analyzer",
            status="resolved",
        ),
    )
    assert ev3.event_type == IntegrityEventType.CANDIDATE_VISIBILITY_RECOVERED
    assert ev3.status == "resolved"

    # Fetch full timeline
    timeline = await get_integrity_events(sess_id)
    # Should have ev1 (updated with 6.2s duration) and ev3 (recovery)
    assert len(timeline.events) == 2
    assert timeline.events[0].duration_seconds == 6.2
    assert timeline.events[1].status == "resolved"


@pytest.mark.asyncio
async def test_potential_communication_event_in_report_and_score_neutrality():
    """Verify that possible external communication events are surfaced under integrity summary without score penalty."""
    setup = InterviewSetupRequest(
        role="Full Stack Engineer",
        experience_level="Senior",
        duration_minutes=45,
        interview_mode="VERBAL",
        question_count=3,
        focus_areas="Distributed Systems",
    )
    questions = [
        QuestionItem(
            id="q_cache",
            text="How would you design a distributed cache?",
            difficulty="hard",
            topic="System Design",
            question_type=QuestionType.VERBAL,
        )
    ]
    session = await create_interview_session(setup=setup, questions=questions)
    sess_id = session.session_id

    # Add question answers and evaluations in session doc
    raw_sess = _in_memory_sessions[sess_id]
    raw_sess["answers"]["q_cache"] = {
        "answer_text": "I would design a distributed caching layer using Redis clusters with consistent hashing.",
        "evaluation": {
            "overall_score": 88,
            "strengths": ["Clear architectural understanding", "Mentions consistent hashing"],
            "growth_areas": ["Could detail cache invalidation"],
            "criterion_scores": {
                "relevance": {"score": 9, "feedback": "Highly relevant answer to the prompt."},
                "technical_depth": {"score": 9, "feedback": "Demonstrates thorough technical depth in caching."},
                "completeness": {"score": 8, "feedback": "Comprehensive coverage of distributed concepts."},
                "structure_flow": {"score": 9, "feedback": "Well-structured architectural delivery."},
                "clarity_conciseness": {"score": 9, "feedback": "Clear explanation of cache trade-offs."},
            },
        },
    }

    # Log secondary person detection
    await record_integrity_event(
        sess_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.MULTIPLE_FACES_DETECTED,
            question_id="q_cache",
            details={"count": 2},
            severity="warning",
            duration_seconds=4.0,
            detection_source="browser_face_detector",
            status="active",
        ),
    )

    # Log possible external communication event
    await record_integrity_event(
        sess_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.POSSIBLE_EXTERNAL_COMMUNICATION,
            question_id="q_cache",
            details={"transcript_snippet": "Can you give me the answer for the cache?"},
            severity="warning",
            duration_seconds=3.5,
            detection_source="multimodal_correlation",
            detection_confidence=0.82,
            status="active",
        ),
    )

    # Generate final report
    report = await generate_interview_report(sess_id)
    assert report is not None
    assert report.session_id == sess_id

    # 1. Total score is based strictly on evaluated technical answers (88) and NOT penalized by telemetry
    assert report.overall_score == 88

    # 2. Potential communication events section is populated for human review
    comm_events = report.integrity_summary.potential_communication_events
    assert len(comm_events) >= 1
    target_event = comm_events[0]
    assert target_event.review_status in ("active", "potential_concern_requiring_human_review")
    assert target_event.duration_seconds == 3.5
    assert target_event.evidence_source == "multimodal_correlation"
    assert "dialogue" in target_event.event_description.lower() or "communication" in target_event.event_description.lower()

    # 3. Neutral disclaimer preserves observation fairness
    assert "not proof of dishonesty" in report.integrity_summary.neutral_disclaimer
    assert "excluded" in report.integrity_summary.score_impact.lower()


@pytest.mark.asyncio
async def test_detector_limitation_is_not_reported_as_malpractice():
    """Verify that detector failures are labeled as monitoring limitations, not malpractice."""
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Junior",
        duration_minutes=30,
        interview_mode="VERBAL",
        question_count=3,
        focus_areas="APIs",
    )
    questions = [
        QuestionItem(
            id="q_junior",
            text="Explain REST vs GraphQL.",
            difficulty="easy",
            topic="API",
            question_type=QuestionType.VERBAL,
        )
    ]
    session = await create_interview_session(setup=setup, questions=questions)
    sess_id = session.session_id

    ev = await record_integrity_event(
        sess_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.DETECTOR_UNAVAILABLE,
            details={"reason": "browser_permissions_restricted"},
            severity="informational",
            status="unresolved",
        ),
    )
    assert ev.event_type == IntegrityEventType.DETECTOR_UNAVAILABLE
    assert ev.severity == "informational"

    report = await generate_interview_report(sess_id)
    assert report is not None
    # No potential communication alerts fabricated from a detector failure
    assert len(report.integrity_summary.potential_communication_events) == 0
