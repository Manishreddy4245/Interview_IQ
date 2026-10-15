import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.resume import (
    AIRawSkillGapOutput,
    PersonalizedQuestionItem,
    ResumeAnalysisResult,
    SkillEvidenceCategory,
)
from app.services.skill_gap_service import (
    _normalize_ai_response_dict,
    analyze_resume_and_gaps,
)

client = TestClient(app)

MOCK_VALID_RAW_RESPONSE = {
    "target_role_benchmark": {
        "target_role": "Senior Backend Engineer",
        "experience_level": "Senior",
        "expected_competencies": [
            {
                "skill_name": "Python",
                "importance": "Core",
                "description": "Backend API design and async services.",
            },
            {
                "skill_name": "PostgreSQL",
                "importance": "Core",
                "description": "Relational schema design and indexing.",
            },
        ],
    },
    "extracted_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "projects_and_experience": ["Engineered distributed payment service handling high volume."],
    "skill_evaluations": [
        {
            "skill_name": "Python",
            "category": "Demonstrated in resume",
            "evidence": "Engineered distributed payment service using Python and FastAPI.",
            "relevance_to_role": "Core backend language for Senior Backend Engineer.",
        },
        {
            "skill_name": "Docker",
            "category": "Mentioned but insufficiently evidenced",
            "evidence": "Mentioned under technical tools without deployment depth.",
            "relevance_to_role": "Standard container orchestration skill.",
        },
    ],
    "personalized_questions": [
        {
            "id": "q_1",
            "question_number": 1,
            "text": "How did you manage connection pooling and async migrations in your FastAPI and PostgreSQL architecture?",
            "assessed_skill": "PostgreSQL",
            "difficulty": "Medium",
            "rubric": "Discusses asyncpg, pool sizing, and Alembic migrations under load.",
            "rationale": "Directly probes candidate PostgreSQL experience from payment service.",
        },
        {
            "id": "q_2",
            "question_number": 2,
            "text": "Can you describe how you configure and optimize Docker multi-stage builds for production microservices?",
            "assessed_skill": "Docker",
            "difficulty": "Medium",
            "rubric": "Explains base image selection, layer caching, and non-root execution.",
            "rationale": "Probes Docker competency which was only briefly listed in skills.",
        },
    ],
    "role_readiness_summary": "Strong alignment in Python backend development with actionable opportunities in containerization.",
}


# ---------------------------------------------------------------------------
# Test 1: Valid response containing personalized_questions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_valid_response_with_personalized_questions():
    """Verify that a response containing personalized_questions is validated and parsed directly."""
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(MOCK_VALID_RAW_RESPONSE)
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        result = await analyze_resume_and_gaps(
            resume_text="Senior Python and FastAPI Developer with PostgreSQL and Docker experience.",
            target_role="Senior Backend Engineer",
            experience_level="Senior",
        )

        assert isinstance(result, AIRawSkillGapOutput)
        assert len(result.personalized_questions) == 2
        assert result.personalized_questions[0].id == "q_1"
        assert result.personalized_questions[0].assessed_skill == "PostgreSQL"
        assert result.personalized_questions[0].difficulty == "Medium"
        assert len(result.extracted_skills) >= 2


# ---------------------------------------------------------------------------
# Test 2: Response missing personalized_questions (Normalized or via Alias)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_response_missing_personalized_questions_with_alias():
    """Verify that alias keys such as 'questions' or 'interview_questions' are normalized cleanly."""
    alias_raw_response = {
        "target_role_benchmark": None,
        "skills": ["Python", "Docker"],
        "projects": ["Built API microservices"],
        "evaluations": [
            {
                "skill_name": "Python",
                "category": "Demonstrated in resume",
                "evidence": "Built API microservices in Python",
                "relevance_to_role": "Core language",
            }
        ],
        # Alias 'questions' instead of 'personalized_questions'
        "questions": [
            {
                "id": "q_1",
                "question_number": 1,
                "text": "How did you design async request handlers in your Python microservices?",
                "assessed_skill": "Python",
                "difficulty": "Medium",
                "rubric": "Discusses event loop and concurrency control.",
                "rationale": "Directly probes candidate Python background.",
            }
        ],
        "summary": "Solid backend alignment.",
    }

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(alias_raw_response)
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        result = await analyze_resume_and_gaps(
            resume_text="Python developer with microservices background.",
            target_role="Backend Engineer",
            experience_level="Mid-Level",
        )

        assert len(result.personalized_questions) == 1
        assert result.personalized_questions[0].assessed_skill == "Python"
        assert result.role_readiness_summary == "Solid backend alignment."


# ---------------------------------------------------------------------------
# Test 3: Malformed JSON or invalid field type
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_malformed_json_response_handling():
    """Verify that completely malformed JSON raises HTTP 502 with a clean error detail."""
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "INVALID_JSON_NOT_AN_OBJECT{incomplete"
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        with pytest.raises(HTTPException) as exc_info:
            await analyze_resume_and_gaps(
                resume_text="Sample resume text",
                target_role="Backend Engineer",
            )

        assert exc_info.value.status_code == 502
        assert "invalid JSON" in exc_info.value.detail


