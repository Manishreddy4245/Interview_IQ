from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.schemas.integrity import IntegrityEventType, IntegrityEventCreate
from app.schemas.evaluation import AnswerEvaluationResponse, CriterionScores, CriterionScore
from app.schemas.interview import SubmitAnswerRequest
from app.services.report_service import compute_integrity_analytics
from app.services.session_service import submit_answer, save_evaluation, record_integrity_event


def create_mocked_session(client: TestClient) -> str:
    """Helper to create an active test session for integration testing."""
    valid_ai_json = """{
      "questions": [
        {
          "id": "q_1",
          "question_number": 1,
          "text": "How do you ensure data integrity in distributed databases?",
          "assessed_skill": "Distributed Systems",
          "difficulty": "Medium",
          "rubric": "Evaluates two-phase commit, consensus algorithms, and idempotency."
        },
        {
          "id": "q_2",
          "question_number": 2,
          "text": "Explain the difference between optimistic and pessimistic concurrency control.",
          "assessed_skill": "Concurrency",
          "difficulty": "Hard",
          "rubric": "Evaluates lock mechanisms, rollback cost, and conflict detection."
        },
        {
          "id": "q_3",
          "question_number": 3,
          "text": "Describe partitioning strategies for high throughput event streams.",
          "assessed_skill": "Event Streaming",
          "difficulty": "Medium",
          "rubric": "Evaluates partition keys, rebalancing, and consumer groups."
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
                "role": "Distributed Systems Engineer",
                "focus_areas": "Distributed Systems, Concurrency",
                "question_count": 3,
            },
        )
        assert res.status_code == 201
        return res.json()["session_id"]


# ==============================================================================
# Unit Tests for Presence Analytics & Interval Pairing
# ==============================================================================

def test_valid_hidden_visible_pair_exact_five_seconds():
    """Verify that a valid hidden -> visible pair computes exactly 5.0 seconds unfocused duration."""
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=5)

    events = [
        {"event_type": "tab_hidden", "timestamp": t0.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_visible", "timestamp": t1.isoformat(), "question_id": "q_1"},
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    assert duration == 5.0
    assert incomplete_count == 0
    assert per_q == {"q_1": 2}


def test_duplicate_hidden_events_no_double_counting():
    """
    Verify that duplicate consecutive tab_hidden events while already hidden
    do not restart the interval or double-count duration.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=2)  # Duplicate hidden
    t2 = t0 + timedelta(seconds=8)  # Visible

    events = [
        {"event_type": "tab_hidden", "timestamp": t0.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_hidden", "timestamp": t1.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_visible", "timestamp": t2.isoformat(), "question_id": "q_1"},
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    # The tab became hidden at t0 and returned visible at t2 (8 seconds total)
    assert duration == 8.0
    assert incomplete_count == 0
    assert per_q == {"q_1": 3}


def test_duplicate_visible_events_safe_handling():
    """
    Verify that duplicate or orphan tab_visible events when tab is already visible
    are safely ignored and do not alter duration or cause errors.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=5)
    t2 = t0 + timedelta(seconds=7)  # Duplicate visible

    events = [
        {"event_type": "tab_hidden", "timestamp": t0.isoformat()},
        {"event_type": "tab_visible", "timestamp": t1.isoformat()},
        {"event_type": "tab_visible", "timestamp": t2.isoformat()},
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    assert duration == 5.0
    assert incomplete_count == 0
    assert per_q == {"unassociated": 3}


def test_unmatched_hidden_event_marked_incomplete():
    """
    Verify that an unmatched tab_hidden event is explicitly flagged in incomplete_intervals_count
    and NEVER silently converted into an artificial completed duration.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=4)
    t2 = t0 + timedelta(seconds=10)  # Unmatched hidden

    events = [
        {"event_type": "tab_hidden", "timestamp": t0.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_visible", "timestamp": t1.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_hidden", "timestamp": t2.isoformat(), "question_id": "q_2"},
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    # Only the first matched interval (4s) contributes to duration
    assert duration == 4.0
    assert incomplete_count == 1
    assert per_q == {"q_1": 2, "q_2": 1}


def test_out_of_order_and_invalid_timestamps():
    """
    Verify that events arriving out-of-order are sorted chronologically,
    and invalid or unparseable timestamps are safely skipped without throwing errors.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=6)

    events = [
        # Out-of-order: visible appears before hidden in list
        {"event_type": "tab_visible", "timestamp": t1.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_hidden", "timestamp": t0.isoformat(), "question_id": "q_1"},
        # Corrupted / invalid timestamp
        {"event_type": "tab_hidden", "timestamp": "corrupted-date-format", "question_id": "q_1"},
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    assert duration == 6.0
    assert incomplete_count == 0
    assert per_q == {"q_1": 3}


def test_clock_skew_and_non_positive_intervals():
    """
    Verify that intervals with visible <= hidden (due to clock skew or identical timestamps)
    are discarded, preventing negative durations from corrupting totals.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 10, tzinfo=timezone.utc)
    # Exact same timestamp (zero duration)
    events_zero = [
        {"event_type": "tab_hidden", "timestamp": t0.isoformat()},
        {"event_type": "tab_visible", "timestamp": t0.isoformat()},
    ]
    dur_zero, inc_zero, _ = compute_integrity_analytics(events_zero)
    assert dur_zero == 0.0
    assert inc_zero == 0


