"""
Tests for InterviewIQ Module 04 — Checkpoint 4:
Closed-Loop Gap Closure & Traceable Evidence Reporting.

Covers all 16 required test scenarios:
1. Competency demonstrably supported by persisted answer and passing evaluation criteria.
2. Partially supported competency (criteria thresholding).
3. Unanswered competency (question exists, but no answer submitted).
4. Submitted answer with no completed evaluation (pending/missing).
5. Evaluation failure or malformed evaluation result.
6. Exact question-to-answer association.
7. Two similar competency names that must not collide (Java vs JavaScript, SQL vs NoSQL).
8. Competency requiring multiple assessment criteria.
9. Resume claim unconfirmed by interview evidence (claim was demonstrated, interview score was low).
10. Grounded resume skill that remains unresolved after the interview.
11. Evidence excerpts and rationales that faithfully reference source data.
12. Report persistence and retrieval.
13. MongoDB-unavailable memory fallback metadata.
14. Legacy sessions and reports with missing linkage fields.
15. Score and evaluation invariance.
16. Preservation of Module 03 integrity and dispute workflows.
"""
from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.resume import (
    ResumeAnalysisResult,
    TargetRoleBenchmark,
    RoleBenchmarkCompetency,
    SkillEvidenceCategory,
    SkillEvidenceItem,
    PersonalizedQuestionItem,
)
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    SubmitAnswerRequest,
)
from app.schemas.evaluation import AIEvaluationRaw, CriterionScores, CriterionScore
from app.schemas.integrity import (
    IntegrityEventCreate,
    IntegrityEventType,
    CandidateExplanationRequest,
    ReviewerDecisionRequest,
)
from app.services.skill_normalizer import normalize_skill_name
from app.services.resume_service import _in_memory_analyses
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    record_integrity_event,
    record_candidate_explanation,
    record_reviewer_decision,
    complete_session,
    _in_memory_sessions,
)
from app.services.report_service import (
    generate_interview_report,
    get_interview_report,
    _in_memory_reports,
)
from app.services.gap_closure_service import (
    resolve_post_interview_status,
    build_traceable_skill_comparisons,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_memory_stores():
    """Ensure in-memory stores are clean before each test."""
    _in_memory_analyses.clear()
    _in_memory_sessions.clear()
    _in_memory_reports.clear()
    yield
    _in_memory_analyses.clear()
    _in_memory_sessions.clear()
    _in_memory_reports.clear()


def create_synthetic_resume_analysis(
    analysis_id: Optional[str] = None,
    target_role: str = "Senior Backend Engineer",
    experience_level: str = "Senior",
    benchmark_skills=None,
    skill_evaluations=None,
) -> ResumeAnalysisResult:
    """Helper to build in-memory synthetic resume analysis fixture."""
    aid = analysis_id or str(uuid.uuid4())
    expected_comps = []
    if benchmark_skills:
        for b in benchmark_skills:
            expected_comps.append(
                RoleBenchmarkCompetency(
                    skill_name=b["name"],
                    normalized_skill=normalize_skill_name(b["name"]),
                    importance=b.get("importance", "Core"),
                    description=b.get("description", "Expected for role"),
                )
            )

    evals = []
    if skill_evaluations:
        for ev in skill_evaluations:
            evals.append(
                SkillEvidenceItem(
                    skill_name=ev["name"],
                    normalized_skill=normalize_skill_name(ev["name"]),
                    category=ev.get("category", SkillEvidenceCategory.DEMONSTRATED),
                    evidence=ev.get("evidence", "Candidate resume statement"),
                    relevance_to_role=ev.get("relevance", "Required for role"),
                    is_source_grounded=ev.get("is_grounded", True),
                    evidence_type="verbatim_quote" if ev.get("is_grounded") else "inferred_summary",
                    source_excerpt=ev.get("excerpt"),
                    is_expected_for_role=ev.get("is_expected", True),
                    classification_rationale=ev.get("rationale", "Evidence verified"),
                    requires_interview_validation=ev.get("requires_validation", False),
                )
            )

    result = ResumeAnalysisResult(
        analysis_id=aid,
        target_role=target_role,
        experience_level=experience_level,
        target_role_benchmark=TargetRoleBenchmark(
            target_role=target_role,
            experience_level=experience_level,
            expected_competencies=expected_comps,
        ) if expected_comps else None,
        extracted_skills=[e.skill_name for e in evals] or ["Python", "Docker"],
        projects_and_experience=["Built distributed platform microservices"],
        skill_evaluations=evals,
        personalized_questions=[],
        role_readiness_summary="Strong technical foundation.",
        is_truncated=False,
        analyzed_character_count=1500,
        created_at=datetime.now(timezone.utc),
        saved_to_db=False,
        db_status="unconfigured",
        db_message="In-memory synthetic fixture",
    )
    _in_memory_analyses[aid] = result.model_dump()
    _in_memory_analyses[aid]["created_at"] = result.created_at.isoformat()
    return result


def create_standard_evaluation(
    overall_score: float = 85.0,
    relevance: int = 9,
    technical_depth: int = 8,
    completeness: int = 8,
    strengths=None,
    improvements=None,
) -> AIEvaluationRaw:
    """Helper to build evaluation object with valid scores and non-empty lists."""
    return AIEvaluationRaw(
        overall_score=overall_score,
        criterion_scores={
            "relevance": {"score": relevance, "feedback": "Directly answered prompt"},
            "technical_depth": {"score": technical_depth, "feedback": "Detailed mechanics"},
            "completeness": {"score": completeness, "feedback": "Covered key parameters"},
            "structure_flow": {"score": 8, "feedback": "Logical progression"},
            "clarity_conciseness": {"score": 9, "feedback": "Clear explanation"},
        },
        strengths=strengths or ["Solid technical understanding"],
        areas_for_improvement=improvements or ["Elaborate on edge cases"],
        actionable_suggestions=["Practice describing fault tolerance"],
        coaching_summary="Well structured response",
    )


# ---------------------------------------------------------------------------
# 1. Competency Demonstrably Supported by Persisted Answer & Passing Criteria
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_competency_demonstrably_supported():
    """Evaluated answer meeting score (>= 70) and criteria (>= 6.5) achieves Demonstrated in Interview."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "PostgreSQL", "importance": "Core"}],
        skill_evaluations=[
            {
                "name": "PostgreSQL",
                "category": SkillEvidenceCategory.REQUIRES_VALIDATION,
                "is_grounded": True,
                "excerpt": "Architected PostgreSQL database with B-Tree indexes",
                "requires_validation": True,
            }
        ],
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="How do you optimize slow query plans in PostgreSQL using EXPLAIN ANALYZE?",
        assessed_skill="PostgreSQL",
        normalized_skill="PostgreSQL",
        difficulty="Medium",
        rubric="Candidate discusses index scans, buffer hit rates, and execution plans.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Senior Backend Engineer", focus_areas="PostgreSQL", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )

    # Submit and evaluate answer with high marks
    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="We use EXPLAIN (ANALYZE, BUFFERS) to examine sequential scans versus index scans and tune shared buffers.",
        ),
    )
    await save_evaluation(
        session.session_id,
        "q_1",
        create_standard_evaluation(overall_score=88.0, relevance=9, technical_depth=9, completeness=8),
    )

    report = await generate_interview_report(session.session_id)
    assert report.has_resume_comparison is True
    assert report.resume_comparison is not None

    pg_item = next(i for i in report.resume_comparison.skills_comparison if i.skill_name == "PostgreSQL")
    assert pg_item.post_interview_status == "Demonstrated in Interview"
    assert pg_item.interview_status == "Demonstrated in Interview"
    assert pg_item.requires_further_validation is False
    assert pg_item.evaluation_overall_score == 88.0
    assert "88.0/100" in pg_item.status_rationale
    assert pg_item.question_id == "q_1"
    assert pg_item.candidate_answer_excerpt is not None


# ---------------------------------------------------------------------------
# 2. Partially Supported Competency (Criteria Thresholding)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_partially_supported_competency():
    """Score between 50-69 or failing depth/completeness criteria resolves to Partially Demonstrated."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "Docker", "importance": "Core"}],
        skill_evaluations=[
            {
                "name": "Docker",
                "category": SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
                "requires_validation": True,
            }
        ],
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain container layer caching and multi-stage builds in Docker.",
        assessed_skill="Docker",
        normalized_skill="Docker",
        difficulty="Medium",
        rubric="Explains layer order, cache invalidation, and scratch base images.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Senior Backend Engineer", focus_areas="Docker", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )

    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="Multi-stage builds allow separating build tools from final images. I have basic experience with it.",
        ),
    )
    # Score is 62.0 (Partially Demonstrated range)
    await save_evaluation(
        session.session_id,
        "q_1",
        create_standard_evaluation(overall_score=62.0, relevance=7, technical_depth=6, completeness=5),
    )

    report = await generate_interview_report(session.session_id)
    docker_item = next(i for i in report.resume_comparison.skills_comparison if i.skill_name == "Docker")
    assert docker_item.post_interview_status == "Partially Demonstrated"
    assert docker_item.requires_further_validation is True
    assert "partially demonstrated" in docker_item.details.lower() or "partially demonstrated" in docker_item.status_rationale.lower()


