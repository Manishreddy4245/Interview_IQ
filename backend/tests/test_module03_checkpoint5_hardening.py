from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.schemas.integrity import (
    IntegrityEventType,
    IntegrityEventCreate,
    ReviewStatus,
)
from app.schemas.evaluation import AnswerEvaluationResponse, CriterionScores, CriterionScore
from app.schemas.interview import SubmitAnswerRequest
from app.services.session_service import (
    submit_answer,
    save_evaluation,
    record_integrity_event,
    complete_session,
    record_candidate_explanation,
    record_reviewer_decision,
    get_candidate_explanations,
    _in_memory_sessions,
)
from app.services.report_service import (
    compute_integrity_analytics,
    generate_interview_report,
    get_interview_report,
)


def create_test_session(client: TestClient) -> str:
    """Helper to create an active test session for hardening tests."""
    valid_ai_json = """{
      "questions": [
        {
          "id": "q_1",
          "question_number": 1,
          "text": "How do you achieve fault tolerance in distributed consensus protocols?",
          "assessed_skill": "Distributed Systems",
          "difficulty": "Hard",
          "rubric": "Evaluates Raft/Paxos quorums, leader election, and log replication."
        },
        {
          "id": "q_2",
          "question_number": 2,
          "text": "Explain memory compaction algorithms in garbage collection.",
          "assessed_skill": "Memory Management",
          "difficulty": "Hard",
          "rubric": "Evaluates mark-sweep-compact, copying collectors, and fragmentation."
        },
        {
          "id": "q_3",
          "question_number": 3,
          "text": "What are zero-copy I/O techniques in modern operating systems?",
          "assessed_skill": "Operating Systems",
          "difficulty": "Hard",
          "rubric": "Evaluates sendfile, splice, and direct memory access."
        }
      ]
    }"""
    mock_choice = MagicMock()
    mock_choice.message.content = valid_ai_json
    mock_completion = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_testkey"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):
        res = client.post(
            "/api/interviews/setup",
            json={
                "role": "Principal Systems Architect",
                "focus_areas": "Distributed Systems, OS",
                "question_count": 3,
            },
        )
        assert res.status_code == 201
        return res.json()["session_id"]


def test_reviewer_decision_submission_and_retrieval(client: TestClient):
    """Test valid reviewer decision submission on a candidate explanation and retrieval."""
    session_id = create_test_session(client)

    # 1. Submit candidate explanation
    exp_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Candidate reports cursor moved to secondary screen to view documentation."},
    )
    assert exp_res.status_code == 201
    exp_id = exp_res.json()["explanation_id"]
    assert exp_res.json()["status"] == "pending_review"

    # 2. Record reviewer decision
    dec_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={
            "status": "reviewed",
            "reviewer_name": "Audit Lead Dr. Jane",
            "reviewer_outcome": "Context reviewed; dual-screen documentation check verified benign.",
        },
    )
    assert dec_res.status_code == 200
    updated_exp = dec_res.json()
    assert updated_exp["explanation_id"] == exp_id
    assert updated_exp["status"] == "reviewed"
    assert updated_exp["reviewer_outcome"] == "Context reviewed; dual-screen documentation check verified benign."
    assert len(updated_exp["decision_history"]) == 1

    decision = updated_exp["decision_history"][0]
    assert decision["status"] == "reviewed"
    assert decision["reviewer_name"] == "Audit Lead Dr. Jane"
    assert "Context reviewed" in decision["reviewer_outcome"]
    assert decision["is_verified_identity"] is False
    assert "unauthenticated" in decision["identity_note"].lower()
    assert "decision_id" in decision
    assert "created_at" in decision

    # 3. Retrieve via GET endpoint and confirm persistence
    get_res = client.get(f"/api/interviews/{session_id}/integrity-explanations")
    assert get_res.status_code == 200
    explanations = get_res.json()
    assert len(explanations) == 1
    assert explanations[0]["status"] == "reviewed"
    assert len(explanations[0]["decision_history"]) == 1


def test_reviewer_decision_invalid_status_and_note_validation(client: TestClient):
    """Test rejection of invalid statuses and malformed reviewer notes."""
    session_id = create_test_session(client)

    exp_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Candidate explanation regarding accidental browser shortcut press."},
    )
    exp_id = exp_res.json()["explanation_id"]

    # Invalid status value (HTTP 422)
    inv_status = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={"status": "disqualified", "reviewer_outcome": "Disqualified candidate"},
    )
    assert inv_status.status_code == 422

    # Blank/whitespace reviewer outcome note (HTTP 422)
    blank_note = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={"status": "reviewed", "reviewer_outcome": "    "},
    )
    assert blank_note.status_code == 422

    # Too short reviewer outcome note (< 5 non-whitespace chars) (HTTP 422)
    short_note = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={"status": "reviewed", "reviewer_outcome": "done"},
    )
    assert short_note.status_code == 422

    # Oversized reviewer outcome note (> 2000 chars) (HTTP 422)
    oversized = "A" * 2001
    over_note = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={"status": "reviewed", "reviewer_outcome": oversized},
    )
    assert over_note.status_code == 422

    # Optional/omitted reviewer outcome is valid
    valid_no_outcome = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={"status": "reviewed"},
    )
    assert valid_no_outcome.status_code == 200
    assert valid_no_outcome.json()["status"] == "reviewed"
    assert valid_no_outcome.json()["reviewer_outcome"] is None


