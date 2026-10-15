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
from app.services.resume_service import store_resume_analysis, _in_memory_analyses
from app.schemas.resume import AIRawSkillGapOutput, SkillEvidenceItem, SkillEvidenceCategory

client = TestClient(app)


def test_unauthenticated_access_rejected_on_protected_routes():
    """Verify that unauthenticated callers are rejected with 401 on protected decision intelligence routes."""
    # Decision overview
    res1 = client.get("/api/decision/overview")
    assert res1.status_code == 401
    assert "authentication required" in res1.json()["detail"].lower()

    # Dossier detail
    res2 = client.get("/api/decision/dossier/some-dossier-id")
    assert res2.status_code == 401

    # Record reviewer determination
    res3 = client.post(
        "/api/decision/dossier/some-dossier-id/review",
        json={"reviewer_name": "Sarah", "recommendation": "Advance"},
    )
    assert res3.status_code == 401

    # Auth profile
    res4 = client.get("/api/auth/me")
    assert res4.status_code == 401


def test_authentication_token_issuance_and_validation():
    """Verify login endpoint validates credentials and returns cryptographically signed JWT token."""
    # Valid candidate login
    cand_resp = client.post(
        "/api/auth/token",
        json={"username": "candidate_demo", "password": "CandidatePass123!"},
    )
    assert cand_resp.status_code == 200
    cand_data = cand_resp.json()
    assert cand_data["role"] == "candidate"
    assert "access_token" in cand_data
    token = cand_data["access_token"]

    # Verify GET /api/auth/me
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "candidate"
    assert "interview:create" in me_resp.json()["permissions"]

    # Invalid password rejected
    bad_resp = client.post(
        "/api/auth/token",
        json={"username": "candidate_demo", "password": "WrongPassword!"},
    )
    assert bad_resp.status_code == 401

    # Invalid token rejected
    bad_token_resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
    assert bad_token_resp.status_code == 401


def test_demo_role_token_endpoint():
    """Verify demo-token endpoint issues genuine signed tokens for candidate, reviewer, and admin."""
    for role_name in ["candidate", "reviewer", "admin"]:
        res = client.post("/api/auth/demo-token", json={"role": role_name})
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == role_name
        assert "access_token" in data

    # Unknown role rejected
    bad_res = client.post("/api/auth/demo-token", json={"role": "super_hacker"})
    assert bad_res.status_code == 400


def test_candidate_forbidden_from_reviewer_actions():
    """Verify that a caller with Candidate role is rejected with 403 Forbidden on reviewer endpoints."""
    cand_token = create_access_token(user_id="usr_cand_01", role=ROLE_CANDIDATE, name="Alex Mercer")
    headers = {"Authorization": f"Bearer {cand_token}"}

    # Candidate attempting to view all dossiers overview
    res1 = client.get("/api/decision/overview", headers=headers)
    assert res1.status_code == 403
    assert "lacks permission" in res1.json()["detail"].lower()

    # Candidate attempting to submit hiring determination
    res2 = client.post(
        "/api/decision/dossier/test-record-id/review",
        json={"reviewer_name": "Alex Mercer", "recommendation": "Strong Hire"},
        headers=headers,
    )
    assert res2.status_code == 403
    assert "lacks permission" in res2.json()["detail"].lower()

    # Candidate attempting to submit decision on integrity explanation
    _in_memory_sessions["sess-int-01"] = {
        "session_id": "sess-int-01",
        "owner_id": "usr_cand_01",
        "candidate_explanations": [{"explanation_id": "exp-01", "explanation_text": "Benign switch"}],
    }
    res3 = client.post(
        "/api/interviews/sess-int-01/integrity-explanations/exp-01/decision",
        json={"reviewer_name": "Alex Mercer", "determination": "accepted", "explanation": "Self-cleared"},
        headers=headers,
    )
    assert res3.status_code == 403
    assert "lacks permission" in res3.json()["detail"].lower()


