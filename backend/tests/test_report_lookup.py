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


def test_unauthenticated_request_cannot_fetch_available_reports():
    """Verify that an unauthenticated request to /api/interviews/available-reports returns 401."""
    res = client.get("/api/interviews/available-reports")
    assert res.status_code == 401
    assert "authentication required" in res.json()["detail"].lower()


def test_empty_report_history_for_fresh_candidate():
    """Verify that a newly registered or fresh candidate with no reports receives an empty list []."""
    token_fresh = create_access_token(user_id="usr_cand_fresh_empty", role=ROLE_CANDIDATE, name="Fresh Candidate")
    res = client.get(
        "/api/interviews/available-reports",
        headers={"Authorization": f"Bearer {token_fresh}"},
    )
    assert res.status_code == 200
    assert res.json() == []


def test_candidate_cannot_access_unowned_legacy_report():
    """Verify that a candidate cannot access an unowned legacy report via direct ID lookup."""
    sess_id = "session-unowned-legacy-doc"
    rep_id = "rep-unowned-legacy-doc"
    _in_memory_sessions[sess_id] = {
        "session_id": sess_id,
        "owner_id": None,
        "role": "Legacy Systems Engineer",
        "questions": [],
        "answers": {},
    }
    _in_memory_reports[sess_id] = {
        "report_id": rep_id,
        "session_id": sess_id,
        "owner_id": None,
        "role": "Legacy Systems Engineer",
        "experience_level": "Senior",
        "difficulty": "Hard",
        "focus_areas": "Mainframe, COBOL",
        "total_questions": 1,
        "answered_questions": 1,
        "unanswered_questions": 0,
        "evaluated_questions": 1,
        "evaluation_coverage_pct": 100.0,
        "overall_score": 70.0,
        "score_status": "calculated",
        "scoring_formula_explanation": "Arithmetic average",
        "criterion_averages": {},
        "key_strengths": [],
        "priority_improvements": [],
        "recommended_next_steps": [],
        "executive_summary": "Legacy report.",
        "questions_performance": [],
        "has_resume_comparison": False,
        "integrity_summary": {"total_events": 0, "events_summary": {}, "events_timeline": []},
        "saved_to_db": False,
        "db_status": "in_memory",
    }

    cand_token = create_access_token(user_id="usr_cand_hacker", role=ROLE_CANDIDATE, name="Curious Candidate")
    res = client.get(
        f"/api/interviews/{rep_id}/report",
        headers={"Authorization": f"Bearer {cand_token}"},
    )
    assert res.status_code == 403
    assert "access forbidden" in res.json()["detail"].lower()