def test_reviewer_decision_append_only_history(client: TestClient):
    """Verify that multiple reviewer decisions append to decision_history without overwriting."""
    session_id = create_test_session(client)

    exp_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Candidate explanation regarding audio glitch."},
    )
    exp_id = exp_res.json()["explanation_id"]

    # First decision
    d1 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={
            "status": "reviewed",
            "reviewer_name": "Reviewer A",
            "reviewer_outcome": "Preliminary review: waiting for system logs.",
        },
    )
    assert d1.status_code == 200
    d1_id = d1.json()["decision_history"][0]["decision_id"]

    # Second decision (supplementary determination)
    d2 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={
            "status": "reviewed",
            "reviewer_name": "Senior Reviewer B",
            "reviewer_outcome": "Final determination: system logs confirm hardware audio disconnection.",
        },
    )
    assert d2.status_code == 200
    history = d2.json()["decision_history"]
    assert len(history) == 2
    assert history[0]["decision_id"] == d1_id
    assert history[0]["reviewer_name"] == "Reviewer A"
    assert history[1]["reviewer_name"] == "Senior Reviewer B"
    assert d2.json()["reviewer_outcome"] == "Final determination: system logs confirm hardware audio disconnection."


def test_candidate_explanation_immutability(client: TestClient):
    """Verify that candidate explanation text cannot be altered by reviewer decisions."""
    session_id = create_test_session(client)
    original_text = "Original candidate statement: I sneezed and knocked the mouse off the desk."

    exp_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": original_text},
    )
    exp_id = exp_res.json()["explanation_id"]

    # Record decision
    client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={
            "status": "reviewed",
            "reviewer_name": "Reviewer C",
            "reviewer_outcome": "Noted accidental motion event.",
        },
    )

    get_res = client.get(f"/api/interviews/{session_id}/integrity-explanations")
    saved_exp = get_res.json()[0]
    assert saved_exp["explanation"] == original_text


def test_reviewer_decision_nonexistent_ids(client: TestClient):
    """Test HTTP 404 for non-existent session_id or explanation_id."""
    session_id = create_test_session(client)

    # Unknown session
    r1 = client.post(
        "/api/interviews/unknown-session-id/integrity-explanations/unknown-exp-id/decision",
        json={"status": "reviewed"},
    )
    assert r1.status_code == 404

    # Known session, unknown explanation
    r2 = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/unknown-exp-id/decision",
        json={"status": "reviewed"},
    )
    assert r2.status_code == 404
    assert "unknown-exp-id" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_completed_session_permits_decisions(client: TestClient):
    """
    Verify completed-session policy:
    Candidate raw telemetry is rejected, but reviewer decisions are permitted on completed sessions.
    """
    session_id = create_test_session(client)

    exp_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Pre-completion context note regarding battery low pop-up."},
    )
    exp_id = exp_res.json()["explanation_id"]

    # Complete session
    await complete_session(session_id)

    # Telemetry is blocked
    tel_res = client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "tab_hidden"},
    )
    assert tel_res.status_code == 400

    # Decision on explanation is allowed
    dec_res = client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp_id}/decision",
        json={"status": "reviewed", "reviewer_outcome": "Post-completion review completed."},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "reviewed"


def test_repeated_report_generation_does_not_duplicate_entries(client: TestClient):
    """Verify repeated report fetches do not duplicate events, reviews, or explanations."""
    session_id = create_test_session(client)

    # Add telemetry event
    client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "tab_hidden", "question_id": "q_1"},
    )
    # Add human review
    client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={"reviewer_name": "Auditor", "review_notes": "First audit note for session."},
    )
    # Add candidate explanation
    exp = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Explanation for tab switch event."},
    ).json()
    # Add reviewer decision
    client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp['explanation_id']}/decision",
        json={"status": "reviewed", "reviewer_outcome": "Outcome recorded."},
    )

    # Fetch report multiple times
    with patch("app.core.config.settings.GROQ_API_KEY", None):
        rep1 = client.get(f"/api/interviews/{session_id}/report").json()
        rep2 = client.get(f"/api/interviews/{session_id}/report").json()

    integ1 = rep1["integrity_summary"]
    integ2 = rep2["integrity_summary"]

    assert len(integ1["events_timeline"]) == 1
    assert len(integ2["events_timeline"]) == 1
    assert len(integ1["human_reviews"]) == 1
    assert len(integ2["human_reviews"]) == 1
    assert len(integ1["candidate_explanations"]) == 1
    assert len(integ2["candidate_explanations"]) == 1
    assert len(integ1["candidate_explanations"][0]["decision_history"]) == 1
    assert len(integ2["candidate_explanations"][0]["decision_history"]) == 1