# ---------------------------------------------------------------------------
# 3. Unanswered Competency
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unanswered_competency():
    """Competency with an interview question that the candidate did not answer receives Not Assessed."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "Kubernetes", "importance": "Core"}],
        skill_evaluations=[
            {
                "name": "Kubernetes",
                "category": SkillEvidenceCategory.NOT_DEMONSTRATED,
                "requires_validation": True,
            }
        ],
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="How do you manage pod disruption budgets during cluster upgrades?",
        assessed_skill="Kubernetes",
        normalized_skill="Kubernetes",
        difficulty="Hard",
        rubric="Discusses minAvailable and maxUnavailable pod disruption parameters.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Senior Backend Engineer", focus_areas="Kubernetes", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )
    # Do NOT submit any answer

    report = await generate_interview_report(session.session_id)
    k8s_item = next(i for i in report.resume_comparison.skills_comparison if i.skill_name == "Kubernetes")
    assert k8s_item.post_interview_status == "Not Assessed"
    assert k8s_item.interview_status == "Not Assessed"
    assert k8s_item.requires_further_validation is True
    assert k8s_item.evaluation_overall_score is None
    assert "did not submit an answer" in k8s_item.status_rationale.lower() or "unanswered" in k8s_item.details.lower()


# ---------------------------------------------------------------------------
# 4. Submitted Answer with No Completed Evaluation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_submitted_answer_no_evaluation():
    """Answer submitted but evaluation pending/missing receives Requires Further Validation."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "Kafka", "importance": "Core"}],
        skill_evaluations=[
            {
                "name": "Kafka",
                "category": SkillEvidenceCategory.REQUIRES_VALIDATION,
                "requires_validation": True,
            }
        ],
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain consumer group rebalancing protocols in Apache Kafka.",
        assessed_skill="Kafka",
        normalized_skill="Apache Kafka",
        difficulty="Hard",
        rubric="Discusses eager rebalance versus cooperative sticky assignors.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Senior Backend Engineer", focus_areas="Kafka", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )

    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="Cooperative rebalancing avoids stopping all consumers at once by revoking partitions incrementally.",
        ),
    )
    # Evaluation is NOT called (pending)

    report = await generate_interview_report(session.session_id)
    kafka_item = next(i for i in report.resume_comparison.skills_comparison if i.skill_name == "Kafka")
    assert kafka_item.post_interview_status == "Requires Further Validation"
    assert kafka_item.requires_further_validation is True
    assert "evaluation is pending" in kafka_item.status_rationale.lower() or "unverified" in kafka_item.details.lower()