def test_reviewer_permitted_for_dossiers_and_reviews():
    """Verify that a caller with Reviewer role can view decision intelligence and submit reviewer decisions."""
    # Seed in-memory dossier
    _in_memory_analyses["test-resume-dossier-01"] = {
        "analysis_id": "test-resume-dossier-01",
        "role": "Cloud Architect",
        "experience_level": "Senior",
        "extracted_skills": ["Kubernetes", "Terraform", "GCP"],
        "skill_evaluations": [
            {
                "skill_name": "Kubernetes",
                "category": "Demonstrated in Resume",
                "evidence": "Led multi-cluster migration.",
            }
        ],
        "created_at": "2026-10-12T00:00:00Z",
    }

    reviewer_token = create_access_token(user_id="usr_rev_01", role=ROLE_REVIEWER, name="Sarah Chen")
    headers = {"Authorization": f"Bearer {reviewer_token}"}

    # 1. Overview permitted
    overview_res = client.get("/api/decision/overview", headers=headers)
    assert overview_res.status_code == 200
    assert overview_res.json()["total_records"] >= 1

    # 2. Record determination permitted
    review_payload = {
        "reviewer_name": "Spoofed Name Attempt",
        "recommendation": "Advance to Leadership Screen",
        "notes": "Verified candidate multi-cluster experience.",
    }
    review_res = client.post(
        "/api/decision/dossier/test-resume-dossier-01/review",
        json=review_payload,
        headers=headers,
    )
    assert review_res.status_code == 201
    review_data = review_res.json()
    # Verified reviewer identity from token overrides spoofed name in body!
    assert review_data["reviewer_name"] == "Sarah Chen"
    assert review_data["recommendation"] == "Advance to Leadership Screen"


def test_cross_candidate_resource_isolation():
    """Verify that Candidate A cannot view Candidate B's private session or report."""
    # Create Candidate B's private session
    session_b_id = "session-private-candidate-b"
    _in_memory_sessions[session_b_id] = {
        "session_id": session_b_id,
        "owner_id": "usr_cand_02",  # Candidate B
        "role": "Data Scientist",
        "questions": [{"id": "q1", "text": "Explain transformers."}],
        "answers": {},
    }

    token_candidate_a = create_access_token(user_id="usr_cand_01", role=ROLE_CANDIDATE, name="Alex Mercer")
    token_candidate_b = create_access_token(user_id="usr_cand_02", role=ROLE_CANDIDATE, name="Bob Vance")
    token_reviewer = create_access_token(user_id="usr_rev_01", role=ROLE_REVIEWER, name="Sarah Chen")

    # 1. Candidate B can access their own session
    res_b = client.get(
        f"/api/interviews/{session_b_id}",
        headers={"Authorization": f"Bearer {token_candidate_b}"},
    )
    assert res_b.status_code == 200

    # 2. Candidate A is rejected with 403 Forbidden
    res_a = client.get(
        f"/api/interviews/{session_b_id}",
        headers={"Authorization": f"Bearer {token_candidate_a}"},
    )
    assert res_a.status_code == 403
    assert "cannot view another candidate" in res_a.json()["detail"].lower()

    # 3. Reviewer can access Candidate B's session
    res_rev = client.get(
        f"/api/interviews/{session_b_id}",
        headers={"Authorization": f"Bearer {token_reviewer}"},
    )
    assert res_rev.status_code == 200

    # 4. Unauthenticated caller is rejected with 401 Unauthorized
    res_unauth = client.get(f"/api/interviews/{session_b_id}")
    assert res_unauth.status_code == 401
    assert "authentication required" in res_unauth.json()["detail"].lower()