def test_legacy_records_missing_optional_fields_compatibility(client: TestClient):
    """
    Test backwards compatibility with legacy records missing optional fields:
    - events missing question_id or details
    - explanations missing decision_history or reviewer_outcome
    - missing human_reviews
    """
    raw_events = [
        {"event_id": "e_old_1", "event_type": "tab_hidden", "timestamp": "2026-10-11T12:00:00Z"},
        {"event_id": "e_old_2", "event_type": "tab_visible", "timestamp": "2026-10-11T12:00:10Z"},
    ]
    # compute_integrity_analytics must handle legacy events safely
    duration, incomplete, by_q = compute_integrity_analytics(raw_events)
    assert duration == 10.0
    assert incomplete == 0
    assert by_q == {"unassociated": 2}

    # Simulate legacy session without human_reviews or candidate_explanations
    legacy_session_id = "legacy-session-uuid"
    _in_memory_sessions[legacy_session_id] = {
        "session_id": legacy_session_id,
        "role": "Legacy Systems Engineer",
        "experience_level": "Senior",
        "difficulty": "Hard",
        "focus_areas": "Systems",
        "questions": [],
        "answers": {},
        "integrity_events": raw_events,
        "status": "completed",
        "created_at": "2026-10-11T12:00:00Z",
        "updated_at": "2026-10-11T12:00:00Z",
    }

    with patch("app.core.config.settings.GROQ_API_KEY", None):
        rep = client.get(f"/api/interviews/{legacy_session_id}/report").json()

    assert rep["integrity_summary"]["human_reviews"] == []
    assert rep["integrity_summary"]["candidate_explanations"] == []
    assert rep["integrity_summary"]["total_events"] == 2
    assert rep["integrity_summary"]["cumulative_unfocused_seconds"] == 10.0


@pytest.mark.asyncio
async def test_strict_score_isolation_end_to_end_decision_flow(client: TestClient):
    """
    Verify complete score isolation across the full telemetry and decision lifecycle:
    Events, reviews, candidate explanations, and reviewer decisions do NOT modify:
    - overall_score
    - criterion_averages
    - question evaluations
    - hiring coaching recommendations
    """
    session_id = create_test_session(client)

    # Submit and evaluate an answer
    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(
            question_id="q_1",
            answer_text="Raft uses leader election with randomized timeouts, log replication, and safety invariants.",
        ),
    )
    eval_resp = AnswerEvaluationResponse(
        session_id=session_id,
        question_id="q_1",
        overall_score=92.0,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=10, feedback="Exact Raft protocol breakdown."),
            technical_depth=CriterionScore(score=9, feedback="Strong quorum and commit index discussion."),
            completeness=CriterionScore(score=9, feedback="Covers split-vote and heartbeat semantics."),
            structure_flow=CriterionScore(score=9, feedback="High clarity."),
            clarity_conciseness=CriterionScore(score=9, feedback="Crisp communication."),
            star_structure=CriterionScore(score=9, feedback="Methodical."),
        ),
        strengths=["Deep Raft architecture knowledge"],
        areas_for_improvement=["Mention Joint Consensus for membership changes"],
        actionable_suggestions=["Review Raft section 6"],
        coaching_summary="Exemplary systems architecture response.",
        evaluated_at=datetime.now(timezone.utc),
        saved_to_db=False,
        db_status="unconfigured",
    )
    await save_evaluation(session_id, "q_1", eval_resp)

    # Initial report
    with patch("app.core.config.settings.GROQ_API_KEY", None):
        r_init = client.get(f"/api/interviews/{session_id}/report").json()

    init_score = r_init["overall_score"]
    init_crit = r_init["criterion_averages"]
    init_recs = r_init["recommended_next_steps"]

    assert init_score == 92.0

    # 1. Log telemetry event
    client.post(
        f"/api/interviews/{session_id}/integrity-events",
        json={"event_type": "tab_hidden", "question_id": "q_1"},
    )
    # 2. Add human review
    client.post(
        f"/api/interviews/{session_id}/integrity-review",
        json={"reviewer_name": "Reviewer 1", "review_notes": "Observed momentary focus shift."},
    )
    # 3. Submit candidate explanation
    exp = client.post(
        f"/api/interviews/{session_id}/integrity-explanations",
        json={"explanation": "Candidate reports external meeting alert notification."},
    ).json()
    # 4. Submit reviewer decision
    client.post(
        f"/api/interviews/{session_id}/integrity-explanations/{exp['explanation_id']}/decision",
        json={"status": "reviewed", "reviewer_outcome": "Meeting alert confirmed benign."},
    )

    # Post-lifecycle report
    with patch("app.core.config.settings.GROQ_API_KEY", None):
        r_final = client.get(f"/api/interviews/{session_id}/report").json()

    # Scores, criteria, and recommendations MUST remain 100% identical
    assert r_final["overall_score"] == init_score
    assert r_final["criterion_averages"] == init_crit
    assert r_final["recommended_next_steps"] == init_recs
    assert r_final["evaluated_questions"] == 1
    assert r_final["score_status"] == "calculated"