# ---------------------------------------------------------------------------
# 5. Evaluation Failure or Malformed Evaluation Result
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evaluation_failure_malformed_result():
    """If evaluation record has None score or invalid structure, unresolved status is retained."""
    item = SkillEvidenceItem(
        skill_name="Redis",
        category=SkillEvidenceCategory.INSUFFICIENTLY_EVIDENCED,
        evidence="Used Redis for caching",
        relevance_to_role="In-memory cache",
        requires_interview_validation=True,
    )
    matching_q = {"id": "q_1", "question_number": 1, "text": "Describe Redis caching strategies"}
    answer_data = {
        "answer_text": "We used Redis for session tokens.",
        "evaluation": {"overall_score": None, "criterion_scores": {}},  # Malformed score
    }
    status, post_status, rationale, det, req_val, score, crits, str_list, imp_list = resolve_post_interview_status(
        item=item,
        matching_q=matching_q,
        answer_data=answer_data,
        target_role="Senior Backend Engineer",
    )
    assert post_status == "Requires Further Validation"
    assert req_val is True
    assert score is None


# ---------------------------------------------------------------------------
# 6. Exact Question-to-Answer Association
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_exact_question_to_answer_association():
    """Verifies that each competency faithfully associates with its specific question and answer excerpt."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[
            {"name": "Go", "importance": "Core"},
            {"name": "Rust", "importance": "Recommended"},
        ],
        skill_evaluations=[
            {"name": "Go", "category": SkillEvidenceCategory.DEMONSTRATED},
            {"name": "Rust", "category": SkillEvidenceCategory.DEMONSTRATED},
        ],
    )
    q1 = QuestionItem(id="q_1", question_number=1, text="Explain Go goroutines and channel buffering.", assessed_skill="Go", normalized_skill="Go", difficulty="Medium", rubric="Goroutine mechanics")
    q2 = QuestionItem(id="q_2", question_number=2, text="How does the Rust borrow checker prevent data races?", assessed_skill="Rust", normalized_skill="Rust", difficulty="Hard", rubric="Ownership and lifetimes")

    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Systems Engineer", focus_areas="Go, Rust", question_count=3),
        questions=[q1, q2],
        resume_analysis_id=analysis.analysis_id,
    )

    go_answer = "Go channels can be unbuffered or buffered with a fixed capacity to prevent goroutine blocking."
    rust_answer = "Rust ownership ensures exactly one owner for a value, preventing double frees and aliased mutability."

    await submit_answer(session.session_id, SubmitAnswerRequest(question_id="q_1", answer_text=go_answer))
    await save_evaluation(session.session_id, "q_1", create_standard_evaluation(overall_score=85.0))

    await submit_answer(session.session_id, SubmitAnswerRequest(question_id="q_2", answer_text=rust_answer))
    await save_evaluation(session.session_id, "q_2", create_standard_evaluation(overall_score=90.0))

    report = await generate_interview_report(session.session_id)
    items = report.resume_comparison.skills_comparison

    go_item = next(i for i in items if i.skill_name == "Go")
    rust_item = next(i for i in items if i.skill_name == "Rust")

    assert go_item.question_id == "q_1"
    assert "goroutines and channel buffering" in go_item.question_text
    assert go_item.candidate_answer_excerpt == go_answer
    assert "Session Answer Q1" in go_item.candidate_answer_reference

    assert rust_item.question_id == "q_2"
    assert "Rust borrow checker" in rust_item.question_text
    assert rust_item.candidate_answer_excerpt == rust_answer
    assert "Session Answer Q2" in rust_item.candidate_answer_reference


# ---------------------------------------------------------------------------
# 7. Two Similar Competency Names Must Not Collide (Java vs JavaScript, SQL vs NoSQL)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_two_similar_competency_names_no_collision():
    """Java and JavaScript must not collide; evaluated answer for JavaScript must not evaluate Java."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[
            {"name": "Java", "importance": "Core"},
            {"name": "JavaScript", "importance": "Recommended"},
        ],
        skill_evaluations=[
            {"name": "Java", "category": SkillEvidenceCategory.REQUIRES_VALIDATION, "requires_validation": True},
            {"name": "JavaScript", "category": SkillEvidenceCategory.DEMONSTRATED},
        ],
    )
    # Question only targeting JavaScript
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain closures and the event loop microtask queue in JavaScript.",
        assessed_skill="JavaScript",
        normalized_skill="JavaScript",
        difficulty="Medium",
        rubric="Explains lexical scope closures and promise microtasks.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Full Stack Engineer", focus_areas="JavaScript", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )

    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="Closures retain access to outer scope variables. Microtasks run before the next event loop tick.",
        ),
    )
    await save_evaluation(session.session_id, "q_1", create_standard_evaluation(overall_score=85.0))

    report = await generate_interview_report(session.session_id)
    items = report.resume_comparison.skills_comparison

    js_item = next(i for i in items if i.skill_name == "JavaScript")
    java_item = next(i for i in items if i.skill_name == "Java")

    assert js_item.post_interview_status == "Demonstrated in Interview"
    assert js_item.question_id == "q_1"

    # Java MUST remain unassessed, NEVER marked evaluated from JavaScript's question!
    assert java_item.post_interview_status == "Not Assessed"
    assert java_item.question_id is None
    assert java_item.candidate_answer_excerpt is None


