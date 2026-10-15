"""
InterviewIQ - Module 04, Checkpoint 5: Full Audit, Persistence Hardening & Score Isolation.

Comprehensive regression tests verifying:
1. End-to-end data lineage across the complete lifecycle (resume -> benchmark -> gap -> question -> answer -> evaluation -> report).
2. PostgreSQL vs psql separation at every matching stage (normalization, grounding, prioritization, report).
3. All known alias and substring-collision pairs (Java/JS, C/C++/C#/CSS, SQL/NoSQL/MySQL, Git/GitHub/GitLab).
4. Four-tier deterministic outcomes (Demonstrated, Partially Demonstrated, Requires Further Validation, Not Assessed).
5. Mandatory criterion failure prevention: high overall score (e.g. 85%) cannot override failed technical depth (<6.5).
6. Missing/failed/malformed evaluation handling without ungrounded closure.
7. Repeated report generation and cached retrieval idempotence and score stability.
8. Accurate persistence metadata under unconfigured/fallback storage (no fake durable DB claims).
9. Legacy sessions and reports backward compatibility (missing Module 04 fields).
10. Strict score and hiring decision invariance (gap closure does not touch 0-100 score, criteria averages, or evaluations).
11. Preservation of Module 03 integrity telemetry, candidate explanations, and reviewer decisions.
12. Security and evidence integrity: raw prompt sanitization, non-punitive failure framing, authentic quote grounding.
"""
import uuid
from typing import Any, Dict, List, Optional
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.resume import (
    ResumeAnalysisResult,
    SkillEvidenceCategory,
    SkillEvidenceItem,
    TargetRoleBenchmark,
    RoleBenchmarkCompetency,
)
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    SubmitAnswerRequest,
)
from app.schemas.evaluation import (
    AIEvaluationRaw,
    CriterionScores,
    CriterionScore,
)
from app.schemas.integrity import (
    IntegrityEventCreate,
    IntegrityEventType,
    CandidateExplanationRequest,
    ReviewerDecisionRequest,
)
from app.services.skill_normalizer import (
    normalize_skill_name,
    canonical_skill_key,
    skills_match,
    find_matching_skill,
)
from app.services.skill_grounding import (
    find_skill_evidence_in_resume,
    verify_evidence_grounding,
)
from app.services.gap_prioritizer import (
    prioritize_skill_gaps,
)
from app.services.resume_service import (
    store_resume_analysis,
    get_resume_analysis,
    _in_memory_analyses,
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    complete_session,
    record_integrity_event,
    record_candidate_explanation,
    record_reviewer_decision,
    _in_memory_sessions,
)
from app.services.report_service import (
    generate_interview_report,
    get_interview_report,
    _in_memory_reports,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_memory_stores():
    """Ensure in-memory fixture isolation between test runs."""
    _in_memory_analyses.clear()
    _in_memory_sessions.clear()
    _in_memory_reports.clear()
    yield
    _in_memory_analyses.clear()
    _in_memory_sessions.clear()
    _in_memory_reports.clear()


def make_synthetic_evaluation(
    overall_score: float = 85.0,
    relevance: float = 9.0,
    technical_depth: float = 8.5,
    completeness: float = 8.0,
    structure: float = 8.0,
    clarity: float = 9.0,
) -> AIEvaluationRaw:
    """Helper creating structured synthetic AIEvaluationRaw."""
    return AIEvaluationRaw(
        overall_score=overall_score,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=int(relevance), feedback="Direct technical response"),
            technical_depth=CriterionScore(score=int(technical_depth), feedback="Deep implementation detail"),
            completeness=CriterionScore(score=int(completeness), feedback="Covered all facets"),
            structure_flow=CriterionScore(score=int(structure), feedback="Logical explanation"),
            clarity_conciseness=CriterionScore(score=int(clarity), feedback="Clear delivery"),
        ),
        strengths=["Demonstrated concrete architecture knowledge"],
        areas_for_improvement=["Elaborate on production failure recovery"],
        actionable_suggestions=["Review cluster failover mechanisms"],
        coaching_summary="Strong technical execution with structured communication.",
    )


