from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class IntegrityEventType(str, Enum):
    """Allowed observable browser and session integrity event types."""

    # Tab & Window Lifecycle
    TAB_HIDDEN = "tab_hidden"
    TAB_VISIBLE = "tab_visible"
    WINDOW_BLUR = "window_blur"
    WINDOW_FOCUS = "window_focus"

    # Media Permissions & Stream Lifecycle
    CAMERA_MIC_GRANTED = "camera_mic_granted"
    CAMERA_MIC_DENIED = "camera_mic_denied"
    CAMERA_PERMISSION_DENIED = "camera_permission_denied"
    CAMERA_UNAVAILABLE = "camera_unavailable"
    MEDIA_TRACK_ENDED = "media_track_ended"
    VIDEO_TRACK_STOPPED = "video_track_stopped"
    VIDEO_TRACK_ENDED = "video_track_ended"
    STREAM_INTERRUPTED = "stream_interrupted"
    STREAM_RECOVERED = "stream_recovered"

    # Face Presence & Visibility
    FACE_NOT_DETECTED = "face_not_detected"
    CANDIDATE_OUT_OF_FRAME = "candidate_out_of_frame"
    FACE_DETECTED = "face_detected"
    CANDIDATE_VISIBILITY_RECOVERED = "candidate_visibility_recovered"

    # Secondary Person Monitoring
    MULTIPLE_FACES_DETECTED = "multiple_faces_detected"
    MULTIPLE_FACES_RESOLVED = "multiple_faces_resolved"

    # Potential External Communication
    POSSIBLE_EXTERNAL_COMMUNICATION = "possible_external_communication"
    COMMUNICATION_ALERT_CLEARED = "communication_alert_cleared"

    # Detector & Service Availability
    DETECTOR_UNAVAILABLE = "detector_unavailable"
    DETECTION_SERVICE_UNAVAILABLE = "detection_service_unavailable"

    # Session Lifecycle
    PRACTICE_STARTED = "practice_started"
    PRACTICE_PAUSED = "practice_paused"
    SESSION_COMPLETED = "session_completed"
    INTERVIEW_STARTED = "interview_started"
    INTERVIEW_PAUSED = "interview_paused"
    INTERVIEW_RESUMED = "interview_resumed"
    INTERVIEW_COMPLETED = "interview_completed"
    INTERVIEW_TERMINATED = "interview_terminated"


class IntegrityEventCreate(BaseModel):
    """Payload for submitting an observable integrity event."""

    event_type: IntegrityEventType = Field(
        ...,
        description="Type of observable browser or media lifecycle event",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="ISO timestamp of the event",
    )
    question_id: Optional[str] = Field(
        default=None,
        description="Optional ID of the active interview question when event was observed",
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Neutral context details, e.g. device label or track status",
    )
    severity: Optional[str] = Field(
        default="info",
        description="Event severity category: 'info', 'warning', or 'critical'",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration of the incident in seconds where measurable",
    )
    detection_source: Optional[str] = Field(
        default=None,
        description="Sensor, detector, or subsystem reporting the event",
    )
    detection_confidence: Optional[float] = Field(
        default=None,
        description="Confidence score for automated detections (0.0 - 1.0)",
    )
    status: Optional[str] = Field(
        default="recorded",
        description="Current state of the event: 'active', 'resolved', 'requiring_review', or 'recorded'",
    )


class IntegrityEventRecord(BaseModel):
    """Stored integrity event model."""

    event_id: str = Field(..., description="Unique event identifier")
    session_id: str = Field(..., description="Associated interview session ID")
    question_id: Optional[str] = Field(
        default=None,
        description="Associated interview question ID, or None if session-level",
    )
    event_type: IntegrityEventType
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    saved_to_db: bool = Field(
        ..., description="True if persisted to MongoDB Atlas; False if active memory only"
    )
    db_status: str = Field(
        ..., description="Database persistence status: 'persisted', 'unconfigured', or 'unreachable'"
    )
    severity: Optional[str] = Field(
        default="info",
        description="Event severity category: 'info', 'warning', or 'critical'",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration of the incident in seconds where measurable",
    )
    detection_source: Optional[str] = Field(
        default=None,
        description="Sensor, detector, or subsystem reporting the event",
    )
    detection_confidence: Optional[float] = Field(
        default=None,
        description="Confidence score for automated detections (0.0 - 1.0)",
    )
    status: Optional[str] = Field(
        default="recorded",
        description="Current state of the event: 'active', 'resolved', 'requiring_review', or 'recorded'",
    )


class HumanReviewAuditEntry(BaseModel):
    """Auditable log entry recorded by a human reviewer."""

    note_id: str = Field(..., description="Unique UUID for this review entry")
    reviewer_name: Optional[str] = Field(
        default=None,
        description="Self-declared reviewer identifier (unauthenticated in current environment)",
    )
    is_verified_identity: bool = Field(
        default=False,
        description="Explicitly indicates reviewer identity is self-declared without verified SSO/JWT authentication",
    )
    identity_note: str = Field(
        default="Self-declared reviewer identity (unauthenticated environment)",
        description="Explicit limitation documentation regarding reviewer authentication",
    )
    review_notes: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Human contextual observations, notes, or explanations",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of reviewer note submission",
    )