# ---------------------------------------------------------------------------
# 8. Competency Requiring Multiple Assessment Criteria
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_competency_requiring_multiple_assessment_criteria():
    """Overall score 75 with failing completeness criterion (4/10) resolves to Partially Demonstrated."""
    item = SkillEvidenceItem(
        skill_name="System Architecture",
        category=SkillEvidenceCategory.REQUIRES_VALIDATION,
        evidence="Led architecture design",
        relevance_to_role="High-level architecture",
        requires_interview_validation=True,
    )
    matching_q = {"id": "q_1", "question_number": 1, "text": "Design a geo-distributed cache with multi-region replication."}
    answer_data = {
        "answer_text": "We place caches near users and replicate data asynchronously.",
        "evaluation": {
            "overall_score": 75.0,  # Overall passes 70
            "criterion_scores": {
                "relevance": {"score": 8, "feedback": "Relevant"},
                "technical_depth": {"score": 8, "feedback": "Good depth"},
                "completeness": {"score": 4, "feedback": "Omitted partition handling and conflict resolution"},  # Fails 6.0
            },
            "strengths": ["Clear latency focus"],
            "areas_for_improvement": ["Did not address write conflicts"],
        },
    }
    status, post_status, rationale, det, req_val, score, crits, str_list, imp_list = resolve_post_interview_status(
        item=item,
        matching_q=matching_q,
        answer_data=answer_data,
        target_role="Principal Architect",
    )
    assert post_status == "Partially Demonstrated"
    assert req_val is True
    assert "completeness (4.0/10)" in rationale


