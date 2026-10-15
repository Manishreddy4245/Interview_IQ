from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    """Score and feedback for an individual evaluation criterion."""

    score: int = Field(..., ge=1, le=10, description="Score on a 1-10 integer scale")
    feedback: str = Field(
        ...,
        min_length=5,
        description="Evidence-based rationale tied directly to the candidate's answer",
    )


class CriterionScores(BaseModel):
    """Detailed criterion breakdown covering technical and communication competencies."""

    relevance: CriterionScore = Field(
        ..., description="How directly and specifically the answer addresses the question asked"
    )
    technical_depth: CriterionScore = Field(
        ..., description="Technical accuracy, correctness, and domain depth of the response"
    )
    completeness: CriterionScore = Field(
        ..., description="Whether all key aspects and edge cases of the prompt were addressed"
    )
    structure_flow: CriterionScore = Field(
        ..., description="Logical sequencing, coherence, and progression of thoughts"
    )
    clarity_conciseness: CriterionScore = Field(
        ..., description="Written clarity, efficiency of expression, and absence of filler"
    )
    star_structure: Optional[CriterionScore] = Field(
        default=None,
        description="Situation, Task, Action, Result framework execution (for behavioral prompts)",
    )


class AIEvaluationRaw(BaseModel):
    """Schema for validating structured JSON output returned by the Groq model."""

    overall_score: int = Field(
        ..., ge=1, le=100, description="Overall performance score on a 1-100 scale"
    )
    criterion_scores: CriterionScores
    strengths: List[str] = Field(
        ..., min_length=1, description="Observed strengths with concrete textual evidence"
    )
    areas_for_improvement: List[str] = Field(
        ..., min_length=1, description="Specific gaps or weaknesses with evidence"
    )
    actionable_suggestions: List[str] = Field(
        ..., min_length=1, description="Concrete tips to restructure or improve the response"
    )
    coaching_summary: str = Field(
        ..., min_length=10, description="Actionable communication coaching synthesis"
    )
    stronger_example_answer: Optional[str] = Field(
        default=None,
        description="Illustrative example answer demonstrating ideal response structure and evidence",
    )
    recommended_practice: Optional[str] = Field(
        default=None,
        description="Recommended follow-up technical or behavioral practice topic",
    )
    acoustic_disclaimer: str = Field(
        default=(
            "Pronunciation, pitch, vocal confidence, and acoustic voice-quality analysis "
            "were not performed. Evaluation is strictly based on the recognized transcript text."
        ),
        description="Explicit disclaimer clarifying evaluation boundary",
    )


class EvaluateAnswerRequest(BaseModel):
    """Request payload to trigger an evaluation."""

    question_id: Optional[str] = Field(
        default=None,
        description="Target question identifier being evaluated",
    )
    answer_text: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Optional updated answer text; if omitted, the stored session answer is evaluated",
    )
    answer_mode: Optional[str] = Field(
        default=None,
        description="Mode of submission: 'coding', 'sql', 'system_design', or 'verbal'",
    )
    code: Optional[str] = Field(
        default=None,
        description="Source code when evaluating coding solutions",
    )
    language: Optional[str] = Field(
        default=None,
        description="Programming language for coding solutions",
    )
    sql_query: Optional[str] = Field(
        default=None,
        description="SQL query string when evaluating SQL solutions",
    )


class AnswerEvaluationResponse(BaseModel):
    """Full evaluation payload returned to frontend."""

    session_id: str
    question_id: str
    overall_score: int = Field(..., ge=1, le=100)
    criterion_scores: CriterionScores
    strengths: List[str]
    areas_for_improvement: List[str]
    actionable_suggestions: List[str]
    coaching_summary: str
    stronger_example_answer: Optional[str] = None
    recommended_practice: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    saved_to_db: bool = Field(
        ..., description="True if evaluation was persisted to MongoDB Atlas; False otherwise"
    )
    db_status: str = Field(
        ..., description="Database persistence status: 'persisted', 'unconfigured', or 'unreachable'"
    )
    db_message: Optional[str] = None
    decision_support_disclaimer: str = Field(
        default="AI evaluation provides advisory feedback and coaching evidence. It is a decision support signal, not an automated or definitive hiring decision.",
        description="Explicit guarantee that AI evaluation serves as decision support, not an automated hiring mandate.",
    )
    acoustic_disclaimer: str = Field(
        default=(
            "Pronunciation, pitch, vocal confidence, and acoustic voice-quality analysis "
            "were not performed. Evaluation is strictly based on the recognized transcript text."
        ),
        description="Explicit disclaimer clarifying evaluation boundary",
    )