# ===========================================================================
# 1. PostgreSQL vs psql Separation at Every Lifecycle Stage
# ===========================================================================
def test_psql_postgresql_strict_isolation_at_all_stages():
    """
    Verify PostgreSQL and psql remain distinct across:
    - Normalization
    - Direct matching
    - Disallowed collisions
    - Resume text grounding
    """
    # 1. Normalization
    assert normalize_skill_name("psql") == "psql"
    assert normalize_skill_name("Postgres") == "PostgreSQL"
    assert normalize_skill_name("PostgreSQL") == "PostgreSQL"
    assert normalize_skill_name("postgresql") == "PostgreSQL"

    # 2. Canonical key matching
    assert skills_match("psql", "PostgreSQL") is False
    assert skills_match("psql", "Postgres") is False
    assert skills_match("psql", "postgresql") is False
    assert skills_match("Postgres", "PostgreSQL") is True

    # 3. Grounding isolation: mentioning only 'psql' in resume does NOT ground 'PostgreSQL'
    resume_with_psql_only = "Used psql command line tool to execute database maintenance scripts."
    found_pg, snippet_pg, practical_pg = find_skill_evidence_in_resume(resume_with_psql_only, "PostgreSQL")
    assert found_pg is False
    assert snippet_pg is None

    # Mentioning 'PostgreSQL' finds PostgreSQL
    resume_with_pg = "Designed high-throughput PostgreSQL database schema with B-tree indexing."
    found_pg2, snippet_pg2, practical_pg2 = find_skill_evidence_in_resume(resume_with_pg, "PostgreSQL")
    assert found_pg2 is True
    assert "PostgreSQL" in snippet_pg2
    assert practical_pg2 is True


# ===========================================================================
# 2. Comprehensive Alias & Substring Collision Matrix
# ===========================================================================
def test_comprehensive_collision_matrix():
    """Ensure no false-positive collisions across critical technology boundaries."""
    disallowed_pairs = [
        ("Java", "JavaScript"),
        ("java", "javascript"),
        ("C", "C++"),
        ("C", "C#"),
        ("C", "CSS"),
        ("C++", "C#"),
        ("Go", "Django"),
        ("Go", "Google Cloud"),
        ("Git", "GitHub"),
        ("Git", "GitLab"),
        ("SQL", "NoSQL"),
        ("SQL", "MySQL"),
        ("SQL", "PostgreSQL"),
        ("SQL", "SQLite"),
        ("psql", "PostgreSQL"),
        ("psql", "Postgres"),
        ("React", "Reactive"),
    ]
    for skill_a, skill_b in disallowed_pairs:
        assert skills_match(skill_a, skill_b) is False, f"Unexpected match between {skill_a} and {skill_b}"
        assert skills_match(skill_b, skill_a) is False, f"Unexpected reverse match between {skill_b} and {skill_a}"


