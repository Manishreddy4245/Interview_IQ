from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class CompetencyEvidenceItem(BaseModel):
    """Grounding item for a skill or competency with verbatim evidence."""
    skill_name: str
    status: str = Field(..., description="e.g. 'Demonstrated', 'Gap / Needs Validation', 'Partially Evidenced'")
    category: Optional[str] = None
    evidence_text: Optional[str] = None
    source_type: str = Field(default="resume", description="'resume' or 'interview_answer'")
    role_importance: Optional[str] = None


class DecisionCriterionSummary(BaseModel):
    """Criterion scores aggregated strictly from real evaluated data."""
    relevance: Optional[float] = None
    technical_depth: Optional[float] = None
    completeness: Optional[float] = None
    structure_flow: Optional[float] = None
    clarity_conciseness: Optional[float] = None
    star_structure: Optional[float] = None


class HumanReviewDecisionRecord(BaseModel):
    """Append-only record of a human hiring manager's determination."""
    decision_id: str
    reviewer_name: str
    recommendation: str = Field(..., description="e.g. 'Advance', 'Follow-up Required', 'Practical Assessment Needed', 'Hold'")
    notes: Optional[str] = None
    timestamp: datetime


class HumanReviewDecisionRequest(BaseModel):
    """Payload to record a human reviewer determination."""
    reviewer_name: str = Field(..., min_length=2, max_length=100)
    recommendation: str = Field(..., min_length=2, max_length=100)
    notes: Optional[str] = Field(default="", max_length=1000)


class CandidateDossierItem(BaseModel):
    """Unified evidence-grounded candidate decision profile."""
    record_id: str
    record_type: str = Field(..., description="'resume_analysis', 'interview_report', or 'interview_session'")
    candidate_identifier: str = Field(..., description="Verified candidate identity or anonymous record label")
    target_role: str
    experience_level: str
    created_at: Optional[datetime] = None
    overall_score: Optional[float] = None
    scoring_status: str = Field(default="Evaluated", description="'Evaluated', 'Pending Evaluation', or 'Resume Analysis'")
    criterion_scores: DecisionCriterionSummary = Field(default_factory=DecisionCriterionSummary)
    demonstrated_competencies: List[CompetencyEvidenceItem] = Field(default_factory=list)
    competency_gaps: List[CompetencyEvidenceItem] = Field(default_factory=list)
    key_strengths: List[str] = Field(default_factory=list)
    critical_improvements: List[str] = Field(default_factory=list)
    executive_summary: Optional[str] = None
    integrity_event_count: int = 0
    cumulative_unfocused_seconds: Optional[float] = 0.0
    linked_resume_id: Optional[str] = None
    linked_session_id: Optional[str] = None
    human_reviews: List[HumanReviewDecisionRecord] = Field(default_factory=list)


class DecisionOverviewResponse(BaseModel):
    """Overview payload containing all real available candidate records."""
    total_records: int
    resume_analyses_count: int
    interview_reports_count: int
    interview_sessions_count: int
    dossiers: List[CandidateDossierItem]