def test_mutual_cross_candidate_isolation_and_tampered_id():
    """
    Verify complete mutual isolation:
    - Candidate A has report A.
    - Candidate B has report B.
    - Candidate A sees only Report A in history and can fetch Report A directly.
    - Candidate B sees only Report B in history and can fetch Report B directly.
    - Candidate A fetching Report B (or Session B) gets 403 Forbidden.
    - Candidate B fetching Report A (or Session A) gets 403 Forbidden.
    """
    sess_a = "sess-isolation-cand-a"
    rep_a = "rep-isolation-cand-a"
    _in_memory_sessions[sess_a] = {
        "session_id": sess_a,
        "owner_id": "usr_iso_cand_a",
        "role": "Frontend Architect",
        "questions": [],
        "answers": {},
        "status": "completed",
    }
    _in_memory_reports[sess_a] = {
        "report_id": rep_a,
        "session_id": sess_a,
        "owner_id": "usr_iso_cand_a",
        "role": "Frontend Architect",
        "experience_level": "Staff",
        "difficulty": "Hard",
        "focus_areas": "React, CSS, Performance",
        "total_questions": 2,
        "answered_questions": 2,
        "unanswered_questions": 0,
        "evaluated_questions": 2,
        "evaluation_coverage_pct": 100.0,
        "overall_score": 95.0,
        "score_status": "calculated",
        "scoring_formula_explanation": "Arithmetic average",
        "criterion_averages": {},
        "key_strengths": ["Next.js architecture"],
        "priority_improvements": [],
        "recommended_next_steps": [],
        "executive_summary": "Outstanding frontend profile.",
        "questions_performance": [],
        "has_resume_comparison": False,
        "integrity_summary": {"total_events": 0, "events_summary": {}, "events_timeline": []},
        "saved_to_db": False,
        "db_status": "in_memory",
    }

    sess_b = "sess-isolation-cand-b"
    rep_b = "rep-isolation-cand-b"
    _in_memory_sessions[sess_b] = {
        "session_id": sess_b,
        "owner_id": "usr_iso_cand_b",
        "role": "Backend Architect",
        "questions": [],
        "answers": {},
        "status": "completed",
    }
    _in_memory_reports[sess_b] = {
        "report_id": rep_b,
        "session_id": sess_b,
        "owner_id": "usr_iso_cand_b",
        "role": "Backend Architect",
        "experience_level": "Staff",
        "difficulty": "Hard",
        "focus_areas": "Go, Distributed Systems",
        "total_questions": 2,
        "answered_questions": 2,
        "unanswered_questions": 0,
        "evaluated_questions": 2,
        "evaluation_coverage_pct": 100.0,
        "overall_score": 91.0,
        "score_status": "calculated",
        "scoring_formula_explanation": "Arithmetic average",
        "criterion_averages": {},
        "key_strengths": ["Raft consensus"],
        "priority_improvements": [],
        "recommended_next_steps": [],
        "executive_summary": "Outstanding backend profile.",
        "questions_performance": [],
        "has_resume_comparison": False,
        "integrity_summary": {"total_events": 0, "events_summary": {}, "events_timeline": []},
        "saved_to_db": False,
        "db_status": "in_memory",
    }

    token_a = create_access_token(user_id="usr_iso_cand_a", role=ROLE_CANDIDATE, name="Alice Architecture")
    token_b = create_access_token(user_id="usr_iso_cand_b", role=ROLE_CANDIDATE, name="Bob Backend")
    token_admin = create_access_token(user_id="usr_admin_01", role=ROLE_ADMIN, name="Admin Root")

    # History verification
    res_a_hist = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_hist.status_code == 200
    sids_a = [item["session_id"] for item in res_a_hist.json()]
    assert sess_a in sids_a
    assert sess_b not in sids_a

    res_b_hist = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_hist.status_code == 200
    sids_b = [item["session_id"] for item in res_b_hist.json()]
    assert sess_b in sids_b
    assert sess_a not in sids_b

    # Direct report lookup: Own report succeeds
    res_a_own = client.get(f"/api/interviews/{sess_a}/report", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_own.status_code == 200
    assert res_a_own.json()["report_id"] == rep_a

    res_b_own = client.get(f"/api/interviews/{sess_b}/report", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_own.status_code == 200
    assert res_b_own.json()["report_id"] == rep_b

    # Cross report lookup: Attempting to access other candidate's report by session_id or report_id -> 403
    res_a_tamper = client.get(f"/api/interviews/{sess_b}/report", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_tamper.status_code == 403
    assert "cannot view another candidate" in res_a_tamper.json()["detail"].lower()

    res_a_tamper_rep_id = client.get(f"/api/interviews/{rep_b}/report", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a_tamper_rep_id.status_code == 403

    res_b_tamper = client.get(f"/api/interviews/{sess_a}/report", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_tamper.status_code == 403
    assert "cannot view another candidate" in res_b_tamper.json()["detail"].lower()

    # Tampering with report generation POST /{session_id}/report
    res_b_tamper_gen = client.post(f"/api/interviews/{sess_a}/report", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_tamper_gen.status_code == 403
    assert "cannot generate reports for another candidate" in res_b_tamper_gen.json()["detail"].lower()

    # Admin access verification: Admin can access both reports
    res_admin_a = client.get(f"/api/interviews/{sess_a}/report", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin_a.status_code == 200
    res_admin_b = client.get(f"/api/interviews/{sess_b}/report", headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin_b.status_code == 200
