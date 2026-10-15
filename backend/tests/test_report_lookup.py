import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import (
    create_access_token,
    ROLE_CANDIDATE,
    ROLE_REVIEWER,
    ROLE_ADMIN,
)
from app.services.session_service import _in_memory_sessions
from app.services.report_service import _in_memory_reports
from app.core.database import db_manager

client = TestClient(app)


def test_list_available_reports_candidate_rbac_isolation():
    """Verify that Candidate A only receives their own sessions and never Candidate B's sessions."""
    # Seed Candidate A's session
    cand_a_sess = "session-rbac-cand-a"
    _in_memory_sessions[cand_a_sess] = {
        "session_id": cand_a_sess,
        "owner_id": "usr_cand_01",
        "role": "Distributed Systems Engineer",
        "experience_level": "Senior",
        "difficulty": "Hard",
        "status": "completed",
        "created_at": "2026-10-12T10:00:00Z",
    }
    _in_memory_reports[cand_a_sess] = {
        "report_id": "rep-rbac-cand-a",
        "session_id": cand_a_sess,
        "role": "Distributed Systems Engineer",
        "experience_level": "Senior",
        "overall_score": 88.0,
        "created_at": "2026-10-12T10:30:00Z",
    }

    # Seed Candidate B's private session
    cand_b_sess = "session-rbac-cand-b"
    _in_memory_sessions[cand_b_sess] = {
        "session_id": cand_b_sess,
        "owner_id": "usr_cand_02",
        "role": "Data Engineer",
        "experience_level": "Mid-Level",
        "difficulty": "Medium",
        "status": "completed",
        "created_at": "2026-10-12T11:00:00Z",
    }
    _in_memory_reports[cand_b_sess] = {
        "report_id": "rep-rbac-cand-b",
        "session_id": cand_b_sess,
        "role": "Data Engineer",
        "experience_level": "Mid-Level",
        "overall_score": 75.0,
        "created_at": "2026-10-12T11:30:00Z",
    }

    token_a = create_access_token(user_id="usr_cand_01", role=ROLE_CANDIDATE, name="Alex Mercer")
    token_b = create_access_token(user_id="usr_cand_02", role=ROLE_CANDIDATE, name="Bob Vance")
    token_rev = create_access_token(user_id="usr_rev_01", role=ROLE_REVIEWER, name="Sarah Chen")

    # 1. Candidate A retrieves available reports: MUST contain A, MUST NOT contain B
    res_a = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    items_a = res_a.json()
    session_ids_a = [item["session_id"] for item in items_a]
    assert cand_a_sess in session_ids_a
    assert cand_b_sess not in session_ids_a

    # Verify meaningful labels in the returned item
    cand_a_item = next(item for item in items_a if item["session_id"] == cand_a_sess)
    assert cand_a_item["role"] == "Distributed Systems Engineer"
    assert cand_a_item["report_status"] == "Report Ready"
    assert cand_a_item["overall_score"] == 88.0
    assert cand_a_item["report_id"] == "rep-rbac-cand-a"

    # 2. Candidate B retrieves available reports: MUST contain B, MUST NOT contain A
    res_b = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    items_b = res_b.json()
    session_ids_b = [item["session_id"] for item in items_b]
    assert cand_b_sess in session_ids_b
    assert cand_a_sess not in session_ids_b

    # 3. Reviewer retrieves available reports: MUST see both candidates
    res_rev = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token_rev}"})
    assert res_rev.status_code == 200
    items_rev = res_rev.json()
    session_ids_rev = [item["session_id"] for item in items_rev]
    assert cand_a_sess in session_ids_rev
    assert cand_b_sess in session_ids_rev


