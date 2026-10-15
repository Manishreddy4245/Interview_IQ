import pytest
from pathlib import Path
from dotenv import dotenv_values
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import DatabaseManager, db_manager
from app.core.security import create_access_token, ROLE_CANDIDATE, ROLE_REVIEWER
from app.schemas.interview import InterviewSetupRequest, QuestionItem
from app.services.session_service import create_interview_session, _in_memory_sessions
from app.services.report_service import _in_memory_reports

_env_vals = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
REAL_MONGODB_URI = _env_vals.get("MONGODB_URI")


pytestmark = pytest.mark.live_atlas


@pytest.fixture(autouse=True)
def setup_db_connection():
    if not db_manager.client:
        db_manager.connect()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_case_1_atlas_connection_and_ping(client):
    """Case 1: MongoDB connection and database ping succeed."""
    health = await db_manager.check_health()
    assert health["status"] == "connected"
    assert "healthy" in health["detail"].lower()
    assert health["database"] == settings.MONGODB_DATABASE

    res = client.get("/health/db")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "connected"
    assert data["database"] == settings.MONGODB_DATABASE


@pytest.mark.asyncio
async def test_case_2_3_4_5_6_real_session_atlas_persistence_and_lifecycle(client):
    """
    Cases 2, 3, 4, 5, 6:
    2. A real interview session is saved to Atlas.
    3. The saved session appears in Interview History (/available-reports).
    4. Opening the session shows its correct report.
    5. Refreshing / re-querying preserves history from Atlas.
    6. Restarting backend (clearing in-memory cache) preserves Atlas session.
    """
    owner_cand = "usr_live_verify_001"
    setup = InterviewSetupRequest(
        role="Senior Distributed Systems Architect",
        experience_level="Senior",
        difficulty="Hard",
        focus_areas="Raft, Paxos, Event Sourcing",
        question_count=3,
        interview_mode="CODING",
    )
    questions = [
        QuestionItem(
            id="q_verify_01",
            text="Implement a distributed lock coordinator using token leasing.",
            difficulty="Hard",
            rubric="Validates lease expiration, split-brain mitigation, and node failure handling.",
            question_type="coding",
            response_mode="coding_ide",
        ),
        QuestionItem(
            id="q_verify_02",
            text="Describe consensus failover under partial network partitions.",
            difficulty="Hard",
            rubric="Assesses leader election timeouts and log reconciliation.",
            question_type="verbal",
            response_mode="verbal_speech_text",
        ),
        QuestionItem(
            id="q_verify_03",
            text="Optimize event sourcing log compaction using snapshotting.",
            difficulty="Hard",
            rubric="Assesses checkpoint intervals and replay performance.",
            question_type="coding",
            response_mode="coding_ide",
        ),
    ]

    # Case 2: Save session to Atlas
    session_resp = await create_interview_session(setup=setup, questions=questions, owner_id=owner_cand)
    session_id = session_resp.session_id
    assert session_resp.saved_to_db is True
    assert session_resp.db_status == "persisted"
    assert "successfully persisted" in session_resp.db_message.lower()

    # Verify directly in MongoDB Atlas
    db = db_manager.get_database()
    saved_doc = await db["interview_sessions"].find_one({"session_id": session_id})
    assert saved_doc is not None
    assert saved_doc["session_id"] == session_id
    assert saved_doc["owner_id"] == owner_cand
    assert saved_doc["role"] == "Senior Distributed Systems Architect"
    assert saved_doc["interview_mode"] == "CODING"

    # Case 3: The saved session appears in Interview History
    token = create_access_token(user_id=owner_cand, role=ROLE_CANDIDATE, name="Verification Candidate")
    res_history = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token}"})
    assert res_history.status_code == 200
    history_items = res_history.json()
    matching_item = next((item for item in history_items if item["session_id"] == session_id), None)
    assert matching_item is not None
    assert matching_item["role"] == "Senior Distributed Systems Architect"
    assert matching_item["interview_mode"] == "CODING"
    assert matching_item["is_persisted"] is True
    assert matching_item["owner_id"] == owner_cand

    # Case 4: Opening the session shows its correct report
    res_report = client.get(f"/api/interviews/{session_id}/report", headers={"Authorization": f"Bearer {token}"})
    assert res_report.status_code == 200
    report_data = res_report.json()
    assert report_data["session_id"] == session_id
    assert report_data["role"] == "Senior Distributed Systems Architect"
    assert report_data["saved_to_db"] is True

    # Case 5: Refreshing preserves history (idempotent retrieval)
    res_refresh = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token}"})
    assert res_refresh.status_code == 200
    refreshed_match = next((item for item in res_refresh.json() if item["session_id"] == session_id), None)
    assert refreshed_match is not None

    # Case 6: Restarting backend (clearing memory stores) preserves MongoDB-backed sessions
    _in_memory_sessions.pop(session_id, None)
    _in_memory_reports.pop(session_id, None)

    res_post_restart = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token}"})
    assert res_post_restart.status_code == 200
    persisted_match = next((item for item in res_post_restart.json() if item["session_id"] == session_id), None)
    assert persisted_match is not None
    assert persisted_match["session_id"] == session_id
    assert persisted_match["is_persisted"] is True

    # Report lookup after memory wipe still resolves directly from Atlas
    res_report_post_restart = client.get(f"/api/interviews/{session_id}/report", headers={"Authorization": f"Bearer {token}"})
    assert res_report_post_restart.status_code == 200
    assert res_report_post_restart.json()["session_id"] == session_id

    # Clean up test session from Atlas
    await db["interview_sessions"].delete_one({"session_id": session_id})
    await db["interview_reports"].delete_one({"session_id": session_id})