def test_overlapping_and_repeated_intervals_no_inflation():
    """
    Verify that overlapping intervals are merged before summing to prevent inflated totals.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=10)
    t2 = t0 + timedelta(seconds=15)
    t3 = t0 + timedelta(seconds=20)

    # Simulated overlapping interval inputs
    events = [
        {"event_type": "tab_hidden", "timestamp": t0.isoformat()},
        {"event_type": "tab_visible", "timestamp": t1.isoformat()},
        {"event_type": "tab_hidden", "timestamp": t2.isoformat()},
        {"event_type": "tab_visible", "timestamp": t3.isoformat()},
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    # Two disjoint intervals: 10s + 5s = 15s
    assert duration == 15.0
    assert incomplete_count == 0


def test_window_blur_and_focus_distinct_from_tab_visibility():
    """
    Verify that window_blur and window_focus are tracked distinctly and NOT
    added to cumulative_unfocused_seconds to prevent double-counting.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=2)
    t2 = t0 + timedelta(seconds=7)
    t3 = t0 + timedelta(seconds=10)

    events = [
        {"event_type": "window_blur", "timestamp": t0.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_hidden", "timestamp": t1.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_visible", "timestamp": t2.isoformat(), "question_id": "q_1"},
        {"event_type": "window_focus", "timestamp": t3.isoformat(), "question_id": "q_1"},
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    # Only tab_hidden (t1) -> tab_visible (t2) is counted in unfocused duration (5.0s)
    assert duration == 5.0
    assert incomplete_count == 0
    # All 4 events are counted in per-question summary
    assert per_q == {"q_1": 4}


def test_session_with_no_integrity_events_safe_defaults():
    """Verify safe defaults when a session has zero integrity events."""
    duration, incomplete_count, per_q = compute_integrity_analytics([])
    assert duration == 0.0
    assert incomplete_count == 0
    assert per_q == {}


def test_per_question_event_counts_and_unassociated():
    """
    Verify that events without a question_id are categorized as 'unassociated',
    while question-linked events are correctly grouped by question_id.
    """
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)

    events = [
        {"event_type": "tab_hidden", "timestamp": t0.isoformat(), "question_id": "q_1"},
        {"event_type": "tab_visible", "timestamp": (t0 + timedelta(seconds=1)).isoformat(), "question_id": "q_1"},
        {"event_type": "window_blur", "timestamp": (t0 + timedelta(seconds=2)).isoformat(), "question_id": "q_2"},
        {"event_type": "camera_mic_granted", "timestamp": (t0 + timedelta(seconds=3)).isoformat()},  # None
        {"event_type": "practice_started", "timestamp": (t0 + timedelta(seconds=4)).isoformat(), "question_id": ""},  # empty string
    ]

    duration, incomplete_count, per_q = compute_integrity_analytics(events)
    assert per_q == {"q_1": 2, "q_2": 1, "unassociated": 2}


# ==============================================================================
# Integration Test: End-to-End Report Generation & Strict Score Isolation
# ==============================================================================

