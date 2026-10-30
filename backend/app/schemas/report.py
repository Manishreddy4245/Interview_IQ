from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.schemas.evaluation import CriterionScores
from app.schemas.integrity import (
    IntegrityEventRecord,
    HumanReviewAuditEntry,
    CandidateExplanationEntry,
    ReviewerDecisionEntry,
)


class CriterionAverageScores(BaseModel):
    """Average criterion scores aggregated strictly from evaluated answers."""
    relevance: Optional[float] = Field(default=None, description="Average relevance score (1-10)")
    technical_depth: Optional[float] = Field(default=None, description="Average technical depth score (1-10)")
    completeness: Optional[float] = Field(default=None, description="Average completeness score (1-10)")
    structure_flow: Optional[float] = Field(default=None, description="Average structure and flow score (1-10)")
    clarity_conciseness: Optional[float] = Field(default=None, description="Average clarity and conciseness score (1-10)")
    star_structure: Optional[float] = Field(default=None, description="Average STAR behavioral framework score (1-10)")


class ExecutiveSummaryDetails(BaseModel):
    """Deep-dive executive performance summary and readiness assessment."""
    overall_score: Optional[float] = Field(default=None, description="Candidate overall score")
    scoring_calculation: str = Field(..., description="Explicit mathematical calculation formula and steps")
    total_questions: int = Field(..., description="Total questions assigned to session")
    attempted_questions: int = Field(default=0, description="Questions attempted by the candidate")
    answered_questions: int = Field(default=0, description="Questions with submitted answers")
    evaluated_questions: int = Field(default=0, description="Questions that have been formally evaluated")
    unevaluated_questions: int = Field(default=0, description="Questions assigned but not evaluated")
    evaluation_coverage_pct: float = Field(default=0.0, description="Percentage of assigned questions evaluated")
    strongest_competencies: List[str] = Field(default_factory=list, description="Top demonstrated competency areas")
    priority_weaknesses: List[str] = Field(default_factory=list, description="Top technical weakness areas")
    recurring_mistakes: List[str] = Field(default_factory=list, description="Patterns of repeated errors across questions")
    readiness_level: str = Field(default="Borderline / Needs Practice", description="Interview readiness level: 'Interview Ready', 'Borderline / Needs Practice', or 'Needs Substantial Preparation'")
    readiness_summary: str = Field(..., description="Evidence-grounded readiness narrative citing strengths and limitations")
    recommended_learning_priorities: List[str] = Field(default_factory=list, description="Immediate top learning priorities")


class StrengthEvidenceDetail(BaseModel):
    """Concrete evidence of a demonstrated technical strength."""
    concept: str = Field(..., description="Specific concept, algorithm, or pattern executed correctly")
    why_correct: str = Field(..., description="Technical explanation of why this was the correct approach")
    evidence_quote: Optional[str] = Field(default=None, description="Direct quote from submitted answer or test outcome")


class WeaknessEvidenceDetail(BaseModel):
    """Specific technical gap or mistake grounded in submission evidence."""
    concept: str = Field(..., description="Exact concept omitted, misunderstood, or implemented incorrectly")
    technical_impact: str = Field(..., description="Why this concept matters in real-world engineering or technical depth")
    issue_type: str = Field(default="missing_explanation", description="'incorrect_statement', 'missing_explanation', 'incomplete_solution', or 'unassessed_area'")
    evidence_quote: Optional[str] = Field(default=None, description="Direct excerpt or execution failure demonstrating the gap")


class QuestionRubricDeduction(BaseModel):
    """Criterion-level rubric mapping showing where marks were awarded and deducted."""
    criterion_name: str = Field(..., description="Name of rubric criterion (e.g., Technical Depth, Completeness)")
    expected_standard: str = Field(..., description="Expected engineering criteria or standard")
    demonstrated_evidence: str = Field(..., description="What the candidate demonstrated in their answer")
    missing_or_incorrect: str = Field(..., description="What was missing or flawed in the candidate's answer")
    score_awarded: float = Field(..., description="Score awarded for this criterion")
    max_score: float = Field(default=10.0, description="Maximum score for this criterion")
    deduction_reason: str = Field(..., description="Explicit justification for score deduction")


class TestCaseExecutionRecord(BaseModel):
    """Verifiable execution result of a single test case."""
    test_case_id: str
    input: str
    expected_output: str
    actual_output: Optional[str] = None
    passed: bool
    is_hidden: bool = False
    error: Optional[str] = None