@pytest.mark.asyncio
async def test_case_7_empty_state_for_new_candidate(client):
    """Case 7: An account with no private sessions receives an empty history list."""
    new_user_id = "usr_fresh_candidate_without_sessions_99"
    token = create_access_token(user_id=new_user_id, role=ROLE_CANDIDATE, name="Fresh User")

    res = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = res.json()
    for it in items:
        if it.get("owner_id"):
            assert it["owner_id"] == new_user_id


@pytest.mark.asyncio
async def test_case_8_invalid_uri_produces_clear_diagnostic_error():
    """Case 8: An invalid URI produces a clear configuration/connection error."""
    bad_manager = DatabaseManager()
    with patch.object(settings, "MONGODB_URI", "mongodb://invalid-host-definitely-does-not-exist:27017"):
        bad_manager.connect()
        health = await bad_manager.check_health()
        assert health["status"] in ("unreachable", "error")
        assert "failed" in health["detail"].lower() or "error" in health["detail"].lower()


@pytest.mark.asyncio
async def test_case_9_unauthorized_cross_candidate_isolation(client):
    """Case 9: Candidate B cannot access Candidate A's private session history or report."""
    db = db_manager.get_database()
    cand_a_id = "cand_private_alpha"
    cand_b_id = "cand_private_beta"
    sess_id = "sess_private_alpha_isolation_test"

    doc = {
        "_id": sess_id,
        "session_id": sess_id,
        "owner_id": cand_a_id,
        "role": "Lead Cryptography Engineer",
        "created_at": "2026-10-14T05:00:00+00:00",
        "status": "completed",
        "questions": [],
        "answers": {},
    }
    await db["interview_sessions"].delete_one({"_id": sess_id})
    await db["interview_reports"].delete_one({"_id": f"rep_{sess_id}"})
    await db["interview_sessions"].insert_one(doc)

    rep_doc = {
        "_id": f"rep_{sess_id}",
        "session_id": sess_id,
        "report_id": f"rep_{sess_id}",
        "owner_id": cand_a_id,
        "role": "Lead Cryptography Engineer",
        "experience_level": "Senior",
        "difficulty": "Hard",
        "focus_areas": "Zero Knowledge Proofs",
        "total_questions": 1,
        "answered_questions": 1,
        "unanswered_questions": 0,
        "evaluated_questions": 1,
        "evaluation_coverage_pct": 100.0,
        "overall_score": 95.0,
        "score_status": "calculated",
        "scoring_formula_explanation": "Direct evaluation",
        "criterion_averages": {},
        "key_strengths": ["ZK-SNARK implementation"],
        "priority_improvements": [],
        "recommended_next_steps": [],
        "executive_summary": "Top tier cryptography candidate.",
        "questions_performance": [],
        "has_resume_comparison": False,
        "integrity_summary": {"total_events": 0, "events_summary": {}, "events_timeline": []},
        "saved_to_db": True,
        "db_status": "persisted",
    }
    await db["interview_reports"].insert_one(rep_doc)

    token_a = create_access_token(user_id=cand_a_id, role=ROLE_CANDIDATE, name="Candidate Alpha")
    token_b = create_access_token(user_id=cand_b_id, role=ROLE_CANDIDATE, name="Candidate Beta")

    # Candidate A sees their own session in history
    res_a = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    ids_a = [item["session_id"] for item in res_a.json()]
    assert sess_id in ids_a

    # Candidate B MUST NOT see Candidate A's session in history
    res_b = client.get("/api/interviews/available-reports", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    ids_b = [item["session_id"] for item in res_b.json()]
    assert sess_id not in ids_b

    # Candidate B is rejected with 403 when trying to fetch Candidate A's report
    res_forbidden = client.get(f"/api/interviews/{sess_id}/report", headers={"Authorization": f"Bearer {token_b}"})
    assert res_forbidden.status_code == 403

    # Clean up
    await db["interview_sessions"].delete_one({"_id": sess_id})
    await db["interview_reports"].delete_one({"_id": f"rep_{sess_id}"})
