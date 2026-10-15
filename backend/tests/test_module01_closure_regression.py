import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    SubmitAnswerRequest,
    CompetencyStatus,
)
from app.schemas.evaluation import (
    CriterionScores,
    CriterionScore,
    AIEvaluationRaw,
)
from app.schemas.resume import (
    AIRawSkillGapOutput,
    SkillEvidenceCategory,
    SkillEvidenceItem,
    PersonalizedQuestionItem,
)
from app.services.session_service import (
    create_interview_session,
    submit_answer,
    save_evaluation,
    append_session_question,
    get_session,
    _in_memory_sessions,
)
from app.services.adaptation_service import (
    determine_adaptive_difficulty,
    compute_session_competency_state,
    generate_next_adaptive_question,
)
from app.services.report_service import generate_interview_report
from app.services.resume_service import store_resume_analysis

client = TestClient(app)


def test_score_scale_schema_validation():
    """1. Overall interview score is strictly 1-100; Criteria are strictly 1-10."""
    # Invalid overall_score > 100
    with pytest.raises(ValidationError):
        AIEvaluationRaw(
            overall_score=105,
            criterion_scores=CriterionScores(
                relevance=CriterionScore(score=8, feedback="Good"),
                technical_depth=CriterionScore(score=8, feedback="Good"),
                completeness=CriterionScore(score=8, feedback="Good"),
                structure_flow=CriterionScore(score=8, feedback="Good"),
                clarity_conciseness=CriterionScore(score=8, feedback="Good"),
            ),
            strengths=["Strong"],
            areas_for_improvement=["Improve"],
            actionable_suggestions=["Action"],
            coaching_summary="Summary text here.",
        )

    # Invalid overall_score < 1
    with pytest.raises(ValidationError):
        AIEvaluationRaw(
            overall_score=0,
            criterion_scores=CriterionScores(
                relevance=CriterionScore(score=8, feedback="Good"),
                technical_depth=CriterionScore(score=8, feedback="Good"),
                completeness=CriterionScore(score=8, feedback="Good"),
                structure_flow=CriterionScore(score=8, feedback="Good"),
                clarity_conciseness=CriterionScore(score=8, feedback="Good"),
            ),
            strengths=["Strong"],
            areas_for_improvement=["Improve"],
            actionable_suggestions=["Action"],
            coaching_summary="Summary text here.",
        )

    # Invalid criterion score > 10
    with pytest.raises(ValidationError):
        CriterionScore(score=11, feedback="Invalid score > 10")

    # Invalid criterion score < 1
    with pytest.raises(ValidationError):
        CriterionScore(score=0, feedback="Invalid score < 1")


@pytest.mark.asyncio
async def test_score_25_out_of_100_not_treated_as_demonstrated():
    """2. A score of 25/100 must NOT be treated as demonstrated merely because 25 > 6."""
    # 1. Setup resume analysis
    raw_ai = AIRawSkillGapOutput(
        extracted_skills=["Distributed Systems"],
        projects_and_experience=["Built backend cluster"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="Distributed Systems",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Resume evidence",
                relevance_to_role="High",
            )
        ],
        personalized_questions=[],
        role_readiness_summary="Summary",
    )
    analysis = await store_resume_analysis(
        target_role="Distributed Systems Engineer",
        experience_level="Senior",
        ai_output=raw_ai,
    )

    # 2. Setup interview session linked to resume
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Raft consensus.",
        assessed_skill="Distributed Systems",
        difficulty="Medium",
        rubric="Explains quorums and leader election in distributed systems.",
    )
    setup = InterviewSetupRequest(
        role="Distributed Systems Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Distributed Systems",
        question_count=3,
    )
    session = await create_interview_session(
        setup=setup,
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
        target_question_count=1,
    )
    session_id = session.session_id

    # 3. Submit and evaluate with score 25/100
    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(question_id="q_1", answer_text="Raft uses voting."),
    )
    eval_25 = AIEvaluationRaw(
        overall_score=25,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=3, feedback="Superficial"),
            technical_depth=CriterionScore(score=2, feedback="Missed leader election"),
            completeness=CriterionScore(score=2, feedback="Incomplete"),
            structure_flow=CriterionScore(score=3, feedback="Fragmented"),
            clarity_conciseness=CriterionScore(score=4, feedback="Brief"),
        ),
        strengths=["Mentioned voting"],
        areas_for_improvement=["Explain terms and AppendEntries RPC"],
        actionable_suggestions=["Study Raft paper"],
        coaching_summary="Candidate requires deeper preparation on consensus.",
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=eval_25)

    # 4. Generate report
    report = await generate_interview_report(session_id=session_id)
    assert report.has_resume_comparison is True
    assert report.resume_comparison is not None
    skills_comp = report.resume_comparison.skills_comparison
    assert len(skills_comp) == 1

    item = skills_comp[0]
    # Critical assertion: must NOT be "Demonstrated in Interview"
    assert item.interview_status == "Requires Further Validation"
    assert "25.0/100" in item.details
    assert not item.details.endswith("/10")
    assert "/10;" not in item.details
    assert "/10." not in item.details