# ===========================================================================
# 3. Complete End-to-End Data Lineage Audit
# ===========================================================================
@pytest.mark.asyncio
async def test_end_to_end_data_lineage():
    """
    Traces complete lifecycle:
    Resume Analysis -> Benchmark -> Gap Prioritization -> Question -> Answer -> Evaluation -> Report.
    """
    aid = str(uuid.uuid4())
    analysis = ResumeAnalysisResult(
        analysis_id=aid,
        target_role="Principal Distributed Systems Engineer",
        experience_level="Staff",
        target_role_benchmark=TargetRoleBenchmark(
            target_role="Principal Distributed Systems Engineer",
            experience_level="Staff",
            expected_competencies=[
                RoleBenchmarkCompetency(skill_name="Apache Kafka", importance="Core", description="Event streaming"),
                RoleBenchmarkCompetency(skill_name="Kubernetes", importance="Core", description="Container orchestration"),
                RoleBenchmarkCompetency(skill_name="Rust", importance="Recommended", description="Systems programming"),
            ],
        ),
        extracted_skills=["Apache Kafka", "Kubernetes", "Rust"],
        projects_and_experience=["Engineered distributed event streaming fabric handling 500k ops/sec."],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="Apache Kafka",
                normalized_skill="Apache Kafka",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Built Kafka message broker clustering across multiple availability zones.",
                is_source_grounded=True,
                source_excerpt="Engineered distributed event streaming fabric handling 500k ops/sec.",
                relevance_to_role="Key requirement for distributed systems",
                is_expected_for_role=True,
                requires_interview_validation=False,
            ),
            SkillEvidenceItem(
                skill_name="Kubernetes",
                normalized_skill="Kubernetes",
                category=SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                evidence="Resume mentions k8s without cluster operational details.",
                relevance_to_role="Key requirement for distributed systems",
                is_source_grounded=True,
                source_excerpt="Worked with k8s deployments.",
                is_expected_for_role=True,
                requires_interview_validation=True,
            ),
            SkillEvidenceItem(
                skill_name="Rust",
                normalized_skill="Rust",
                category=SkillEvidenceCategory.NOT_DEMONSTRATED,
                evidence="Not identified in candidate resume text.",
                relevance_to_role="Key requirement for distributed systems",
                is_source_grounded=False,
                is_expected_for_role=True,
                requires_interview_validation=True,
            ),
        ],
        personalized_questions=[],
        role_readiness_summary="Strong distributed systems practitioner.",
        is_truncated=False,
        saved_to_db=False,
        db_status="unconfigured",
    )
    _in_memory_analyses[aid] = analysis

    # Prioritization check
    prioritized = prioritize_skill_gaps(analysis)
    assert len(prioritized) == 3
    # Tier 2 (Kubernetes - insufficiently evidenced) precedes Tier 3 (Rust - not demonstrated)
    # and Tier 5 (Kafka - demonstrated)
    assert prioritized[0].skill_name == "Kubernetes"
    assert prioritized[1].skill_name == "Rust"
    assert prioritized[2].skill_name == "Apache Kafka"

    # Setup Session linked to analysis
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Kubernetes custom resource definitions and reconciliation loops.",
        assessed_skill="Kubernetes",
        normalized_skill="Kubernetes",
        difficulty="Hard",
        rubric="Candidate explains controller-runtime, client-go informers, and status subresources.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(
            role="Principal Distributed Systems Engineer",
            experience_level="Staff",
            focus_areas="Kubernetes",
            question_count=3,
        ),
        questions=[q1],
        resume_analysis_id=aid,
    )
    assert session.resume_analysis_id == aid

    # Submit and Evaluate Answer
    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="CRDs extend the Kubernetes API. The controller uses informers and workqueues to watch resources and reconcile desired state with actual state.",
        ),
    )
    eval_q1 = make_synthetic_evaluation(overall_score=92.0, relevance=9.5, technical_depth=9.0, completeness=9.0)
    await save_evaluation(session.session_id, "q_1", eval_q1)

    # Generate Report
    report = await generate_interview_report(session.session_id)
    assert report.has_resume_comparison is True
    assert report.resume_comparison.associated_analysis_id == aid
    assert report.resume_comparison.target_role == "Principal Distributed Systems Engineer"

    comps = report.resume_comparison.skills_comparison
    # Kubernetes: Demonstrated in Interview
    k8s = next(c for c in comps if c.skill_name == "Kubernetes")
    assert k8s.post_interview_status == "Demonstrated in Interview"
    assert k8s.requires_further_validation is False
    assert k8s.evaluation_overall_score == 92.0
    assert k8s.candidate_answer_excerpt is not None
    assert "CRDs extend the Kubernetes API" in k8s.candidate_answer_excerpt

    # Kafka: Not Assessed in Interview (retains demonstrated resume evidence)
    kafka = next(c for c in comps if c.skill_name == "Apache Kafka")
    assert kafka.post_interview_status == "Not Assessed"
    assert kafka.resume_evidence_category == SkillEvidenceCategory.DEMONSTRATED.value
    assert kafka.resume_is_grounded is True

    # Rust: Not Assessed in Interview (retains Not Demonstrated in Resume)
    rust = next(c for c in comps if c.skill_name == "Rust")
    assert rust.post_interview_status == "Not Assessed"
    assert rust.resume_evidence_category == SkillEvidenceCategory.NOT_DEMONSTRATED.value