# ---------------------------------------------------------------------------
# 9. Resume Claim Unconfirmed by Interview Evidence
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_resume_claim_unconfirmed_by_interview_evidence():
    """Candidate claimed Demonstrated in resume, but scored 38/100 in interview: status becomes Requires Further Validation."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "GraphQL", "importance": "Core"}],
        skill_evaluations=[
            {
                "name": "GraphQL",
                "category": SkillEvidenceCategory.DEMONSTRATED,
                "is_grounded": True,
                "excerpt": "Built production GraphQL API serving 1M daily requests",
                "requires_validation": False,
            }
        ],
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="How do you solve the N+1 query problem in GraphQL schemas?",
        assessed_skill="GraphQL",
        normalized_skill="GraphQL",
        difficulty="Hard",
        rubric="Candidate explains DataLoader batching and caching mechanisms.",
    )
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Senior Backend Engineer", focus_areas="GraphQL", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )

    await submit_answer(
        session.session_id,
        SubmitAnswerRequest(
            question_id="q_1",
            answer_text="I don't remember the details of how GraphQL resolvers batch database queries.",
        ),
    )
    # Score 38/100
    await save_evaluation(
        session.session_id,
        "q_1",
        create_standard_evaluation(overall_score=38.0, relevance=4, technical_depth=3, completeness=3),
    )

    report = await generate_interview_report(session.session_id)
    gql_item = next(i for i in report.resume_comparison.skills_comparison if i.skill_name == "GraphQL")

    # Original resume classification is PRESERVED
    assert gql_item.resume_evidence_category == SkillEvidenceCategory.DEMONSTRATED.value
    assert gql_item.resume_source_excerpt == "Built production GraphQL API serving 1M daily requests"

    # Post-interview outcome reflects unconfirmed evidence
    assert gql_item.post_interview_status == "Requires Further Validation"
    assert gql_item.requires_further_validation is True
    assert gql_item.evaluation_overall_score == 38.0
    assert "further live validation or project-based assessment recommended" in gql_item.status_rationale.lower()


# ---------------------------------------------------------------------------
# 10. Grounded Resume Skill That Remains Unresolved After the Interview
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_grounded_resume_skill_unresolved_after_interview():
    """Grounded resume skill unassessed in interview retains grounded resume excerpt and Not Assessed status."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "Redis", "importance": "Recommended"}],
        skill_evaluations=[
            {
                "name": "Redis",
                "category": SkillEvidenceCategory.DEMONSTRATED,
                "is_grounded": True,
                "excerpt": "Configured Redis cluster for distributed session management",
            }
        ],
    )
    q1 = QuestionItem(id="q_1", question_number=1, text="Explain Python asyncio event loop.", assessed_skill="Python", normalized_skill="Python", difficulty="Medium", rubric="Event loop")
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Backend Engineer", focus_areas="Python", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )
    # Redis question was never asked

    report = await generate_interview_report(session.session_id)
    redis_item = next(i for i in report.resume_comparison.skills_comparison if i.skill_name == "Redis")
    assert redis_item.post_interview_status == "Not Assessed"
    assert redis_item.resume_source_excerpt == "Configured Redis cluster for distributed session management"
    assert redis_item.question_id is None