@pytest.mark.asyncio
async def test_score_75_out_of_100_adaptation_and_report_logic():
    """3. A score of 75/100 escalates difficulty and marks competency demonstrated."""
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain Kubernetes control plane components.",
        assessed_skill="Kubernetes",
        difficulty="Medium",
        rubric="Explains api-server, etcd, controller-manager, scheduler.",
    )
    setup = InterviewSetupRequest(
        role="DevOps Engineer",
        experience_level="Senior",
        difficulty="Medium",
        focus_areas="Kubernetes",
        question_count=3,
    )
    session = await create_interview_session(
        setup=setup,
        questions=[q1],
        target_question_count=2,
    )
    session_id = session.session_id

    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(question_id="q_1", answer_text="Detailed K8s answer."),
    )
    eval_75 = AIEvaluationRaw(
        overall_score=75,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=8, feedback="Very relevant"),
            technical_depth=CriterionScore(score=8, feedback="Solid architecture knowledge"),
            completeness=CriterionScore(score=7, feedback="Covers key components"),
            structure_flow=CriterionScore(score=8, feedback="Logical progression"),
            clarity_conciseness=CriterionScore(score=8, feedback="Crisp phrasing"),
        ),
        strengths=["Clear breakdown of etcd and api-server"],
        areas_for_improvement=["Mention lease locks for controller-manager"],
        actionable_suggestions=["Discuss HA topology"],
        coaching_summary="Strong grasp of control plane.",
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=eval_75)

    # Check adaptation logic
    stored_session = await get_session(session_id)
    adapted_diff = determine_adaptive_difficulty(stored_session)
    assert adapted_diff == "Hard", "Score of 75/100 on Medium should escalate to Hard"

    comp_state = compute_session_competency_state(stored_session)
    k8s_skill = comp_state.skills.get("Kubernetes")
    assert k8s_skill is not None
    assert k8s_skill.status == CompetencyStatus.DEMONSTRATED
    assert k8s_skill.average_score == 75.0


@pytest.mark.asyncio
async def test_missing_scores_remain_none_not_zero():
    """4. Unanswered / unevaluated questions must have overall_score=None, not 0.0."""
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Question text here for candidate evaluation.",
        assessed_skill="Python",
        difficulty="Medium",
        rubric="Comprehensive rubric for evaluating Python knowledge.",
    )
    setup = InterviewSetupRequest(
        role="Backend Engineer",
        experience_level="Junior",
        difficulty="Medium",
        focus_areas="Python",
        question_count=3,
    )
    session = await create_interview_session(
        setup=setup,
        questions=[q1],
        target_question_count=1,
    )
    session_id = session.session_id

    report = await generate_interview_report(session_id=session_id)
    assert report.overall_score is None, "Overall score must be None when no evaluations exist"
    assert report.score_status == "insufficient_data"
    assert report.evaluated_questions == 0
    assert report.answered_questions == 0
    assert report.total_questions == 1
    assert report.questions_performance[0].overall_score is None
    assert report.questions_performance[0].is_answered is False
    assert report.questions_performance[0].is_evaluated is False