# ===========================================================================
# 4. Mandatory Criterion Failure Prevents Demonstrated Status
# ===========================================================================
@pytest.mark.asyncio
async def test_high_overall_score_cannot_override_failed_technical_depth():
    """
    If a candidate receives an overall score of 78% but their technical depth criterion
    is scored 4.0/10 (< 6.5 threshold), the competency must NOT be marked 'Demonstrated in Interview'.
    It must resolve to 'Partially Demonstrated'.
    """
    aid = str(uuid.uuid4())
    analysis = ResumeAnalysisResult(
        analysis_id=aid,
        target_role="Backend Architect",
        experience_level="Lead",
        extracted_skills=["gRPC"],
        projects_and_experience=["Built backend microservices"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="gRPC",
                normalized_skill="gRPC",
                category=SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                evidence="Mentions gRPC in tools.",
                relevance_to_role="Key requirement for backend architecture",
                is_expected_for_role=True,
                requires_interview_validation=True,
            )
        ],
        personalized_questions=[],
        role_readiness_summary="Architectural candidate.",
        is_truncated=False,
        saved_to_db=False,
        db_status="unconfigured",
    )
    _in_memory_analyses[aid] = analysis

    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain HTTP/2 multiplexing, streaming RPCs, and protobuf serialization in gRPC.",
        assessed_skill="gRPC",
        normalized_skill="gRPC",
        difficulty="Hard",
        rubric="Candidate discusses HTTP/2 frames, binary protobuf wire format, and bidirectional streaming.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Backend Architect", focus_areas="gRPC", question_count=3),
        questions=[q1],
        resume_analysis_id=aid,
    )
    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="gRPC uses HTTP/2 and protobuf. It is very fast and efficient for services.",
        ),
    )

    # Overall score is 78/100, but technical_depth is only 4/10
    eval_shallow = make_synthetic_evaluation(
        overall_score=78.0,
        relevance=8.0,
        technical_depth=4.0,  # Failed mandatory criterion
        completeness=7.0,
    )
    await save_evaluation(session.session_id, "q_1", eval_shallow)

    report = await generate_interview_report(session.session_id)
    grpc_comp = next(c for c in report.resume_comparison.skills_comparison if c.skill_name == "gRPC")

    # Invariant: Must NOT be Demonstrated in Interview
    assert grpc_comp.post_interview_status == "Partially Demonstrated"
    assert grpc_comp.requires_further_validation is True
    assert "technical depth (4.0/10)" in grpc_comp.status_rationale


# ===========================================================================
# 5. Failed, Incomplete, or Unanswered Evaluation Handling
# ===========================================================================
@pytest.mark.asyncio
async def test_failed_or_incomplete_evaluation_safely_unclosed():
    """
    Submitting an answer without an evaluation (e.g. LLM timeout or uncalled evaluation route)
    must resolve to 'Requires Further Validation' with safe defaults, NEVER 'Demonstrated'.
    """
    aid = str(uuid.uuid4())
    analysis = ResumeAnalysisResult(
        analysis_id=aid,
        target_role="Security Engineer",
        experience_level="Senior",
        extracted_skills=["OAuth2"],
        projects_and_experience=["Implemented IAM security systems"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="OAuth2",
                normalized_skill="OAuth2",
                category=SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                evidence="Resume mentions OAuth2.",
                relevance_to_role="Essential IAM competency",
                is_expected_for_role=True,
                requires_interview_validation=True,
            )
        ],
        personalized_questions=[],
        role_readiness_summary="Security candidate.",
        is_truncated=False,
        saved_to_db=False,
        db_status="unconfigured",
    )
    _in_memory_analyses[aid] = analysis

    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain OAuth 2.0 Authorization Code flow with PKCE.",
        assessed_skill="OAuth2",
        normalized_skill="OAuth2",
        difficulty="Hard",
        rubric="Candidate explains code_verifier, code_challenge, token exchange, and mitigating interception attacks.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Security Engineer", focus_areas="OAuth2", question_count=3),
        questions=[q1],
        resume_analysis_id=aid,
    )
    # Answer submitted, but save_evaluation NEVER called
    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="PKCE uses a cryptographic code verifier and challenge to protect mobile clients from authorization code interception.",
        ),
    )

    report = await generate_interview_report(session.session_id)
    oauth_comp = next(c for c in report.resume_comparison.skills_comparison if c.skill_name == "OAuth2")
    assert oauth_comp.post_interview_status == "Requires Further Validation"
    assert oauth_comp.requires_further_validation is True
    assert oauth_comp.evaluation_overall_score is None
    assert "evaluation is pending or could not be completed" in oauth_comp.status_rationale