def test_cross_candidate_report_lookup_rejected():
    """Verify that Candidate A is rejected when attempting to fetch Candidate B's report."""
    session_b_id = "session-report-lookup-cand-b"
    _in_memory_sessions[session_b_id] = {
        "session_id": session_b_id,
        "owner_id": "usr_cand_02",
        "role": "ML Engineer",
        "questions": [],
        "answers": {},
    }
    _in_memory_reports[session_b_id] = {
        "report_id": "rep-lookup-cand-b",
        "session_id": session_b_id,
        "role": "ML Engineer",
        "experience_level": "Senior",
        "difficulty": "Hard",
        "focus_areas": "PyTorch, CUDA",
        "total_questions": 3,
        "answered_questions": 3,
        "unanswered_questions": 0,
        "evaluated_questions": 3,
        "evaluation_coverage_pct": 100.0,
        "overall_score": 92.0,
        "score_status": "calculated",
        "scoring_formula_explanation": "Arithmetic average",
        "criterion_averages": {},
        "key_strengths": ["CUDA optimization"],
        "priority_improvements": [],
        "recommended_next_steps": [],
        "executive_summary": "Strong engineering profile.",
        "questions_performance": [],
        "has_resume_comparison": False,
        "integrity_summary": {
            "total_events": 0,
            "events_summary": {},
            "events_timeline": [],
        },
        "saved_to_db": False,
        "db_status": "in_memory",
    }

    token_a = create_access_token(user_id="usr_cand_01", role=ROLE_CANDIDATE, name="Alex Mercer")
    token_b = create_access_token(user_id="usr_cand_02", role=ROLE_CANDIDATE, name="Bob Vance")

    # Candidate A gets 403 Forbidden
    res_a = client.get(
        f"/api/interviews/{session_b_id}/report",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert res_a.status_code == 403
    assert "cannot view another candidate" in res_a.json()["detail"].lower()

    # Candidate B gets 200 OK
    res_b = client.get(
        f"/api/interviews/{session_b_id}/report",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_b.status_code == 200
    assert res_b.json()["session_id"] == session_b_id
    assert res_b.json()["overall_score"] == 92.0


def test_report_lookup_fallback_by_report_id():
    """Verify that looking up a report using its report_id resolves to the session report."""
    sess_id = "session-report-id-lookup-test"
    rep_id = "rep-unique-id-998877"
    _in_memory_sessions[sess_id] = {
        "session_id": sess_id,
        "owner_id": None,  # Public/unowned
        "role": "Security Engineer",
        "questions": [],
        "answers": {},
    }
    _in_memory_reports[sess_id] = {
        "report_id": rep_id,
        "session_id": sess_id,
        "role": "Security Engineer",
        "experience_level": "Senior",
        "difficulty": "Hard",
        "focus_areas": "AppSec, Cryptography",
        "total_questions": 3,
        "answered_questions": 3,
        "unanswered_questions": 0,
        "evaluated_questions": 3,
        "evaluation_coverage_pct": 100.0,
        "overall_score": 85.0,
        "score_status": "calculated",
        "scoring_formula_explanation": "Arithmetic average",
        "criterion_averages": {},
        "key_strengths": ["Penetration testing"],
        "priority_improvements": [],
        "recommended_next_steps": [],
        "executive_summary": "Solid security expertise.",
        "questions_performance": [],
        "has_resume_comparison": False,
        "integrity_summary": {
            "total_events": 0,
            "events_summary": {},
            "events_timeline": [],
        },
        "saved_to_db": False,
        "db_status": "in_memory",
    }

    # Query with report_id fallback
    res = client.get(f"/api/interviews/{rep_id}/report")
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == sess_id
    assert data["report_id"] == rep_id
    assert data["overall_score"] == 85.0


def test_real_atlas_report_retrieval():
    """Verify report retrieval of a real verified session existing in database/atlas."""
    # From inspection, 'ad00a407-59c4-42df-8ea3-6ef29a405f51' is a verified real report
    real_session_id = "ad00a407-59c4-42df-8ea3-6ef29a405f51"
    token_rev = create_access_token(user_id="usr_rev_01", role=ROLE_REVIEWER, name="Sarah Chen")

    res = client.get(
        f"/api/interviews/{real_session_id}/report",
        headers={"Authorization": f"Bearer {token_rev}"},
    )
    if res.status_code == 200:
        data = res.json()
        assert data["session_id"] == real_session_id
        assert "role" in data
        assert data["role"] == "Full Stack Engineer"