@pytest.mark.asyncio
async def test_invalid_field_type_response_handling():
    """Verify that invalid field types (e.g. non-object root or unparseable evaluations) fail cleanly."""
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps("A simple string instead of JSON object")
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        with pytest.raises(HTTPException) as exc_info:
            await analyze_resume_and_gaps(
                resume_text="Sample resume text",
                target_role="Backend Engineer",
            )

        assert exc_info.value.status_code == 502
        assert "invalid JSON" in exc_info.value.detail or "schema" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Test 4: Successful controlled regeneration
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_successful_controlled_regeneration_when_field_omitted():
    """
    Verify that when the first pass completely omits personalized_questions,
    a single controlled regeneration call is performed to retrieve the questions.
    """
    first_pass_response = {
        "target_role_benchmark": None,
        "extracted_skills": ["Python", "FastAPI", "PostgreSQL"],
        "projects_and_experience": ["Led development of payment processing engine."],
        "skill_evaluations": [
            {
                "skill_name": "Python",
                "category": "Demonstrated in resume",
                "evidence": "Led development of payment processing engine in Python.",
                "relevance_to_role": "Core language",
            }
        ],
        # personalized_questions is COMPLETELY OMITTED in first pass
        "role_readiness_summary": "Extensive experience in backend development.",
    }

    regen_response = {
        "personalized_questions": [
            {
                "id": "q_regen_1",
                "question_number": 1,
                "text": "How did you ensure transactional consistency in the payment processing engine?",
                "assessed_skill": "PostgreSQL",
                "difficulty": "Hard",
                "rubric": "Explains ACID guarantees, transaction isolation levels, and idempotency.",
                "rationale": "Directly probes candidate payment engine architecture.",
            }
        ]
    }

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        mock_comp = MagicMock()
        mock_c = MagicMock()
        if call_count == 1:
            mock_c.message.content = json.dumps(first_pass_response)
        else:
            mock_c.message.content = json.dumps(regen_response)
        mock_comp.choices = [mock_c]
        return mock_comp

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        result = await analyze_resume_and_gaps(
            resume_text="Led development of payment processing engine in Python and PostgreSQL.",
            target_role="Backend Architect",
            experience_level="Senior",
        )

        assert call_count == 2, "Expected exactly 1 first pass + 1 controlled regeneration attempt"
        assert len(result.personalized_questions) == 1
        assert result.personalized_questions[0].assessed_skill == "PostgreSQL"
        assert "transactional consistency" in result.personalized_questions[0].text


# ---------------------------------------------------------------------------
# Test 5: Repeated invalid responses and safe error handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_repeated_omitted_questions_handles_safely():
    """
    Verify that when both first pass and regeneration omit personalized_questions,
    the pipeline normalizes the field safely to [] without fabricating content.
    """
    first_pass_response = {
        "target_role_benchmark": None,
        "extracted_skills": ["Python"],
        "projects_and_experience": ["Software engineering background."],
        "skill_evaluations": [],
        # personalized_questions is completely omitted
    }

    # Regeneration also returns empty object or fails to provide questions
    regen_response = {
        "personalized_questions": []
    }

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        mock_comp = MagicMock()
        mock_c = MagicMock()
        if call_count == 1:
            mock_c.message.content = json.dumps(first_pass_response)
        else:
            mock_c.message.content = json.dumps(regen_response)
        mock_comp.choices = [mock_c]
        return mock_comp

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        result = await analyze_resume_and_gaps(
            resume_text="Software engineering background with Python.",
            target_role="Software Engineer",
            experience_level="Mid-Level",
        )

        assert call_count == 2
        # Missing field normalized safely to []
        assert result.personalized_questions == []
        assert "Python" in result.extracted_skills


# ---------------------------------------------------------------------------
# Test 6: Complete resume upload and skill-gap analysis flow
# ---------------------------------------------------------------------------
def test_complete_resume_upload_and_skill_gap_analysis_flow():
    """Verify the full HTTP multipart upload endpoint executes successfully and returns valid result."""
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(MOCK_VALID_RAW_RESPONSE)
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test_mock_key"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client), \
         patch("app.routers.resume.extract_text_from_pdf_upload", AsyncMock(return_value="Extracted PDF text for testing.")):

        response = client.post(
            "/api/resume/analyze",
            files={"file": ("resume.pdf", dummy_pdf, "application/pdf")},
            data={"target_role": "Senior Backend Engineer", "experience_level": "Senior"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data
        assert data["target_role"] == "Senior Backend Engineer"
        assert len(data["personalized_questions"]) == 2
        assert data["personalized_questions"][0]["assessed_skill"] == "PostgreSQL"
        assert len(data["extracted_skills"]) >= 2
