from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class SkillEvidenceCategory(str, Enum):
    """The 4 required skill gap evidence classifications."""
    DEMONSTRATED = "Demonstrated in resume"
    INSUFFICIENTLY_EVIDENCED = "Mentioned but insufficiently evidenced"
    NOT_DEMONSTRATED = "Not demonstrated in resume"
    REQUIRES_VALIDATION = "Requires interview validation"


class RoleBenchmarkCompetency(BaseModel):
    """An expected competency or skill requirement for the target job role."""
    skill_name: str = Field(..., description="Name of the skill or technical competency expected for the role")
    normalized_skill: Optional[str] = Field(default=None, description="Canonical normalized skill name")
    importance: str = Field(default="Core", description="'Core', 'Recommended', or 'Advanced'")
    expected_proficiency: Optional[str] = Field(default="Intermediate", description="'Foundational', 'Intermediate', 'Advanced', 'Expert'")
    description: Optional[str] = Field(default="", description="Why this competency is relevant or expected for the role")


class TargetRoleBenchmark(BaseModel):
    """Structured benchmark of competencies expected for the selected target role."""
    target_role: str = Field(..., description="Target job title")
    experience_level: str = Field(default="Mid-Level", description="Target seniority/level")
    expected_competencies: List[RoleBenchmarkCompetency] = Field(default_factory=list)
    benchmark_source: str = Field(
        default="AI-synthesized role profile (informative baseline, not an official industry standard)",
        description="Transparent disclosure of the benchmark origin",
    )
    disclaimer: str = Field(
        default=(
            "This competency benchmark is synthesized by AI as an indicative baseline for assessment planning. "
            "It is not an official industry standard or verified employer requirement. "
            "Absence from a candidate's resume does not imply lack of ability."
        ),
        description="Standard fairness and non-prejudice disclosure",
    )


class SkillEvidenceItem(BaseModel):
    """Specific skill evaluation against target role expectations."""
    skill_name: str = Field(..., description="Name of the skill or technical competency")
    normalized_skill: Optional[str] = Field(
        default=None,
        description="Canonical normalized skill name",
    )
    category: SkillEvidenceCategory = Field(
        ...,
        description="One of the 4 standard skill evidence classifications",
    )
    evidence: str = Field(
        ...,
        description="Specific excerpt, project reference, or explanation of why evidence is lacking",
    )
    relevance_to_role: str = Field(
        ...,
        description="Explanation of why this skill is relevant to the target job role",
    )
    is_source_grounded: bool = Field(
        default=False,
        description="True if evidence was verified directly against extracted resume text",
    )
    evidence_type: str = Field(
        default="inferred_summary",
        description="'verbatim_quote' if grounded in resume text, 'inferred_summary' if summary, or 'unverified'",
    )
    source_excerpt: Optional[str] = Field(
        default=None,
        description="Direct matching passage or snippet located in the candidate resume",
    )
    is_expected_for_role: bool = Field(
        default=False,
        description="True if this skill is identified as an expected competency for the target role",
    )
    classification_rationale: Optional[str] = Field(
        default=None,
        description="Deterministic explanation for the assigned skill-gap category",
    )
    requires_interview_validation: bool = Field(
        default=False,
        description="True if practical competency needs to be assessed or confirmed during live interview",
    )


class PersonalizedQuestionItem(BaseModel):
    """Personalized follow-up interview question derived from resume analysis."""
    id: str = Field(..., description="Unique question ID, e.g., 'q_1'")
    question_number: int = Field(..., ge=1, description="Sequential index")
    text: str = Field(..., min_length=10, description="Full interview question text")
    assessed_skill: str = Field(..., description="Target skill or gap being examined")
    normalized_skill: Optional[str] = Field(
        default=None,
        description="Canonical normalized skill name for consistent mapping and tracking",
    )
    gap_category: Optional[str] = Field(
        default=None,
        description="Gap classification or validation reason (e.g. 'Requires Interview Validation')",
    )
    role_relevance: Optional[str] = Field(
        default=None,
        description="Target-role relevance or justification for asking about this competency",
    )
    source_evidence: Optional[str] = Field(
        default=None,
        description="Grounded resume evidence excerpt or note if evidence was lacking",
    )
    difficulty: str = Field(default="Medium", description="Question difficulty")
    rubric: str = Field(..., description="Key indicators for an effective answer")
    rationale: str = Field(
        ...,
        description="Explanation of why this question was formulated based on the candidate's resume",
    )