def test_demo_token_disabled_in_production_environment(monkeypatch):
    """Verify that /api/auth/demo-token is rejected with 403 when ENVIRONMENT is production."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    res = client.post("/api/auth/demo-token", json={"role": "admin"})
    assert res.status_code == 403
    assert "disabled in production" in res.json()["detail"].lower()


def test_candidate_registration_and_immediate_login():
    """Verify that a candidate can register, receive a JWT token, and authenticate immediately."""
    import uuid
    uname = f"cand_test_{uuid.uuid4().hex[:6]}"
    reg_payload = {
        "username": uname,
        "password": "ValidPassword123!",
        "name": "Jordan Smith",
        "email": f"{uname}@example.com",
    }
    reg_res = client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    data = reg_res.json()
    assert data["role"] == "candidate"
    assert data["username"] == uname
    assert "access_token" in data

    # Verify newly registered candidate can authenticate via /api/auth/token
    login_res = client.post(
        "/api/auth/token",
        json={"username": uname, "password": "ValidPassword123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Verify caller profile
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "candidate"
    assert me_res.json()["name"] == "Jordan Smith"


def test_candidate_registration_rejects_duplicate_credentials():
    """Verify that duplicate username or duplicate email is rejected with 409 Conflict."""
    import uuid
    uname = f"cand_dup_{uuid.uuid4().hex[:6]}"
    payload = {
        "username": uname,
        "password": "Password123!",
        "name": "Dup User",
        "email": f"{uname}@test.com",
    }
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    # Duplicate username
    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()

    # Different username, duplicate email
    payload_diff_user = {
        "username": f"another_{uuid.uuid4().hex[:6]}",
        "password": "Password123!",
        "name": "Another User",
        "email": f"{uname}@test.com",
    }
    res3 = client.post("/api/auth/register", json=payload_diff_user)
    assert res3.status_code == 409
    assert "already registered" in res3.json()["detail"].lower()


def test_candidate_registration_prevents_privilege_escalation():
    """Verify that requesting reviewer or admin in registration is strictly ignored or prevented."""
    import uuid
    uname = f"cand_hacker_{uuid.uuid4().hex[:6]}"
    payload = {
        "username": uname,
        "password": "Password123!",
        "name": "Hacker Attempt",
        "email": f"{uname}@test.com",
        "role": "admin",  # Malicious attempt to self-assign admin role!
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    # MUST BE FORCED TO CANDIDATE!
    assert data["role"] == "candidate"

    # Verify that the generated token is rejected on protected admin/reviewer endpoints
    token = data["access_token"]
    rev_res = client.get("/api/decision/overview", headers={"Authorization": f"Bearer {token}"})
    assert rev_res.status_code == 403
    assert "lacks permission" in rev_res.json()["detail"].lower()


def test_email_login_for_demo_and_registered_users():
    """Verify that users can log in using their email address instead of username."""
    # 1. Candidate login by email
    cand_res = client.post(
        "/api/auth/token",
        json={"username": "candidate@interviewiq.com", "password": "CandidatePass123!"},
    )
    assert cand_res.status_code == 200
    assert cand_res.json()["role"] == "candidate"

    # 2. Reviewer login by email
    rev_res = client.post(
        "/api/auth/token",
        json={"username": "reviewer@interviewiq.com", "password": "ReviewerPass123!"},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["role"] == "reviewer"

    # 3. Admin login by email
    adm_res = client.post(
        "/api/auth/token",
        json={"username": "admin@interviewiq.com", "password": "AdminPass123!"},
    )
    assert adm_res.status_code == 200
    assert adm_res.json()["role"] == "admin"


def test_session_expiration_and_malformed_tokens():
    """Verify that expired tokens and malformed signatures return 401 Unauthorized."""
    from datetime import timedelta
    # Token expired 10 minutes ago
    expired_token = create_access_token(
        user_id="usr_cand_01",
        role=ROLE_CANDIDATE,
        name="Alex Mercer",
        expires_delta=timedelta(minutes=-10),
    )
    exp_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert exp_res.status_code == 401
    assert "expired" in exp_res.json()["detail"].lower()

    # Tampered signature
    tampered_token = expired_token[:-5] + "XXXXX"
    tamper_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert tamper_res.status_code == 401
    assert "invalid" in tamper_res.json()["detail"].lower()