class QuestionSolutionAnalysis(BaseModel):
    """Exemplary solution, algorithmic breakdown, and model answer."""
    expected_approach: str = Field(..., description="High-level ideal engineering approach")
    model_answer: Optional[str] = Field(default=None, description="Concise exemplary model answer for verbal or system design")
    tradeoffs_and_terminology: List[str] = Field(default_factory=list, description="Key technical terminology and engineering tradeoffs")
    why_model_is_stronger: Optional[str] = Field(default=None, description="Comparison explaining why model answer exceeds candidate's response")

    # Coding specifics
    is_coding: bool = Field(default=False)
    code_mistakes: List[str] = Field(default_factory=list, description="Logical or implementation flaws in submitted code")
    missed_edge_cases: List[str] = Field(default_factory=list, description="Boundary conditions or constraints unhandled")
    test_cases_summary: Optional[str] = Field(default=None, description="Summary of automated test results")
    test_cases: List[TestCaseExecutionRecord] = Field(default_factory=list, description="Individual test results")
    optimal_algorithm: Optional[str] = Field(default=None, description="Optimal algorithmic technique")
    time_complexity: Optional[str] = Field(default=None, description="Time complexity with justification")
    space_complexity: Optional[str] = Field(default=None, description="Space complexity with justification")
    corrected_code: Optional[str] = Field(default=None, description="Corrected reference implementation in target language")
    verification_mode: str = Field(default="static_analysis", description="'verified_execution', 'static_analysis', or 'unverified'")


class QuestionActionableImprovement(BaseModel):
    """Targeted, measurable follow-up recommendation for a specific question."""
    specific_correction: str = Field(..., description="Exact correction to apply to candidate's approach")
    concept_to_study: str = Field(..., description="Core concept or pattern to review")
    targeted_exercise: str = Field(..., description="Concrete follow-up practice problem or exercise")
    resolution_criterion: str = Field(..., description="Measurable definition of done proving the weakness is resolved")


class QuestionPerformanceSummary(BaseModel):
    """Per-question breakdown of answer status and evaluation metrics."""
    question_id: str
    question_number: int
    question_text: str
    assessed_skill: str
    difficulty: str
    is_answered: bool
    is_evaluated: bool
    overall_score: Optional[float] = None
    criterion_scores: Optional[CriterionScores] = None
    strengths: List[str] = Field(default_factory=list)
    areas_for_improvement: List[str] = Field(default_factory=list)
    candidate_answer_snippet: Optional[str] = None
    question_type: Optional[str] = Field(default="verbal", description="Type of question: 'verbal', 'coding_dsa', 'sql', 'hybrid'")
    code_snippet: Optional[str] = None
    language: Optional[str] = None
    sql_query: Optional[str] = None
    tests_passed: Optional[str] = None
    sql_status: Optional[str] = None

    # Deep-dive evidence fields
    full_candidate_answer: Optional[str] = None
    full_code: Optional[str] = None
    answer_availability: str = Field(default="available", description="'available', 'not_stored', or 'unanswered'")
    strengths_detail: List[StrengthEvidenceDetail] = Field(default_factory=list)
    weaknesses_detail: List[WeaknessEvidenceDetail] = Field(default_factory=list)
    rubric_breakdown: List[QuestionRubricDeduction] = Field(default_factory=list)
    solution_analysis: Optional[QuestionSolutionAnalysis] = None
    actionable_improvement: Optional[QuestionActionableImprovement] = None


class CompetencyAnalysisItem(BaseModel):
    """Aggregate competency assessment across all evaluated questions."""
    competency_name: str
    average_score: Optional[float] = None
    evaluated_questions_count: int = 0
    total_questions_count: int = 0
    status: str = Field(default="Needs Further Assessment", description="'Demonstrated', 'Needs Further Assessment', or 'Insufficient Evidence'")
    demonstrated_strengths: List[str] = Field(default_factory=list)
    recurring_weaknesses: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)


class PersonalizedRoadmapItem(BaseModel):
    """Prioritized learning milestone derived from candidate weaknesses."""
    priority_rank: int = Field(..., description="Sequence order (1 = highest priority foundational gap)")
    topic: str = Field(..., description="Topic or concept to master")
    why_it_matters: str = Field(..., description="Why this gap matters, directly tied to interview mistakes")
    what_to_learn_first: str = Field(..., description="Core foundational starting point")
    practice_exercise: str = Field(..., description="Concrete problem type or hands-on practice task")
    completion_criterion: str = Field(..., description="Measurable condition confirming mastery")


