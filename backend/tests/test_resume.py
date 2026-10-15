import io
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.main import app
from app.core.config import settings

client = TestClient(app)


def create_dummy_pdf_bytes(text: str) -> bytes:
    """Helper to generate a valid PDF byte string containing text."""
    writer = PdfWriter()
    # Add a blank page with text annotation or metadata
    page = writer.add_blank_page(width=612, height=792)
    # Write stream
    buffer = io.BytesIO()
    writer.write(buffer)
    # The default blank page might not have extractable text via page.extract_text(),
    # so we mock extract_text_from_pdf_upload or inject actual text streams.
    buffer.seek(0)
    return buffer.getvalue()


MOCK_SKILL_GAP_RESPONSE = {
    "extracted_skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
    "projects_and_experience": [
        "Backend microservices architecture at Acme Corp",
        "High-performance query optimization",
    ],
    "skill_evaluations": [
        {
            "skill_name": "Python",
            "category": "Demonstrated in resume",
            "evidence": "4 years developing backend services with high test coverage.",
            "relevance_to_role": "Core language for backend development.",
        },
        {
            "skill_name": "Docker",
            "category": "Mentioned but insufficiently evidenced",
            "evidence": "Listed in skills section without container orchestration project details.",
            "relevance_to_role": "Required for application containerization.",
        },
        {
            "skill_name": "Kubernetes",
            "category": "Not demonstrated in resume",
            "evidence": "Not mentioned anywhere in the resume text.",
            "relevance_to_role": "Standard orchestration expectation for Senior roles.",
        },
        {
            "skill_name": "Distributed Systems",
            "category": "Requires interview validation",
            "evidence": "Mentions microservices but does not specify consistency or fault-tolerance mechanisms.",
            "relevance_to_role": "Critical for scalable system design.",
        },
    ],
    "personalized_questions": [
        {
            "id": "q_1",
            "question_number": 1,
            "text": "How did you manage database connection pooling and migrations in your FastAPI services?",
            "assessed_skill": "FastAPI & PostgreSQL",
            "difficulty": "Medium",
            "rubric": "Mentions async engine setup, Alembic migrations, and connection pool sizing.",
            "rationale": "Directly probes the candidate's reported FastAPI and database backend project.",
        },
        {
            "id": "q_2",
            "question_number": 2,
            "text": "Can you describe a scenario where you troubleshot a container crash or networking issue with Docker?",
            "assessed_skill": "Docker",
            "difficulty": "Medium",
            "rubric": "Explains container lifecycle, logs inspection, and network bridge debugging.",
            "rationale": "Validates Docker capability which was only briefly mentioned in the resume.",
        },
        {
            "id": "q_3",
            "question_number": 3,
            "text": "How do you handle service discovery and inter-service communication across microservices?",
            "assessed_skill": "Distributed Systems",
            "difficulty": "Hard",
            "rubric": "Discusses gRPC, REST, message brokers, and circuit breakers.",
            "rationale": "Explores the ambiguous distributed systems claim from the candidate's background.",
        },
    ],
    "role_readiness_summary": "Strong foundational alignment in Python backend development with actionable interview opportunities in container orchestration and system architecture.",
}


def test_reject_non_pdf_file():
    """Verify that uploading a non-PDF file returns HTTP 400."""
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("resume.txt", b"This is plain text", "text/plain")},
        data={"target_role": "Backend Engineer", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_reject_empty_file():
    """Verify that an empty 0-byte file returns HTTP 400."""
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("resume.pdf", b"", "application/pdf")},
        data={"target_role": "Backend Engineer", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_reject_corrupted_pdf_header():
    """Verify that a file lacking %PDF- magic bytes returns HTTP 400."""
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("fake.pdf", b"NOT_A_PDF_STREAM", "application/pdf")},
        data={"target_role": "Backend Engineer", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 400
    assert "magic header" in response.json()["detail"].lower()


def test_reject_invalid_target_role():
    """Verify that an empty or single-character target role returns HTTP 422."""
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("resume.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        data={"target_role": " ", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 422


@patch("app.routers.resume.extract_text_from_pdf_upload")
@patch("app.core.config.settings.GROQ_API_KEY", None)
def test_missing_groq_key_returns_503(mock_extract):
    """Verify that missing GROQ_API_KEY returns HTTP 503."""
    mock_extract.return_value = "Valid resume text with more than fifty characters of candidate background and work experience."
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("resume.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        data={"target_role": "Backend Engineer", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 503
    assert "Groq API key is not configured" in response.json()["detail"]


@patch("app.routers.resume.extract_text_from_pdf_upload")
@patch("app.core.groq_client.groq_manager.get_client")
@patch("app.core.config.settings.GROQ_API_KEY", "gsk_mock_valid_key_12345")
def test_successful_resume_analysis(mock_get_client, mock_extract):
    """Verify successful PDF text extraction and skill-gap analysis."""
    mock_extract.return_value = (
        "John Doe, Backend Developer with 4 years in Python, FastAPI, Docker, and PostgreSQL."
    )

    # Mock Groq completion
    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(MOCK_SKILL_GAP_RESPONSE)
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    mock_get_client.return_value = mock_client

    response = client.post(
        "/api/resume/analyze",
        files={"file": ("resume.pdf", b"%PDF-1.4 dummy content", "application/pdf")},
        data={"target_role": "Senior Backend Engineer", "experience_level": "Senior"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "analysis_id" in data
    assert data["target_role"] == "Senior Backend Engineer"
    assert data["experience_level"] == "Senior"
    assert len(data["extracted_skills"]) == 4
    assert len(data["skill_evaluations"]) == 4
    assert len(data["personalized_questions"]) == 3
    assert data["saved_to_db"] is False
    assert data["db_status"] == "unconfigured"

    # Verify 4 required categories are present
    categories = [item["category"] for item in data["skill_evaluations"]]
    assert "Demonstrated in resume" in categories
    assert "Mentioned but insufficiently evidenced" in categories
    assert "Not demonstrated in resume" in categories
    assert "Requires interview validation" in categories

    analysis_id = data["analysis_id"]

    # Verify retrieval endpoint
    get_res = client.get(f"/api/resume/{analysis_id}")
    assert get_res.status_code == 200
    assert get_res.json()["analysis_id"] == analysis_id

    # Verify starting an interview session from this analysis
    start_res = client.post(f"/api/resume/{analysis_id}/start-interview")
    assert start_res.status_code == 201
    start_data = start_res.json()
    assert "session_id" in start_data
    assert len(start_data["questions"]) == 3
    assert start_data["questions"][0]["text"] == MOCK_SKILL_GAP_RESPONSE["personalized_questions"][0]["text"]


def test_get_non_existent_analysis():
    """Verify that querying an unknown analysis ID returns HTTP 404."""
    response = client.get("/api/resume/non-existent-uuid")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_start_interview_non_existent_analysis():
    """Verify that starting interview for an unknown analysis ID returns HTTP 404."""
    response = client.post("/api/resume/non-existent-uuid/start-interview")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