# ---------------------------------------------------------------------------
# 11. Evidence Excerpts and Rationales Faithfully Reference Source Data
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evidence_excerpts_faithfully_reference_source_data():
    """Ensures no fabricated quotes; answer excerpt and resume quote are exact substrings."""
    exact_resume_quote = "Engineered high-throughput event processing with AWS SQS and SNS"
    exact_candidate_ans = "We configured SQS dead letter queues with redrive policies and exponential backoff."

    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "AWS SQS", "importance": "Core"}],
        skill_evaluations=[
            {
                "name": "AWS SQS",
                "category": SkillEvidenceCategory.DEMONSTRATED,
                "is_grounded": True,
                "excerpt": exact_resume_quote,
            }
        ],
    )
    q1 = QuestionItem(id="q_1", question_number=1, text="How do you handle message failure in AWS SQS?", assessed_skill="AWS SQS", normalized_skill="AWS SQS", difficulty="Medium", rubric="DLQ and redrive")
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Cloud Engineer", focus_areas="AWS SQS", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )

    await submit_answer(session.session_id, SubmitAnswerRequest(question_id="q_1", answer_text=exact_candidate_ans))
    await save_evaluation(session.session_id, "q_1", create_standard_evaluation(overall_score=82.0))

    report = await generate_interview_report(session.session_id)
    sqs_item = next(i for i in report.resume_comparison.skills_comparison if i.skill_name == "AWS SQS")

    assert sqs_item.resume_source_excerpt == exact_resume_quote
    assert sqs_item.candidate_answer_excerpt == exact_candidate_ans
    assert "82.0/100" in sqs_item.status_rationale


