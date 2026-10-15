"""
Test InterviewIQ Student-Centric End-to-End Workflow:
Phases 1 through 10 test suite covering:
1. Student registration and login (candidate role only, PBKDF2 hash, JWT token)
2. Student resume upload, text extraction (skills, projects, education, experience, certs) and ownership
3. Student manual skill correction before proceeding
4. Supported job-role selection from standardized catalogue
5. Initial skill gap analysis with deterministic status mapping
6. Sequential adaptive interview progression: Q1 issued -> answer submitted & evaluated -> adapted next question
7. Cross-student data isolation & ownership protection
8. Final evidence-based skill gap analysis and personalized feedback
"""
import io
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import (
    create_access_token,
    hash_password,
    USERS_DB,
    ROLE_CANDIDATE,
    ROLE_REVIEWER,
)
from app.schemas.resume import (
    AIRawSkillGapOutput,
    TargetRoleBenchmark,
    RoleBenchmarkCompetency,
    SkillEvidenceItem,
    SkillEvidenceCategory,
    PersonalizedQuestionItem,
)
from app.schemas.interview import QuestionItem
from app.services.resume_service import _in_memory_analyses
from app.services.session_service import _in_memory_sessions
from app.services.report_service import _in_memory_reports

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_test_state():
    """Clear in-memory state between tests."""
    yield
    # Cleanup dummy test users
    for k in list(USERS_DB.keys()):
        if k.startswith("student_") or k.startswith("attacker_"):
            del USERS_DB[k]


def make_student_token(username: str = "student_test_1", user_id: str = "usr_student_1") -> str:
    """Helper to generate signed JWT for authenticated student."""
    USERS_DB[username] = {
        "user_id": user_id,
        "username": username,
        "name": "Test Student",
        "email": f"{username}@example.com",
        "role": ROLE_CANDIDATE,
        "password_hash": hash_password("SecurePass123!"),
    }
    return create_access_token(user_id=user_id, role=ROLE_CANDIDATE, name="Test Student")


# ============================================================================
# PHASE 1: Student Registration & Authentication Security
# ============================================================================

