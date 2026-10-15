from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DimensionDetail(BaseModel):
    """Detailed score and qualitative feedback for a specific communication dimension."""
    score: int = Field(default=8, ge=1, le=10, description="Criterion rating between 1 and 10")
    feedback: str = Field(..., description="Actionable qualitative feedback for this dimension")


class TranscriptMetrics(BaseModel):
    """Objective textual and pacing metrics derived from the transcript."""
    word_count: int = Field(default=0, description="Total word count in transcript")
    speaking_duration_seconds: Optional[float] = Field(
        default=None,
        description="Measured or estimated speaking duration in seconds",
    )
    words_per_minute: Optional[float] = Field(
        default=None,
        description="Speaking rate in words per minute",
    )
    filler_word_count: int = Field(default=0, description="Total count of identifiable vocal fillers")
    filler_words_detected: Dict[str, int] = Field(
        default_factory=dict,
        description="Identified filler words and their respective occurrence counts",
    )


class CommunicationCoachRequest(BaseModel):
    """Request payload for speech-to-text communication coaching and review."""

    message: Optional[str] = Field(
        default=None,
        description="The candidate's coaching request, query, or practice goal",
    )
    transcript: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="The candidate's spoken or edited transcript to be reviewed",
    )
    practice_task: str = Field(
        default="question",
        description="Practice task mode: 'question', 'introduction', 'improve_answer', or 'technical_concept'",
    )
    task_prompt: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="The specific question, introduction prompt, or technical concept being addressed",
    )
    context_type: str = Field(
        default="general",
        description="Contextual grounding type: 'general', 'answer', 'evaluation', or 'star_practice'",
    )
    context_text: Optional[str] = Field(
        default=None,
        max_length=8000,
        description="Optional prior answer, question text, or evaluation feedback to ground coaching in",
    )
    target_role: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Target job role for tailored tone and terminology (e.g. 'Senior Full Stack Engineer')",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional linked interview session ID",
    )
    recording_duration_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=3600.0,
        description="Elapsed recording duration in seconds measured by the client timer",
    )


class CommunicationCoachResponse(BaseModel):
    """Comprehensive response payload containing structured communication evaluation."""

    summary: str = Field(
        default="Structured communication review completed.",
        description="Concise overall evaluation of the candidate's spoken communication delivery",
    )
    coaching_advice: str = Field(
        ...,
        description="Core coaching guidance on clarity, structure, tone, or feedback explanation",
    )
    dimension_scores: Dict[str, DimensionDetail] = Field(
        default_factory=dict,
        description="Evaluations across Clarity, Structure, Conciseness, Professional Language, and Relevance",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Key communication strengths evidenced in the response",
    )
    areas_for_improvement: List[str] = Field(
        default_factory=list,
        description="Concrete areas where the candidate can tighten or polish delivery",
    )
    actionable_tips: List[str] = Field(
        default_factory=list,
        description="Bullet-point actionable rules for immediate application",
    )
    star_breakdown: Optional[Dict[str, str]] = Field(
        default=None,
        description="STAR format breakdown: situation, task, action, result",
    )
    suggested_revision: Optional[str] = Field(
        default=None,
        description="Actionable example response illustrating the coaching recommendations",
    )
    next_practice_exercise: Optional[str] = Field(
        default=None,
        description="Targeted follow-up exercise for focused deliberate practice",
    )
    transcript_metrics: Optional[TranscriptMetrics] = Field(
        default=None,
        description="Objective transcript metrics: word count, estimated speaking rate, and identified filler words",
    )
    clarity_focus: str = Field(
        default="Structure & Impact",
        description="Primary communication dimension addressed",
    )
    grounded_in_evidence: bool = Field(
        default=False,
        description="True if feedback is directly grounded in recorded candidate answer text; False if general advice",
    )
    disclaimer: str = Field(
        default=(
            "Evaluation is based strictly on transcript text clarity, structure, conciseness, and tone. "
            "Acoustic features (pitch, voice tone, spoken pacing, acoustic confidence) and pronunciation were not assessed from plain text. "
            "Coaching feedback is provided solely for practice and preparation; it does not modify interview evaluation scores, integrity records, or reviewer hiring decisions."
        ),
        description="Transparency guarantee on acoustic limitations and score isolation",
    )
    evaluation_mode: str = Field(
        default="ai",
        description="Mode of evaluation: 'ai' if evaluated by Groq, or 'deterministic_fallback' if rate-limited or offline",
    )