@pytest.mark.asyncio
async def test_idempotent_append_and_target_count_enforcement():
    """5. Appending duplicate questions is ignored; appending beyond target count raises HTTP 400."""
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Question 1 text here for candidate evaluation.",
        assessed_skill="Python",
        difficulty="Medium",
        rubric="Rubric for evaluating Python question 1.",
    )
    setup = InterviewSetupRequest(
        role="Software Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python",
        question_count=3,
    )
    session = await create_interview_session(
        setup=setup,
        questions=[q1],
        target_question_count=2,
    )
    session_id = session.session_id

    # Append Q1 again (duplicate) -> should not duplicate
    updated_session = await append_session_question(session_id, q1)
    assert len(updated_session["questions"]) == 1

    # Append Q2 -> succeeds (count becomes 2)
    q2 = QuestionItem(
        id="q_2",
        question_number=2,
        text="Question 2 text here for candidate evaluation.",
        assessed_skill="FastAPI",
        difficulty="Medium",
        rubric="Rubric for evaluating FastAPI question 2.",
    )
    updated_session = await append_session_question(session_id, q2)
    assert len(updated_session["questions"]) == 2

    # Append Q3 -> target count is 2, so this must raise HTTP 400
    q3 = QuestionItem(
        id="q_3",
        question_number=3,
        text="Question 3 text here for candidate evaluation.",
        assessed_skill="AsyncIO",
        difficulty="Hard",
        rubric="Rubric for evaluating AsyncIO question 3.",
    )
    with pytest.raises(HTTPException) as exc_info:
        await append_session_question(session_id, q3)
    assert exc_info.value.status_code == 400
    assert "target question count" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_concurrent_next_question_requests_serialize():
    """6. Concurrent next-question requests do not overflow target_question_count."""
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Question 1 text here for candidate evaluation.",
        assessed_skill="Python",
        difficulty="Medium",
        rubric="Rubric for evaluating Python question 1.",
    )
    setup = InterviewSetupRequest(
        role="Software Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Python, FastAPI",
        question_count=3,
    )
    session = await create_interview_session(
        setup=setup,
        questions=[q1],
        target_question_count=2,
    )
    session_id = session.session_id

    mock_groq_content = json.dumps({
        "id": "q_2",
        "question_number": 2,
        "text": "Explain FastAPI dependency injection.",
        "assessed_skill": "FastAPI",
        "difficulty": "Medium",
        "rubric": "Discusses Depends and yield dependencies in FastAPI.",
        "selection_rationale": "Assessing second competency.",
    })

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = mock_groq_content
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        # Launch two concurrent requests for the 2nd question slot
        results = await asyncio.gather(
            generate_next_adaptive_question(session_id),
            generate_next_adaptive_question(session_id),
            return_exceptions=True,
        )

        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]

        # One request should succeed, the other should be rejected with HTTP 400 target count reached
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], HTTPException)
        assert failures[0].status_code == 400

        # Session questions length must be exactly 2 (never 3)
        final_session = await get_session(session_id)
        assert len(final_session["questions"]) == 2


@pytest.mark.asyncio
async def test_existing_reports_display_correct_denominators_and_scale():
    """7. Existing reports remain readable with correct denominators and scale interpretation."""
    # Setup resume analysis with two skills
    raw_ai = AIRawSkillGapOutput(
        extracted_skills=["System Design", "Legacy Skill"],
        projects_and_experience=["Built backend cluster"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="System Design",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Resume evidence",
                relevance_to_role="High",
            ),
            SkillEvidenceItem(
                skill_name="Legacy Skill",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Resume evidence",
                relevance_to_role="High",
            ),
        ],
        personalized_questions=[],
        role_readiness_summary="Summary",
    )
    analysis = await store_resume_analysis(
        target_role="Principal Architect",
        experience_level="Senior",
        ai_output=raw_ai,
    )

    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain large-scale cache invalidation architectures.",
        assessed_skill="System Design",
        difficulty="Hard",
        rubric="Mentions event-driven cache invalidation, thundering herd, and lease locks.",
    )
    setup = InterviewSetupRequest(
        role="Principal Architect",
        experience_level="Senior",
        difficulty="Hard",
        focus_areas="System Design, Legacy Skill",
        question_count=3,
    )
    session = await create_interview_session(
        setup=setup,
        questions=[q1],
        resume_analysis_id=analysis.analysis_id,
        target_question_count=1,
    )
    session_id = session.session_id

    # Score of 88/100 (Canonical 0-100 scale)
    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(question_id="q_1", answer_text="Use write-through with Redis leases."),
    )
    eval_88 = AIEvaluationRaw(
        overall_score=88,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Directly addresses caching"),
            technical_depth=CriterionScore(score=9, feedback="Covers leases and stamps"),
            completeness=CriterionScore(score=8, feedback="Covers stampede mitigations"),
            structure_flow=CriterionScore(score=9, feedback="Structured clearly"),
            clarity_conciseness=CriterionScore(score=9, feedback="Concise phrasing"),
        ),
        strengths=["Deep understanding of cache stampede mitigations"],
        areas_for_improvement=["Could mention probabilistic early expiration (XFetch)"],
        actionable_suggestions=["Reference XFetch algorithm"],
        coaching_summary="Exemplary systems design answer.",
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=eval_88)

    report = await generate_interview_report(session_id=session_id)
    assert report.overall_score == 88.0
    assert report.score_status == "calculated"
    assert report.questions_performance[0].overall_score == 88.0

    # Resume comparison verification
    assert report.has_resume_comparison is True
    skills_comp = report.resume_comparison.skills_comparison
    sys_item = next(i for i in skills_comp if i.skill_name == "System Design")
    assert sys_item.interview_status == "Demonstrated in Interview"
    assert "88.0/100" in sys_item.details
    assert not sys_item.details.endswith("/10")
    assert "/10." not in sys_item.details
    assert "/10;" not in sys_item.details

    # Untested skill
    legacy_item = next(i for i in skills_comp if i.skill_name == "Legacy Skill")
    assert legacy_item.interview_status == "Claimed in Resume (Not Evaluated in Session)"