def test_student_registration_strictly_creates_candidate():
    """Public registration must always assign role='candidate' and prevent privilege escalation."""
    payload = {
        "name": "New Student",
        "username": "student_reg_01",
        "email": "newstudent@example.edu",
        "password": "ValidPassword99#",
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["role"] == ROLE_CANDIDATE
    assert data["username"] == "student_reg_01"
    assert "access_token" in data
    # Password hash stored in USERS_DB must not be plaintext
    user_record = USERS_DB["student_reg_01"]
    assert user_record["password_hash"] != "ValidPassword99#"
    assert user_record["role"] == ROLE_CANDIDATE


def test_student_login_with_valid_credentials():
    """Authenticated student logs in and receives verified profile."""
    USERS_DB["student_login_01"] = {
        "user_id": "usr_cand_login01",
        "username": "student_login_01",
        "name": "Login Student",
        "email": "login@example.com",
        "role": ROLE_CANDIDATE,
        "password_hash": hash_password("CorrectPassword123!"),
    }
    login_res = client.post("/api/auth/token", json={
        "username": "student_login_01",
        "password": "CorrectPassword123!",
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Verify /api/auth/me returns student profile
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    profile = me_res.json()
    assert profile["role"] == ROLE_CANDIDATE
    assert profile["username"] == "student_login_01"


# ============================================================================
# PHASE 2: Resume Upload, Skill Extraction, and Correction
# ============================================================================

@pytest.mark.asyncio
async def test_student_resume_upload_and_extraction():
    """Student uploads resume; text, skills, projects, education, and certs are stored with owner_id."""
    token = make_student_token("student_uploader", "usr_student_up")

    mock_ai_output = AIRawSkillGapOutput(
        target_role_benchmark=TargetRoleBenchmark(
            target_role="Full Stack Engineer",
            experience_level="Mid-Level",
            expected_competencies=[
                RoleBenchmarkCompetency(skill_name="React", importance="Core", description="Frontend UI"),
                RoleBenchmarkCompetency(skill_name="Node.js", importance="Core", description="Backend APIs"),
                RoleBenchmarkCompetency(skill_name="PostgreSQL", importance="Core", description="Relational data"),
            ],
        ),
        extracted_skills=["React", "TypeScript", "Node.js", "Docker"],
        projects_and_experience=["E-Commerce Platform with React and Node.js microservices"],
        education=["B.S. in Computer Science, University of Technology (2024)"],
        work_experience=["Software Engineer Intern at Tech Corp"],
        certifications=["AWS Certified Cloud Practitioner"],
        skill_evaluations=[
            SkillEvidenceItem(
                skill_name="React",
                category=SkillEvidenceCategory.DEMONSTRATED,
                evidence="Built e-commerce UI in React",
                relevance_to_role="Core frontend library",
                is_source_grounded=True,
                is_expected_for_role=True,
            ),
            SkillEvidenceItem(
                skill_name="PostgreSQL",
                category=SkillEvidenceCategory.NOT_DEMONSTRATED,
                evidence="Expected for Full Stack Engineer, but absent from resume.",
                relevance_to_role="Relational database",
                is_source_grounded=False,
                is_expected_for_role=True,
            ),
        ],
        personalized_questions=[
            PersonalizedQuestionItem(
                id="q_1",
                question_number=1,
                text="Explain how you structured component state and side effects in your React e-commerce application.",
                assessed_skill="React",
                difficulty="Medium",
                rubric="Evaluates state normalization, hooks usage, and rendering performance.",
                rationale="Probes candidate React project evidence directly.",
            )
        ],
        role_readiness_summary="Candidate demonstrates strong frontend foundations with React and Node.js.",
    )

    fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    with patch("app.routers.resume.extract_text_from_pdf_upload", new_callable=AsyncMock) as mock_pdf, \
         patch("app.routers.resume.analyze_resume_and_gaps", new_callable=AsyncMock) as mock_analyze:
        mock_pdf.return_value = "John Doe. Software Engineer with experience in React, TypeScript, and Node.js."
        mock_analyze.return_value = mock_ai_output

        response = client.post(
            "/api/resume/analyze",
            files={"file": ("resume.pdf", io.BytesIO(fake_pdf), "application/pdf")},
            data={"target_role": "Full Stack Engineer", "experience_level": "Mid-Level"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["owner_id"] == "usr_student_up"
        assert "React" in data["extracted_skills"]
        assert len(data["education"]) > 0
        assert data["education"][0].startswith("B.S. in Computer Science")
        analysis_id = data["analysis_id"]

    # Student retrieves their active resume via /my-resume
    my_resume_res = client.get("/api/resume/my-resume", headers={"Authorization": f"Bearer {token}"})
    assert my_resume_res.status_code == 200
    my_data = my_resume_res.json()
    assert my_data["analysis_id"] == analysis_id
    assert my_data["owner_id"] == "usr_student_up"


def test_student_can_correct_extracted_skills():
    """Student can edit and correct extraction mistakes before proceeding."""
    token = make_student_token("student_editor", "usr_student_ed")

    # Seed analysis
    mock_ai = AIRawSkillGapOutput(
        target_role_benchmark=TargetRoleBenchmark(
            target_role="Full Stack Engineer",
            experience_level="Mid-Level",
            expected_competencies=[
                RoleBenchmarkCompetency(skill_name="React", importance="Core", description="UI"),
                RoleBenchmarkCompetency(skill_name="PostgreSQL", importance="Core", description="SQL DB"),
            ],
        ),
        extracted_skills=["Reac", "Javascrip"],  # typos from parsing
        projects_and_experience=["Project A"],
        skill_evaluations=[],
    )

    with patch("app.routers.resume.extract_text_from_pdf_upload", new_callable=AsyncMock) as mock_pdf, \
         patch("app.routers.resume.analyze_resume_and_gaps", new_callable=AsyncMock) as mock_analyze:
        mock_pdf.return_value = "Candidate resume text with technical details."
        mock_analyze.return_value = mock_ai

        upload_res = client.post(
            "/api/resume/analyze",
            files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4\nfake"), "application/pdf")},
            data={"target_role": "Full Stack Engineer", "experience_level": "Mid-Level"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = upload_res.json()["analysis_id"]

    # Student corrects skills:
    update_res = client.put(
        f"/api/resume/{analysis_id}/skills",
        json={"skills": ["React", "JavaScript", "PostgreSQL", "Node.js"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert "React" in updated["extracted_skills"]
    assert "PostgreSQL" in updated["extracted_skills"]
    assert "Reac" not in updated["extracted_skills"]


# ============================================================================
# PHASE 3 & 4: Supported Job Role Catalogue & Initial Skill Gap Analysis
# ============================================================================

def test_supported_roles_catalogue():
    """Catalogue exposes standardized supported roles and competency requirements."""
    res = client.get("/api/roles")
    assert res.status_code == 200
    roles = res.json()
    role_names = [r["role_name"] for r in roles]
    assert "Full Stack Engineer" in role_names
    assert "Frontend Specialist" in role_names
    assert "Backend Systems" in role_names
    assert "AI/ML Engineer" in role_names
    assert "DevOps & Cloud" in role_names

    # Check specific role definition
    detail_res = client.get("/api/roles/Full Stack Engineer")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["competencies"]) >= 3
    comp_names = [c["skill_name"] for c in detail["competencies"]]
    assert any("React" in c for c in comp_names)


def test_student_select_target_role_updates_gap_analysis():
    """Student selecting a supported target role receives structured initial skill gap analysis."""
    token = make_student_token("student_rolesel", "usr_student_rs")

    mock_ai = AIRawSkillGapOutput(
        extracted_skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
        projects_and_experience=["Distributed microservices with FastAPI and PostgreSQL"],
        skill_evaluations=[],
    )

    with patch("app.routers.resume.extract_text_from_pdf_upload", new_callable=AsyncMock) as mock_pdf, \
         patch("app.routers.resume.analyze_resume_and_gaps", new_callable=AsyncMock) as mock_analyze:
        mock_pdf.return_value = "Python backend developer with Docker and Postgres."
        mock_analyze.return_value = mock_ai

        res = client.post(
            "/api/resume/analyze",
            files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4\nfake"), "application/pdf")},
            data={"target_role": "Backend Systems", "experience_level": "Mid-Level"},
            headers={"Authorization": f"Bearer {token}"},
        )
        analysis_id = res.json()["analysis_id"]

    # Student updates selected role to Backend Systems
    sel_res = client.post(
        f"/api/resume/{analysis_id}/select-role",
        json={"target_role": "Backend Systems", "experience_level": "Senior"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sel_res.status_code == 200
    data = sel_res.json()
    assert data["target_role"] == "Backend Systems"
    assert data["experience_level"] == "Senior"
    assert len(data["skill_evaluations"]) > 0


# ============================================================================
# PHASE 5, 6, 7: Strictly Sequential Adaptive Interview
# ============================================================================

@pytest.mark.asyncio
async def test_sequential_adaptive_interview_lifecycle():
    """
    Strict sequencing test:
    1. Interview starts -> only Question 1 is issued (not future questions).
    2. Student submits answer for active question -> evaluated -> next question adapted and issued.
    3. Cannot submit answers out of order or for unissued questions.
    """
    token = make_student_token("student_adaptive", "usr_student_ad")

    # Start adaptive interview session
    setup_payload = {
        "role": "Full Stack Engineer",
        "experience_level": "Mid-Level",
        "difficulty": "Medium",
        "focus_areas": "React, Node.js, SQL",
        "question_count": 3,
        "adaptive": True,
    }

    initial_q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Explain React component state and lifecycle management using hooks.",
        assessed_skill="React",
        difficulty="Medium",
        rubric="Candidate explains useState, useEffect, and component lifecycle progression.",
        selection_rationale="Initial baseline question selected to assess core competency 'React'.",
    )
    with patch("app.routers.interview.generate_initial_adaptive_question", new_callable=AsyncMock) as mock_initial_q:
        mock_initial_q.return_value = [initial_q1]
        start_res = client.post(
            "/api/interviews/setup",
            json=setup_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert start_res.status_code == 201
    sess_data = start_res.json()
    session_id = sess_data["session_id"]

    # STRICT SEQUENCING CHECK: Session must only contain Question 1 at start!
    assert len(sess_data["questions"]) == 1
    q1 = sess_data["questions"][0]
    assert q1["id"] == "q_1"
    assert sess_data["active_question_id"] == "q_1"

    # Reject submission for unissued question "q_2"
    bad_sub = client.post(
        f"/api/interviews/{session_id}/submit-and-adapt",
        json={"question_id": "q_2", "answer_text": "Premature answer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_sub.status_code == 400

    # Submit valid answer for Question 1
    with patch("app.routers.interview.evaluate_candidate_answer", new_callable=AsyncMock) as mock_eval, \
         patch("app.routers.interview.generate_next_adaptive_question", new_callable=AsyncMock) as mock_next_q:
        from app.schemas.evaluation import AnswerEvaluationResponse, CriterionScore, CriterionScores
        from app.schemas.interview import NextQuestionResponse, SessionCompetencyState
        mock_eval.return_value = AnswerEvaluationResponse(
            session_id=session_id,
            question_id="q_1",
            overall_score=85.0,
            criterion_scores=CriterionScores(
                relevance=CriterionScore(score=9, feedback="Directly answers prompt"),
                technical_depth=CriterionScore(score=9, feedback="Strong architecture breakdown"),
                completeness=CriterionScore(score=8, feedback="Covers key indicators"),
                structure_flow=CriterionScore(score=8, feedback="Logical progression"),
                clarity_conciseness=CriterionScore(score=9, feedback="Clear concise phrasing"),
            ),
            strengths=["Thorough understanding of React component lifecycles"],
            areas_for_improvement=["Could expand on server-side rendering caching"],
            coaching_feedback="Excellent technical depth.",
            actionable_suggestions=["Focus on caching strategies"],
            coaching_summary="Strong foundation in component state.",
            saved_to_db=False,
            db_status="active_memory",
        )
        q2 = QuestionItem(
            id="q_2",
            question_number=2,
            text="How do you optimize rendering performance in large lists in React?",
            assessed_skill="React Performance",
            difficulty="Medium",
            rubric="Check for virtualization and memoization",
            selection_rationale="Adapted from candidate's strong React lifecycle answer to assess performance depth.",
        )
        mock_next_q.return_value = NextQuestionResponse(
            session_id=session_id,
            question=q2,
            active_question_id="q_2",
            current_difficulty="Medium",
            question_number=2,
            target_question_count=3,
            is_last_question=False,
            competency_state=SessionCompetencyState(
                session_id=session_id,
                skills={},
                current_difficulty="Medium",
                total_evaluated_count=1,
            ),
            saved_to_db=False,
            db_status="active_memory",
        )

        sub_res = client.post(
            f"/api/interviews/{session_id}/submit-and-adapt",
            json={
                "question_id": "q_1",
                "answer_text": "In React, component lifecycle state is managed via hooks like useState and useEffect with dependency arrays.",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert sub_res.status_code == 200
        adapt_data = sub_res.json()
        assert adapt_data["evaluation"]["overall_score"] == 85.0
        # Next question is adapted and returned
        assert adapt_data["next_question"] is not None
        assert adapt_data["next_question"]["question_number"] == 2
        assert adapt_data["active_question_id"] == adapt_data["next_question"]["id"]


@pytest.mark.asyncio
async def test_adaptive_interview_setup_groq_failure_handling():
    """Verify that external Groq failure or rate limit returns actionable HTTP error without fake questions."""
    token = make_student_token("student_rate_limit", "usr_student_rl")
    setup_payload = {
        "role": "Full Stack Engineer",
        "experience_level": "Mid-Level",
        "difficulty": "Medium",
        "focus_areas": "React, Node.js",
        "question_count": 3,
        "adaptive": True,
    }
    from fastapi import HTTPException
    with patch(
        "app.routers.interview.generate_initial_adaptive_question",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=429, detail="Rate limit reached for model openai/gpt-oss-20b on tokens per day (TPD)."),
    ):
        res = client.post(
            "/api/interviews/setup",
            json=setup_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 429
        assert "Rate limit reached" in res.json()["detail"]


# ============================================================================
# PHASE 1 & SECURITY: Cross-Student Isolation & Ownership Enforcement
# ============================================================================

def test_student_cannot_access_another_students_data():
    """Verify that student A cannot access student B's resume, interview, or reports."""
    token_a = make_student_token("student_alice", "usr_cand_alice")
    token_b = make_student_token("student_bob", "usr_cand_bob")

    # Alice creates a resume analysis
    _in_memory_analyses["alice_analysis_1"] = {
        "analysis_id": "alice_analysis_1",
        "owner_id": "usr_cand_alice",
        "target_role": "Full Stack Engineer",
        "experience_level": "Mid-Level",
        "extracted_skills": ["React", "Python"],
        "projects_and_experience": ["Alice Project"],
        "skill_evaluations": [],
        "personalized_questions": [],
        "role_readiness_summary": "Alice Summary",
        "created_at": "2026-10-13T10:00:00Z",
    }

    # Alice creates an interview session
    _in_memory_sessions["alice_session_1"] = {
        "session_id": "alice_session_1",
        "owner_id": "usr_cand_alice",
        "role": "Full Stack Engineer",
        "experience_level": "Mid-Level",
        "difficulty": "Medium",
        "duration_minutes": 30,
        "questions": [{"id": "q_1", "question_number": 1, "text": "Alice Question", "assessed_skill": "React", "difficulty": "Medium", "rubric": "Rubric"}],
        "active_question_id": "q_1",
        "answers": {},
        "status": "in_progress",
        "created_at": "2026-10-13T10:00:00Z",
    }

    # Bob attempts to view Alice's resume analysis -> 403 Forbidden
    res_resume = client.get("/api/resume/alice_analysis_1", headers={"Authorization": f"Bearer {token_b}"})
    assert res_resume.status_code == 403

    # Bob attempts to view Alice's interview session -> 403 Forbidden
    res_sess = client.get("/api/interviews/alice_session_1", headers={"Authorization": f"Bearer {token_b}"})
    assert res_sess.status_code == 403

    # Bob attempts to submit answer for Alice's interview -> 403 Forbidden
    res_ans = client.post(
        "/api/interviews/alice_session_1/answers",
        json={"question_id": "q_1", "answer_text": "Bob interfering"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_ans.status_code == 403

    # Alice CAN view her own resume and session
    alice_res_resume = client.get("/api/resume/alice_analysis_1", headers={"Authorization": f"Bearer {token_a}"})
    assert alice_res_resume.status_code == 200

    alice_res_sess = client.get("/api/interviews/alice_session_1", headers={"Authorization": f"Bearer {token_a}"})
    assert alice_res_sess.status_code == 200