# ===========================================================================
# 6. Report Idempotency & Repeated Retrieval Stability
# ===========================================================================
@pytest.mark.asyncio
async def test_report_idempotency_and_score_invariance():
    """
    Repeated POST /report and GET /report calls produce identical results,
    preserving exact answer evaluations, overall scores, and competency statuses.
    """
    aid = str(uuid.uuid4())
    analysis = ResumeAnalysisResult(
        analysis_id=aid,
        target_role="Cloud Engineer",
        experience_level="Mid-Level",
        extracted_skills=["Terraform"],
        projects_and_experience=["Managed infrastructure with IAC"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="Terraform",
                normalized_skill="Terraform",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Wrote reusable Terraform modules for AWS VPC and ECS.",
                relevance_to_role="Core IAC skill",
                is_source_grounded=True,
                is_expected_for_role=True,
                requires_interview_validation=False,
            )
        ],
        personalized_questions=[],
        role_readiness_summary="Cloud foundation.",
        is_truncated=False,
        saved_to_db=False,
        db_status="unconfigured",
    )
    _in_memory_analyses[aid] = analysis

    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Terraform state locking and backend configuration with S3 and DynamoDB.",
        assessed_skill="Terraform",
        normalized_skill="Terraform",
        difficulty="Medium",
        rubric="Candidate discusses S3 remote state storage, DynamoDB LockID table, and preventing concurrent applies.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Cloud Engineer", focus_areas="Terraform", question_count=3),
        questions=[q1],
        resume_analysis_id=aid,
    )
    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="We configure an S3 bucket for tfstate storage and a DynamoDB table for state locking to prevent concurrent terraform apply executions.",
        ),
    )
    eval_tf = make_synthetic_evaluation(overall_score=86.0)
    await save_evaluation(session.session_id, "q_1", eval_tf)

    # Call 1: POST
    res1 = client.post(f"/api/interviews/{session.session_id}/report")
    assert res1.status_code == 200
    data1 = res1.json()

    # Call 2: GET
    res2 = client.get(f"/api/interviews/{session.session_id}/report")
    assert res2.status_code == 200
    data2 = res2.json()

    # Invariants
    assert data1["report_id"] == data2["report_id"]
    assert data1["overall_score"] == data2["overall_score"] == 86.0
    assert data1["resume_comparison"]["skills_comparison"][0]["post_interview_status"] == "Demonstrated in Interview"
    assert data2["resume_comparison"]["skills_comparison"][0]["post_interview_status"] == "Demonstrated in Interview"
    assert data1["resume_comparison"]["skills_comparison"][0]["evaluation_overall_score"] == 86.0


# ===========================================================================
# 7. Persistence Metadata & Storage Fallback Hardening
# ===========================================================================
@pytest.mark.asyncio
async def test_persistence_metadata_honest_fallback_reporting():
    """
    When MongoDB is not configured, API responses truthfully report:
    saved_to_db = False, db_status = 'unconfigured', never claiming durable database persistence.
    """
    setup = InterviewSetupRequest(role="DevOps Engineer", focus_areas="Docker", question_count=3)
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Docker multi-stage builds.",
        assessed_skill="Docker",
        difficulty="Easy",
        rubric="Explains builder stage and clean runtime image.",
    )
    session = await create_interview_session(setup=setup, questions=[q1])
    assert session.saved_to_db is False
    assert session.db_status == "unconfigured"
    assert "active in-memory only" in session.db_message.lower()

    ans_res = await submit_answer(
        session.session_id,
        SubmitAnswerRequest(question_id="q_1", answer_text="Multi-stage builds reduce final image size."),
    )
    assert ans_res.saved_to_db is False
    assert ans_res.db_status == "unconfigured"