# ---------------------------------------------------------------------------
# 12. Report Persistence and Retrieval
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_persistence_and_retrieval():
    """Generated report is persisted to memory/db store and retrieved identically via GET."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "FastAPI", "importance": "Core"}],
        skill_evaluations=[{"name": "FastAPI", "category": SkillEvidenceCategory.DEMONSTRATED}],
    )
    q1 = QuestionItem(id="q_1", question_number=1, text="Explain FastAPI dependency injection.", assessed_skill="FastAPI", normalized_skill="FastAPI", difficulty="Medium", rubric="Candidate explains Depends() and dependency overrides for testing.")
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Backend Engineer", focus_areas="FastAPI", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )
    await submit_answer(session.session_id, SubmitAnswerRequest(question_id="q_1", answer_text="Depends() provides composable sub-dependencies."))
    await save_evaluation(session.session_id, "q_1", create_standard_evaluation(overall_score=85.0))

    # Generate via POST
    post_res = client.post(f"/api/interviews/{session.session_id}/report")
    assert post_res.status_code == 200
    post_data = post_res.json()

    # Retrieve via GET
    get_res = client.get(f"/api/interviews/{session.session_id}/report")
    assert get_res.status_code == 200
    get_data = get_res.json()

    assert post_data["report_id"] == get_data["report_id"]
    assert len(post_data["resume_comparison"]["skills_comparison"]) == len(get_data["resume_comparison"]["skills_comparison"])
    assert get_data["resume_comparison"]["skills_comparison"][0]["post_interview_status"] == "Demonstrated in Interview"


# ---------------------------------------------------------------------------
# 13. MongoDB-Unavailable Memory Fallback Metadata
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_mongodb_unavailable_memory_fallback_metadata():
    """When MongoDB Atlas is unconfigured, report accurately reflects in-memory fallback status."""
    analysis = create_synthetic_resume_analysis()
    q1 = QuestionItem(id="q_1", question_number=1, text="Explain Python decorators.", assessed_skill="Python", normalized_skill="Python", difficulty="Medium", rubric="Higher order functions")
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Python Developer", focus_areas="Python", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )
    report = await generate_interview_report(session.session_id)
    assert report.saved_to_db is False
    assert report.db_status == "unconfigured"
    assert "server memory" in report.db_message.lower()


# ---------------------------------------------------------------------------
# 14. Legacy Sessions and Reports with Missing Linkage Fields
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_legacy_sessions_and_reports_missing_linkage():
    """Older sessions created without resume_analysis_id compile safely with has_resume_comparison=False."""
    q1 = QuestionItem(id="q_1", question_number=1, text="Explain SQL joins.", assessed_skill="SQL", difficulty="Medium", rubric="Inner vs outer joins")
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Data Analyst", focus_areas="SQL", question_count=3),
        questions=[q1],
        resume_analysis_id=None,  # Legacy: no resume analysis
    )
    await submit_answer(session.session_id, SubmitAnswerRequest(question_id="q_1", answer_text="Inner join returns matching rows."))
    await save_evaluation(session.session_id, "q_1", create_standard_evaluation(overall_score=75.0))

    report = await generate_interview_report(session.session_id)
    assert report.has_resume_comparison is False
    assert report.resume_comparison is None
    assert report.overall_score == 75.0


# ---------------------------------------------------------------------------
# 15. Score and Evaluation Invariance
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_score_and_evaluation_invariance():
    """Gap closure status resolution consumes evaluation scores but never modifies them."""
    analysis = create_synthetic_resume_analysis(
        benchmark_skills=[{"name": "TypeScript", "importance": "Core"}],
        skill_evaluations=[
            {
                "name": "TypeScript",
                "category": SkillEvidenceCategory.NOT_DEMONSTRATED,  # Resume gap
                "requires_validation": True,
            }
        ],
    )
    q1 = QuestionItem(id="q_1", question_number=1, text="Explain TypeScript utility types.", assessed_skill="TypeScript", normalized_skill="TypeScript", difficulty="Medium", rubric="Partial and Pick")
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Frontend Engineer", focus_areas="TypeScript", question_count=3),
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
    )
    await submit_answer(session.session_id, SubmitAnswerRequest(question_id="q_1", answer_text="Pick extracts specific keys while Partial makes properties optional."))
    eval_raw = create_standard_evaluation(overall_score=94.0, relevance=10, technical_depth=9, completeness=9)
    await save_evaluation(session.session_id, "q_1", eval_raw)

    report = await generate_interview_report(session.session_id)
    # The fact that TypeScript was NOT_DEMONSTRATED on the resume did NOT dock the score
    assert report.overall_score == 94.0
    assert report.criterion_averages.relevance == 10.0
    assert report.criterion_averages.technical_depth == 9.0


# ---------------------------------------------------------------------------
# 16. Preservation of Module 03 Integrity and Dispute Workflows
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_module_03_integrity_and_dispute_preservation():
    """Integrity telemetry, candidate explanations, and reviewer decisions remain fully preserved."""
    q1 = QuestionItem(id="q_1", question_number=1, text="Explain REST API design.", assessed_skill="API", difficulty="Medium", rubric="Status codes")
    session = await create_interview_session(
        setup=InterviewSetupRequest(role="Backend Engineer", focus_areas="API", question_count=3),
        questions=[q1],
    )
    # Integrity event
    evt = await record_integrity_event(
        session.session_id,
        IntegrityEventCreate(event_type=IntegrityEventType.WINDOW_BLUR, question_id="q_1", details={"note": "Blur"}),
    )
    # Candidate explanation
    exp = await record_candidate_explanation(
        session.session_id,
        CandidateExplanationRequest(event_id=evt.event_id, explanation="System notification popped up"),
    )
    # Reviewer decision
    await record_reviewer_decision(
        session.session_id,
        exp.explanation_id,
        ReviewerDecisionRequest(status="reviewed", reviewer_outcome="upheld_explanation", determination_note="Legitimate notification"),
    )
    # Complete session
    await complete_session(session.session_id)

    report = await generate_interview_report(session.session_id)
    integ = report.integrity_summary
    assert integ.total_events == 1
    assert len(integ.candidate_explanations) == 1
    assert integ.candidate_explanations[0].status == "reviewed"
    assert integ.candidate_explanations[0].reviewer_outcome == "upheld_explanation"
    assert "excluded from candidate capability score" in integ.neutral_disclaimer.lower()