class ResumeSkillComparisonItem(BaseModel):
    """Correlation between resume claims and evaluated interview performance."""
    skill_name: str
    normalized_skill: Optional[str] = Field(
        default=None,
        description="Canonical normalized competency identifier",
    )
    target_role: Optional[str] = Field(
        default=None,
        description="Selected target job role",
    )
    role_importance: Optional[str] = Field(
        default=None,
        description="Role benchmark importance: 'Core', 'Recommended', or 'Advanced'",
    )
    resume_evidence_category: str = Field(
        ...,
        description="Original four-tier resume classification",
    )
    resume_evidence: Optional[str] = Field(
        default=None,
        description="Original resume evidence text or explanation",
    )
    resume_is_grounded: Optional[bool] = Field(
        default=None,
        description="True if evidence was verified directly against resume text",
    )
    resume_source_excerpt: Optional[str] = Field(
        default=None,
        description="Verbatim excerpt located in the candidate resume",
    )
    gap_priority_tier: Optional[int] = Field(
        default=None,
        description="Gap prioritization tier (1 to 5)",
    )
    selection_reason: Optional[str] = Field(
        default=None,
        description="Reason this competency was prioritized for live validation",
    )
    question_id: Optional[str] = Field(
        default=None,
        description="Associated interview question ID (e.g., 'q_1')",
    )
    question_text: Optional[str] = Field(
        default=None,
        description="Text of the interview question targeting this competency",
    )
    candidate_answer_reference: Optional[str] = Field(
        default=None,
        description="Reference identifier or label for candidate's submitted answer",
    )
    candidate_answer_excerpt: Optional[str] = Field(
        default=None,
        description="Faithful excerpt of candidate's actual answer (un-fabricated)",
    )
    evaluation_overall_score: Optional[float] = Field(
        default=None,
        description="Evaluated overall score for this question",
    )
    criterion_feedback: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Criterion scores and specific evaluative feedback",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Candidate strengths identified during evaluation",
    )
    areas_for_improvement: List[str] = Field(
        default_factory=list,
        description="Specific improvement areas identified during evaluation",
    )
    interview_status: str = Field(
        ...,
        description="'Demonstrated in Interview', 'Partially Demonstrated', 'Requires Further Validation', or 'Not Assessed'",
    )
    post_interview_status: str = Field(
        default="Not Assessed",
        description="Canonical outcome: 'Demonstrated in Interview', 'Partially Demonstrated', 'Requires Further Validation', or 'Not Assessed'",
    )
    status_rationale: Optional[str] = Field(
        default=None,
        description="Deterministic evidence-based rationale for post-interview status",
    )
    requires_further_validation: bool = Field(
        default=False,
        description="True if competency requires additional live validation or assessment",
    )
    details: str


class ResumeComparisonSection(BaseModel):
    """Comparison of resume skill claims against observed interview evidence."""
    associated_analysis_id: str
    target_role: str
    skills_comparison: List[ResumeSkillComparisonItem]
    comparison_summary: str
    demonstrated_competencies_count: int = Field(
        default=0,
        description="Number of competencies successfully demonstrated in interview",
    )
    partially_demonstrated_count: int = Field(
        default=0,
        description="Number of competencies partially demonstrated in interview",
    )
    requires_further_validation_count: int = Field(
        default=0,
        description="Number of competencies requiring further validation",
    )
    unassessed_count: int = Field(
        default=0,
        description="Number of competencies not assessed during interview",
    )


class PotentialCommunicationEventRecord(BaseModel):
    """Auditable log of flagged potential external communication incidents for human review."""
    event_id: str = Field(..., description="Unique event identifier")
    timestamp: datetime = Field(..., description="Timestamp of communication event")
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration of the incident in seconds where measurable",
    )
    event_description: str = Field(
        ...,
        description="Neutral summary of the observed telemetry or dialogue signal",
    )
    evidence_source: str = Field(
        ...,
        description="Detection sensor or pipeline source (e.g., 'multimodal_audio_visual', 'dialogue_transcription_analyzer')",
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Automated detection confidence score (0.0 - 1.0) where available",
    )
    warning_displayed: bool = Field(
        default=True,
        description="Whether a non-blocking candidate advisory warning was displayed",
    )
    review_status: str = Field(
        default="potential_concern_requiring_human_review",
        description="Human reviewer outcome status: 'potential_concern_requiring_human_review', 'verified_benign', or 'confirmed_concern'",
    )
    question_id: Optional[str] = Field(
        default=None,
        description="Associated interview question ID if observed during a question context",
    )
    incident_type: str = Field(
        default="possible_external_communication",
        description="Categorical incident type identifier",
    )