@pytest.mark.asyncio
async def test_strict_score_isolation_end_to_end_report(client: TestClient):
    """
    Verify that recording extensive integrity telemetry (tab switches, window blurs, incomplete intervals)
    does NOT alter overall score, criterion scores, or competency evaluations.
    """
    session_id = create_mocked_session(client)

    # 1. Submit and evaluate answers with known scores
    eval_q1 = AnswerEvaluationResponse(
        session_id=session_id,
        question_id="q_1",
        overall_score=80.0,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=8, feedback="Relevant answer with strong accuracy."),
            technical_depth=CriterionScore(score=8, feedback="Good depth regarding distributed consensus."),
            completeness=CriterionScore(score=8, feedback="Complete coverage of two-phase commit edge cases."),
            structure_flow=CriterionScore(score=8, feedback="Clear structure with logical step-by-step layout."),
            clarity_conciseness=CriterionScore(score=8, feedback="Concise formulation without unnecessary filler."),
        ),
        strengths=["Clear explanation"],
        areas_for_improvement=["Could mention Paxos"],
        actionable_suggestions=["Review Paxos"],
        coaching_summary="Solid performance",
        evaluated_at=datetime.now(timezone.utc),
        saved_to_db=False,
        db_status="unconfigured",
    )

    eval_q2 = AnswerEvaluationResponse(
        session_id=session_id,
        question_id="q_2",
        overall_score=70.0,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=7, feedback="Relevant answer comparing both concurrency models."),
            technical_depth=CriterionScore(score=7, feedback="Decent depth regarding lock contention issues."),
            completeness=CriterionScore(score=7, feedback="Complete analysis of optimistic validation phases."),
            structure_flow=CriterionScore(score=7, feedback="Good structure differentiating read vs write costs."),
            clarity_conciseness=CriterionScore(score=7, feedback="Concise explanation of commit rollbacks."),
        ),
        strengths=["Understands locks"],
        areas_for_improvement=["Could elaborate on MVCC"],
        actionable_suggestions=["Study MVCC"],
        coaching_summary="Good answer",
        evaluated_at=datetime.now(timezone.utc),
        saved_to_db=False,
        db_status="unconfigured",
    )

    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(question_id="q_1", answer_text="Two phase commit guarantees atomicity."),
    )
    await save_evaluation(session_id=session_id, question_id="q_1", evaluation=eval_q1)

    await submit_answer(
        session_id=session_id,
        answer_data=SubmitAnswerRequest(question_id="q_2", answer_text="Optimistic concurrency uses version checks."),
    )
    await save_evaluation(session_id=session_id, question_id="q_2", evaluation=eval_q2)

    # 2. Record multiple integrity events:
    # Q1: 5-second tab switch
    t0 = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(
            event_type=IntegrityEventType.TAB_HIDDEN,
            timestamp=t0,
            question_id="q_1",
        ),
    )
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(
            event_type=IntegrityEventType.TAB_VISIBLE,
            timestamp=t0 + timedelta(seconds=5),
            question_id="q_1",
        ),
    )

    # Q2: Window blur/focus + unmatched tab hidden
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(
            event_type=IntegrityEventType.WINDOW_BLUR,
            timestamp=t0 + timedelta(seconds=10),
            question_id="q_2",
        ),
    )
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(
            event_type=IntegrityEventType.WINDOW_FOCUS,
            timestamp=t0 + timedelta(seconds=12),
            question_id="q_2",
        ),
    )
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(
            event_type=IntegrityEventType.TAB_HIDDEN,
            timestamp=t0 + timedelta(seconds=15),
            question_id="q_2",
        ),
    )

    # Session-level unassociated event
    await record_integrity_event(
        session_id=session_id,
        event_data=IntegrityEventCreate(
            event_type=IntegrityEventType.CAMERA_MIC_GRANTED,
            timestamp=t0 + timedelta(seconds=20),
            question_id=None,
        ),
    )

    # 3. Fetch final report
    response = client.get(f"/api/interviews/{session_id}/report")
    assert response.status_code == 200
    report_data = response.json()

    # 4. Strict Score Isolation Verification:
    # Average score: (80.0 + 70.0) / 2 = 75.0
    assert report_data["overall_score"] == 75.0
    assert report_data["score_status"] == "calculated"
    assert report_data["criterion_averages"]["relevance"] == 7.5
    assert report_data["criterion_averages"]["technical_depth"] == 7.5

    # 5. Integrity Intelligence Verification:
    integ = report_data["integrity_summary"]
    assert integ["total_events"] == 6
    assert integ["cumulative_unfocused_seconds"] == 5.0
    assert integ["incomplete_intervals_count"] == 1
    assert integ["events_by_question"] == {"q_1": 2, "q_2": 3, "unassociated": 1}
    assert "None (Excluded from candidate capability scoring)" in integ["score_impact"]

    # Timeline preserves chronological ordering
    timeline = integ["events_timeline"]
    assert len(timeline) == 6
    assert timeline[0]["event_type"] == "tab_hidden"
    assert timeline[0]["question_id"] == "q_1"
    assert timeline[-1]["event_type"] == "camera_mic_granted"
    assert timeline[-1]["question_id"] is None
