import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.decision import DecisionOverviewResponse, CandidateDossierItem
from app.schemas.resume import (
    AIRawSkillGapOutput,
    SkillEvidenceCategory,
    SkillEvidenceItem,
    PersonalizedQuestionItem,
)
from app.services.resume_service import store_resume_analysis, _in_memory_analyses
from app.core.security import create_access_token, ROLE_REVIEWER

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token(user_id='usr_rev_01', role=ROLE_REVIEWER, name='Senior Engineering Manager')}"


@pytest.fixture(autouse=True)
def seed_in_memory_analysis():
    """Ensure in-memory store has a verified candidate record during isolated tests."""
    async def _populate():
        raw_ai = AIRawSkillGapOutput(
            extracted_skills=["React", "TypeScript", "State Management"],
            projects_and_experience=["HostelCare AI project using React"],
            skill_evaluations=[
                SkillEvidenceItem(
                    skill_name="React",
                    category=SkillEvidenceCategory.DEMONSTRATED,
                    evidence="Built responsive frontend components.",
                    relevance_to_role="Core library.",
                ),
                SkillEvidenceItem(
                    skill_name="State Management",
                    category=SkillEvidenceCategory.NOT_DEMONSTRATED,
                    evidence="No Redux or Zustand evidenced in resume.",
                    relevance_to_role="Essential for mid-level.",
                ),
            ],
            personalized_questions=[
                PersonalizedQuestionItem(
                    id="q_1",
                    question_number=1,
                    text="Explain React component state management.",
                    assessed_skill="React",
                    difficulty="Medium",
                    rubric="Covers useState and context.",
                    rationale="Validates core skill.",
                )
            ],
            role_readiness_summary="Promising frontend candidate with state management gaps.",
        )
        return await store_resume_analysis(
            target_role="Frontend Specialist",
            experience_level="Mid-Level",
            ai_output=raw_ai,
        )

    asyncio.run(_populate())
    yield
    _in_memory_analyses.clear()


def test_decision_overview_endpoint():
    """Verify GET /api/decision/overview returns valid schema with dossiers from active store."""
    response = client.get("/api/decision/overview")
    assert response.status_code == 200
    data = response.json()
    validated = DecisionOverviewResponse(**data)
    assert validated.total_records >= 1
    assert len(validated.dossiers) == validated.total_records


def test_decision_dossier_detail_and_reviews():
    """Verify detailed dossier retrieval and human reviewer decision appending."""
    overview_resp = client.get("/api/decision/overview")
    assert overview_resp.status_code == 200
    overview_data = overview_resp.json()
    assert len(overview_data["dossiers"]) > 0

    first_dossier = overview_data["dossiers"][0]
    record_id = first_dossier["record_id"]

    # 1. Fetch detail
    detail_resp = client.get(f"/api/decision/dossier/{record_id}")
    assert detail_resp.status_code == 200
    dossier = CandidateDossierItem(**detail_resp.json())
    assert dossier.record_id == record_id
    assert dossier.target_role == "Frontend Specialist"
    assert len(dossier.demonstrated_competencies) >= 1
    assert len(dossier.competency_gaps) >= 1

    # 2. Append a human review decision
    review_payload = {
        "reviewer_name": "Senior Engineering Manager",
        "recommendation": "Advance to Technical Screen",
        "notes": "Verified candidate projects and core demonstrated skills.",
    }
    review_resp = client.post(f"/api/decision/dossier/{record_id}/review", json=review_payload)
    assert review_resp.status_code == 201
    rev_data = review_resp.json()
    assert rev_data["reviewer_name"] == "Senior Engineering Manager"
    assert rev_data["recommendation"] == "Advance to Technical Screen"
    assert "decision_id" in rev_data

    # 3. Fetch detail again to ensure review was attached
    detail_resp2 = client.get(f"/api/decision/dossier/{record_id}")
    assert detail_resp2.status_code == 200
    dossier2 = CandidateDossierItem(**detail_resp2.json())
    assert len(dossier2.human_reviews) >= 1
    assert any(r.reviewer_name == "Senior Engineering Manager" for r in dossier2.human_reviews)


def test_decision_dossier_not_found():
    """Verify 404 for unknown record ID."""
    response = client.get("/api/decision/dossier/non-existent-record-uuid")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