class IntegrityReportSection(BaseModel):
    """Factual, neutral summary of observable browser and media events."""
    total_events: int
    events_summary: Dict[str, int]
    events_timeline: List[IntegrityEventRecord]
    cumulative_unfocused_seconds: float = Field(
        default=0.0,
        description="Cumulative seconds spent with tab hidden, calculated from valid tab_hidden and tab_visible pairs",
    )
    incomplete_intervals_count: int = Field(
        default=0,
        description="Count of unmatched tab_hidden events lacking a corresponding tab_visible event",
    )
    events_by_question: Dict[str, int] = Field(
        default_factory=dict,
        description="Event counts aggregated per question_id, with unassociated events grouped under 'unassociated'",
    )
    human_reviews: List[HumanReviewAuditEntry] = Field(
        default_factory=list,
        description="Audit trail of contextual notes and reviews submitted by human evaluators",
    )
    candidate_explanations: List[CandidateExplanationEntry] = Field(
        default_factory=list,
        description="Audit trail of contextual explanations and dispute notes submitted by the candidate",
    )
    potential_communication_events: List[PotentialCommunicationEventRecord] = Field(
        default_factory=list,
        description="Chronological log of flagged potential external communication incidents for human review",
    )
    neutral_disclaimer: str = Field(
        default=(
            "Integrity timeline provides limited browser and hardware context. "
            "Tab switches or media interruptions are not proof of dishonesty and are strictly "
            "excluded from candidate capability scores."
        )
    )
    score_impact: str = Field(
        default="None (Excluded from candidate capability scoring)",
        description="Explicit guarantee that integrity events have zero impact on performance scores",
    )



class InterviewReportResponse(BaseModel):
    """Complete candidate interview report and decision intelligence payload."""
    report_id: str = Field(..., description="Unique UUID for this report")
    session_id: str = Field(..., description="ID of the evaluated interview session")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    role: str
    experience_level: str
    difficulty: str
    focus_areas: str

    # Quantitative coverage and scores
    total_questions: int
    answered_questions: int
    unanswered_questions: int
    evaluated_questions: int
    evaluation_coverage_pct: float
    overall_score: Optional[float] = Field(
        default=None,
        description="Arithmetic mean of overall_score across evaluated answers. None if 0 answers evaluated.",
    )
    score_status: str = Field(
        ...,
        description="'calculated' if at least 1 answer was evaluated; 'insufficient_data' otherwise",
    )
    scoring_formula_explanation: str = Field(
        ...,
        description="Explicit mathematical formula and coverage parameters used to compute the overall score",
    )
    criterion_averages: CriterionAverageScores

    # Qualitative findings
    key_strengths: List[str] = Field(default_factory=list)
    priority_improvements: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
    executive_summary: str

    # Granular breakdowns
    questions_performance: List[QuestionPerformanceSummary]
    has_resume_comparison: bool
    resume_comparison: Optional[ResumeComparisonSection] = None
    integrity_summary: IntegrityReportSection

    # Upgraded Evidence-Based Technical Assessment & Learning Roadmap
    executive_summary_details: Optional[ExecutiveSummaryDetails] = None
    competencies_analysis: List[CompetencyAnalysisItem] = Field(default_factory=list)
    learning_roadmap: List[PersonalizedRoadmapItem] = Field(default_factory=list)

    # Persistence transparency
    owner_id: Optional[str] = Field(default=None, description="Owner user ID for RBAC isolation")
    saved_to_db: bool
    db_status: str
    db_message: Optional[str] = None


class AvailableReportItem(BaseModel):
    """Summary of an interview session/report available for retrieval."""
    session_id: str = Field(..., description="Interview Session ID used for report lookup")
    report_id: Optional[str] = Field(default=None, description="Interview Report UUID if report is generated")
    resume_analysis_id: Optional[str] = Field(default=None, description="Linked Resume Analysis UUID if tied to a resume")
    role: str = Field(..., description="Target job role")
    experience_level: Optional[str] = Field(default=None, description="Candidate experience level")
    difficulty: Optional[str] = Field(default=None, description="Interview difficulty level")
    status: str = Field(default="in_progress", description="Session lifecycle status")
    report_status: str = Field(default="Report Ready", description="Human-readable report readiness status")
    overall_score: Optional[float] = Field(default=None, description="Overall evaluated score if available")
    created_at: Optional[datetime] = Field(default=None, description="Session creation timestamp")
    owner_id: Optional[str] = Field(default=None, description="Owner user ID for RBAC isolation")
    interview_mode: Optional[str] = Field(default=None, description="Interview mode ('CODING', 'VERBAL', etc.)")
    is_persisted: bool = Field(default=True, description="True if persisted in MongoDB Atlas, False if running in-memory fallback")