class HumanReviewAuditRequest(BaseModel):
    """Payload for submitting a human review audit note."""

    reviewer_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional reviewer identifier or role title (self-declared)",
    )
    review_notes: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Contextual review notes regarding observable telemetry",
    )

    @field_validator("review_notes")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Review notes cannot be empty or contain only whitespace.")
        if len(trimmed) < 5:
            raise ValueError("Review notes must contain at least 5 non-whitespace characters.")
        return trimmed


class IntegrityEventsResponse(BaseModel):
    """Timeline response containing observed session events."""

    session_id: str
    events: List[IntegrityEventRecord]
    total_events: int
    saved_to_db: bool
    db_status: str
    db_message: Optional[str] = None


class CandidateExplanationRequest(BaseModel):
    """Payload for submitting a candidate explanation regarding observable telemetry."""

    event_id: Optional[str] = Field(
        default=None,
        description="Optional ID of specific integrity event being explained or disputed. None for session-level context.",
    )
    explanation: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Candidate-provided contextual explanation for observable telemetry",
    )

    @field_validator("explanation")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Explanation cannot be empty or contain only whitespace.")
        if len(trimmed) < 5:
            raise ValueError("Explanation must contain at least 5 non-whitespace characters.")
        return trimmed


class CandidateExplanationEntry(BaseModel):
    """Auditable candidate explanation entry attached to session or specific event."""

    explanation_id: str = Field(..., description="Unique UUID for this explanation entry")
    session_id: str = Field(..., description="Associated interview session ID")
    event_id: Optional[str] = Field(
        default=None,
        description="Optional ID of specific integrity event; None if session-level context",
    )
    explanation: str = Field(
        ...,
        description="Candidate-provided context or explanation regarding telemetry signals",
    )
    status: str = Field(
        default="pending_review",
        description="Review status: 'pending_review' or 'reviewed'. Never auto-accepted or auto-rejected.",
    )
    reviewer_outcome: Optional[str] = Field(
        default=None,
        description="Optional recorded human reviewer decision or note. None while pending review.",
    )
    decision_history: List["ReviewerDecisionEntry"] = Field(
        default_factory=list,
        description="Append-only audit trail of recorded reviewer decisions",
    )
    is_verified_identity: bool = Field(
        default=False,
        description="Indicates candidate identity is unverified in unauthenticated environment",
    )
    identity_note: str = Field(
        default="Candidate-provided explanation without authenticated identity verification (unauthenticated environment)",
        description="Explicit limitation documentation regarding candidate authentication",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of candidate explanation submission",
    )
    saved_to_db: bool = Field(
        default=False,
        description="True if persisted to MongoDB Atlas; False if active memory only",
    )
    db_status: str = Field(
        default="unconfigured",
        description="Database persistence status: 'persisted', 'unconfigured', or 'unreachable'",
    )


class ReviewStatus(str, Enum):
    """Allowed review outcome status for candidate explanations."""

    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"


class ReviewerDecisionEntry(BaseModel):
    """Auditable review decision entry in the append-only decision trail."""

    decision_id: str = Field(..., description="Unique UUID for this review decision")
    explanation_id: str = Field(..., description="Target candidate explanation UUID")
    status: str = Field(..., description="Review outcome status: 'reviewed' or 'pending_review'")
    reviewer_name: Optional[str] = Field(
        default=None,
        description="Self-declared reviewer identity (unauthenticated in current environment)",
    )
    reviewer_outcome: Optional[str] = Field(
        default=None,
        description="Optional human reviewer finding, determination, or contextual note",
    )
    is_verified_identity: bool = Field(
        default=False,
        description="Explicitly indicates reviewer identity is self-declared without verified SSO/JWT authentication",
    )
    identity_note: str = Field(
        default="Self-declared reviewer identity (unauthenticated environment)",
        description="Explicit limitation documentation regarding reviewer authentication",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of review decision submission",
    )


class ReviewerDecisionRequest(BaseModel):
    """Payload for recording a human reviewer decision on a candidate explanation."""

    status: ReviewStatus = Field(
        default=ReviewStatus.REVIEWED,
        description="New review status. Must be 'reviewed' or 'pending_review'.",
    )
    reviewer_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional self-declared reviewer name or role title",
    )
    reviewer_outcome: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional reviewer determination or context note regarding candidate explanation",
    )

    @field_validator("reviewer_outcome")
    @classmethod
    def validate_reviewer_outcome(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Reviewer outcome note cannot be empty or contain only whitespace when provided.")
        if len(trimmed) < 5:
            raise ValueError("Reviewer outcome note must contain at least 5 non-whitespace characters.")
        return trimmed


CandidateExplanationEntry.model_rebuild()