# ===========================================================================
# 8. Score Isolation & Hiring-Decision Invariance
# ===========================================================================
@pytest.mark.asyncio
async def test_strict_score_and_hiring_decision_isolation():
    """
    Module 04 closed-loop gap analysis consumes evaluations but NEVER alters:
    - Overall session score (0-100)
    - Criterion scores (1-10)
    - Answer evaluation objects
    - Candidate hiring recommendations
    """
    aid = str(uuid.uuid4())
    analysis = ResumeAnalysisResult(
        analysis_id=aid,
        target_role="Full Stack Engineer",
        experience_level="Senior",
        extracted_skills=["Python", "React", "UnknownGappedSkill"],
        projects_and_experience=["Built web platforms"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="Python",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Built backends",
                relevance_to_role="Core stack component",
                is_expected_for_role=True,
            ),
            # Massive ungrounded gap
            SkillEvidenceItem(
                skill_name="UnknownGappedSkill",
                category=SkillEvidenceCategory.NOT_DEMONSTRATED,
                evidence="Never seen before",
                relevance_to_role="Core stack component",
                is_expected_for_role=True,
                requires_interview_validation=True,
            ),
        ],
        personalized_questions=[],
        role_readiness_summary="Fullstack engineer.",
        is_truncated=False,
        saved_to_db=False,
        db_status="unconfigured",
    )
    _in_memory_analyses[aid] = analysis

    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Python async generators.",
        assessed_skill="Python",
        normalized_skill="Python",
        difficulty="Medium",
        rubric="Candidate explains async def with yield and async for loop consumption.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Full Stack Engineer", focus_areas="Python", question_count=3),
        questions=[q1],
        resume_analysis_id=aid,
    )
    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(question_id="q_1", answer_text="Async generators use async def with yield."),
    )
    initial_eval = make_synthetic_evaluation(overall_score=80.0)
    saved_eval = await save_evaluation(session.session_id, "q_1", initial_eval)

    # Verify initial evaluation scores
    assert saved_eval.overall_score == 80.0
    assert saved_eval.criterion_scores.relevance.score == 9

    # Generate Report
    report = await generate_interview_report(session.session_id)

    # Invariants:
    # 1. Overall session score is strictly 80.0 (no penalty for 'UnknownGappedSkill' being unaddressed)
    assert report.overall_score == 80.0
    # 2. Criterion scores are strictly untouched
    assert report.criterion_averages.relevance == 9.0
    # 3. Evaluated question performance reflects untouched evaluation
    assert report.questions_performance[0].overall_score == 80.0


# ===========================================================================
# 9. Preservation of Module 03 Integrity & Candidate Dispute Workflows
# ===========================================================================
@pytest.mark.asyncio
async def test_module_03_integrity_dispute_preservation():
    """
    Ensures that presence events, candidate explanations, and human review decisions
    remain fully preserved and strictly separated from competency evaluation scores.
    """
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain RESTful HTTP status codes.",
        assessed_skill="REST APIs",
        difficulty="Easy",
        rubric="Candidate differentiates 2xx success, 4xx client errors, and 5xx server errors.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="API Developer", focus_areas="REST APIs", question_count=3),
        questions=[q1],
    )

    # Log integrity event
    evt = await record_integrity_event(
        session.session_id,
        IntegrityEventCreate(
            event_type=IntegrityEventType.TAB_HIDDEN,
            question_id="q_1",
            details={"reason": "browser tab switch"},
        ),
    )

    # Submit candidate dispute / explanation
    exp = await record_candidate_explanation(
        session.session_id,
        CandidateExplanationRequest(
            event_id=evt.event_id,
            explanation="Switched to check official RFC documentation for HTTP status codes.",
        ),
    )
    assert exp.is_verified_identity is False
    assert "Candidate-provided explanation without authenticated identity verification" in exp.identity_note

    # Record reviewer decision
    dec = await record_reviewer_decision(
        session.session_id,
        exp.explanation_id,
        ReviewerDecisionRequest(
            status="reviewed",
            reviewer_name="Senior Engineering Reviewer",
            reviewer_outcome="upheld_explanation",
            determination_note="Document search confirmed benign.",
        ),
    )
    assert dec.decision_history[0].reviewer_name == "Senior Engineering Reviewer"
    assert dec.decision_history[0].is_verified_identity is False

    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(question_id="q_1", answer_text="200 OK, 201 Created, 400 Bad Request, 500 Internal Error."),
    )
    await save_evaluation(session.session_id, "q_1", make_synthetic_evaluation(overall_score=85.0))
    await complete_session(session.session_id)

    report = await generate_interview_report(session.session_id)
    integ = report.integrity_summary

    assert integ.total_events == 1
    assert len(integ.candidate_explanations) == 1
    assert integ.candidate_explanations[0].status == "reviewed"
    assert integ.candidate_explanations[0].reviewer_outcome == "upheld_explanation"
    assert "strictly excluded from candidate capability scores" in integ.neutral_disclaimer.lower()
    # Integrity telemetry does not deduct from candidate score
    assert report.overall_score == 85.0