class AIRawSkillGapOutput(BaseModel):
    """Schema for validating raw LLM JSON response from Groq."""
    target_role_benchmark: Optional[TargetRoleBenchmark] = Field(
        default=None,
        description="Benchmark of expected competencies for the target role",
    )
    extracted_skills: List[str] = Field(
        ...,
        description="Skills and technologies explicitly mentioned in the resume",
    )
    projects_and_experience: List[str] = Field(
        ...,
        description="Key projects or career experiences extracted from the resume",
    )
    education: List[str] = Field(default_factory=list, description="Academic degrees, universities, education extracted from resume")
    work_experience: List[str] = Field(default_factory=list, description="Work history, internships, roles extracted from resume")
    certifications: List[str] = Field(default_factory=list, description="Certifications and credentials extracted from resume")
    skill_evaluations: List[SkillEvidenceItem] = Field(
        ...,
        description="Structured classification of candidate skills against target role",
    )
    personalized_questions: List[PersonalizedQuestionItem] = Field(
        default_factory=list,
        description="Targeted follow-up questions formulated from the resume evidence and gaps",
    )
    role_readiness_summary: str = Field(
        default="",
        description="Objective, neutral summary of resume alignment with role without arbitrary scores",
    )
    is_truncated: bool = Field(
        default=False,
        description="True if resume text exceeded limit and was safely truncated",
    )
    analyzed_character_count: Optional[int] = Field(
        default=None,
        description="Character count analyzed from resume",
    )


class ResumeAnalysisResult(BaseModel):
    """Complete resume-to-role skill gap analysis payload returned to client."""
    analysis_id: str = Field(..., description="Unique UUID for this analysis")
    owner_id: Optional[str] = Field(default=None, description="Authenticated candidate user ID who owns this analysis")
    target_role: str = Field(..., description="Target job title")
    experience_level: str = Field(default="Mid-Level", description="Experience level selected")
    target_role_benchmark: Optional[TargetRoleBenchmark] = Field(
        default=None,
        description="Benchmark of expected competencies for the target role",
    )
    extracted_skills: List[str]
    projects_and_experience: List[str]
    education: List[str] = Field(default_factory=list)
    work_experience: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    skill_evaluations: List[SkillEvidenceItem]
    personalized_questions: List[PersonalizedQuestionItem]
    role_readiness_summary: str
    is_truncated: bool = Field(
        default=False,
        description="True if resume text exceeded limit and was safely truncated",
    )
    analyzed_character_count: Optional[int] = Field(
        default=None,
        description="Character count analyzed from resume",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    saved_to_db: bool = Field(
        ...,
        description="True if analysis was persisted to MongoDB Atlas; False if active in memory only",
    )
    db_status: str = Field(
        ...,
        description="Database persistence status: 'persisted', 'unconfigured', or 'unreachable'",
    )
    db_message: Optional[str] = Field(
        default=None,
        description="Diagnostic explanation regarding database persistence",
    )


class UpdateExtractedSkillsRequest(BaseModel):
    """Candidate manual correction of extracted skills before proceeding."""
    skills: List[str] = Field(..., min_length=1, description="Candidate-verified list of skills")


class SelectTargetRoleRequest(BaseModel):
    """Candidate selection of target job role and seniority level."""
    target_role: str = Field(..., min_length=2, max_length=100, description="Target job title from catalogue")
    experience_level: Optional[str] = Field(default="Mid-Level", description="Target seniority level")


class StartInterviewFromResumeRequest(BaseModel):
    """Optional configuration for starting an interview session from a resume analysis."""
    adaptive: bool = Field(
        default=False,
        description="Enable dynamic adaptive difficulty progression instead of pre-generated static questions",
    )
    difficulty: Optional[str] = Field(
        default=None,
        description="Initial difficulty level (Easy, Medium, Hard). Defaults to analysis level or Medium.",
    )
    question_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Number of questions to configure for the session. Defaults to 5.",
    )
    interview_mode: Optional[str] = Field(
        default="VERBAL",
        description="Interview mode: 'CODING' or 'VERBAL'",
    )

    @field_validator("interview_mode", mode="before")
    @classmethod
    def validate_interview_mode(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            return "VERBAL"
        val = v.strip().upper()
        if val in ("CODING", "CODE", "PROGRAMMING"):
            return "CODING"
        return "VERBAL"


class StartInterviewFromResumeResponse(BaseModel):
    """Response returned when an interview session is initiated from a resume analysis."""
    session_id: str
    analysis_id: str
    role: str
    experience_level: str
    difficulty: str
    focus_areas: str
    question_count: int
    is_adaptive: bool = Field(default=False, description="True if adaptive interview mode was selected")
    saved_to_db: bool
    db_status: str
    message: str
