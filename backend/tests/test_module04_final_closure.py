"""
InterviewIQ - Module 04 Final Closure Test Suite:
Truncation Consistency, Boundary Enforcement & Synthetic PDF Tests.

Verifies:
1. Authoritative 12,000-character ceiling boundary behavior:
   - Text < 12,000 chars is not marked truncated.
   - Text == 12,000 chars follows documented ceiling (not truncated).
   - Text > 12,000 chars is deterministically truncated to 12,000 chars.
   - Analyzed text payload never exceeds the authoritative 12,000-char limit.
   - Truncation warning is attached to role readiness summary when truncated.
   - Repeated analysis yields consistent truncation metadata.
2. Synthetic PDF generation & upload validation:
   - Fictional, non-identifying in-memory synthetic PDF upload succeeds.
   - Corrupted PDF without %PDF- magic bytes fails with HTTP 400.
   - Empty file (0 bytes) fails with HTTP 400.
   - Non-PDF extension fails with HTTP 400.
3. Legacy records without truncation metadata deserialize with safe defaults.
"""
import io
import json
import uuid
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.resume import (
    ResumeAnalysisResult,
    SkillEvidenceCategory,
    SkillEvidenceItem,
)
from app.services.skill_gap_service import (
    MAX_RESUME_ANALYSIS_CHARS,
    analyze_resume_and_gaps,
)
from app.services.pdf_extractor import (
    extract_text_from_pdf_upload,
)
from app.services.resume_service import (
    _in_memory_analyses,
    get_resume_analysis,
    store_resume_analysis,
)

client = TestClient(app)


def build_synthetic_pdf_bytes(text_lines: List[str]) -> bytes:
    """
    Generates a valid, minimal, compliant PDF binary in-memory
    strictly for testing without any external PDF generation libraries.
    """
    stream_content = ["BT", "/F1 12 Tf", "72 720 Td"]
    first = True
    for line in text_lines:
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if first:
            stream_content.append(f"({safe_line}) Tj")
            first = False
        else:
            stream_content.append(f"T* ({safe_line}) Tj")
    stream_content.append("ET")
    stream_bytes = "\n".join(stream_content).encode("latin-1")

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")

    offsets = []

    def add_obj(obj_bytes: bytes):
        offsets.append(len(pdf))
        pdf.extend(obj_bytes)

    add_obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    add_obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    add_obj(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
    add_obj(f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1") + stream_bytes + b"\nendstream\nendobj\n")
    add_obj(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1"))
    return bytes(pdf)


@pytest.fixture(autouse=True)
def clean_memory_stores():
    _in_memory_analyses.clear()
    yield
    _in_memory_analyses.clear()


# ===========================================================================
# 1. Authoritative Truncation Boundary Tests (12,000 Chars)
# ===========================================================================

def test_authoritative_truncation_constant_is_12000():
    """Verify authoritative constant is strictly 12,000 characters."""
    assert MAX_RESUME_ANALYSIS_CHARS == 12000


@pytest.mark.asyncio
async def test_truncation_boundary_below_limit():
    """Text below 12,000 characters is not marked truncated."""
    text_below = "Senior Python engineer building microservices. " * 100  # ~4,700 chars
    assert len(text_below) < MAX_RESUME_ANALYSIS_CHARS

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "extracted_skills": ["Python"],
        "projects_and_experience": ["Building microservices"],
        "skill_evaluations": [],
        "personalized_questions": [],
        "role_readiness_summary": "Solid backend profile.",
    })
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        result = await analyze_resume_and_gaps(text_below, "Backend Engineer")
        assert result.is_truncated is False
        assert result.analyzed_character_count == len(text_below)
        assert "[Note: Resume exceeded 12,000 characters" not in result.role_readiness_summary


@pytest.mark.asyncio
async def test_truncation_boundary_exactly_at_limit():
    """Text exactly at 12,000 characters is not truncated."""
    filler = "A" * MAX_RESUME_ANALYSIS_CHARS
    assert len(filler) == 12000

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "extracted_skills": ["Python"],
        "projects_and_experience": ["Long resume profile"],
        "skill_evaluations": [],
        "personalized_questions": [],
        "role_readiness_summary": "Extensive profile.",
    })
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        result = await analyze_resume_and_gaps(filler, "Backend Engineer")
        assert result.is_truncated is False
        assert result.analyzed_character_count == 12000
        assert "[Note: Resume exceeded 12,000 characters" not in result.role_readiness_summary


@pytest.mark.asyncio
async def test_truncation_boundary_above_limit_is_deterministic():
    """Text above 12,000 characters is deterministically capped at 12,000 chars."""
    text_above = "B" * 15500  # 15,500 chars

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "extracted_skills": ["Docker", "Kubernetes"],
        "projects_and_experience": ["Oversized resume profile"],
        "skill_evaluations": [],
        "personalized_questions": [],
        "role_readiness_summary": "Large document analyzed.",
    })
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        result = await analyze_resume_and_gaps(text_above, "Cloud Engineer")
        assert result.is_truncated is True
        assert result.analyzed_character_count == 12000
        assert "[Note: Resume exceeded 12,000 characters" in result.role_readiness_summary

        # Verify LLM call prompt NEVER exceeded 12,000 characters of resume text
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_msg = call_kwargs["messages"][1]["content"]
        # Extract content inside <candidate_resume_document>
        start_tag = "<candidate_resume_document>\n"
        end_tag = "\n</candidate_resume_document>"
        assert start_tag in user_msg
        assert end_tag in user_msg
        doc_content = user_msg.split(start_tag)[1].split(end_tag)[0]
        assert len(doc_content) == 12000
        assert len(doc_content) <= MAX_RESUME_ANALYSIS_CHARS


@pytest.mark.asyncio
async def test_repeated_analysis_consistent_metadata():
    """Repeated analysis of identical oversized text yields identical truncation metadata."""
    oversized_text = "C" * 14000

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "extracted_skills": ["PostgreSQL"],
        "projects_and_experience": ["Database engineering"],
        "skill_evaluations": [],
        "personalized_questions": [],
        "role_readiness_summary": "DB engineer.",
    })
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        res1 = await analyze_resume_and_gaps(oversized_text, "Database Engineer")
        res2 = await analyze_resume_and_gaps(oversized_text, "Database Engineer")

        assert res1.is_truncated == res2.is_truncated == True
        assert res1.analyzed_character_count == res2.analyzed_character_count == 12000


# ===========================================================================
# 2. Synthetic PDF Fixture & Upload Tests
# ===========================================================================

def test_synthetic_pdf_generation_and_text_extraction():
    """Verify synthetic PDF fixture generates valid binary with extractable text."""
    lines = [
        "Alex Rivers - Senior Backend Engineer",
        "Technical Skills: Python, Docker, PostgreSQL, FastAPI, Redis",
        "Experience: 5 years designing high-throughput REST APIs and microservices.",
        "Built async order processing engine handling 5000 req/sec with Redis caching.",
    ]
    pdf_bytes = build_synthetic_pdf_bytes(lines)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert len(pdf_bytes) > 500

    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    extracted = reader.pages[0].extract_text()
    assert "Alex Rivers" in extracted
    assert "FastAPI" in extracted
    assert "PostgreSQL" in extracted


def test_synthetic_pdf_upload_api_success():
    """Test full upload route /api/resume/analyze with in-memory synthetic PDF."""
    pdf_bytes = build_synthetic_pdf_bytes([
        "Jordan Taylor - Staff Distributed Systems Engineer",
        "Skills: Golang, Kubernetes, Apache Kafka, Prometheus, gRPC",
        "Engineered multi-region Kafka streaming pipelines processing 1M events per second.",
        "Implemented custom Kubernetes controllers and Prometheus alert metrics.",
    ])

    mock_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "extracted_skills": ["Golang", "Kubernetes", "Apache Kafka", "Prometheus", "gRPC"],
        "projects_and_experience": ["Engineered multi-region Kafka streaming pipelines"],
        "skill_evaluations": [
            {
                "skill_name": "Apache Kafka",
                "category": "Demonstrated in resume",
                "evidence": "Engineered multi-region Kafka streaming pipelines processing 1M events per second.",
                "relevance_to_role": "Core event streaming competency.",
            }
        ],
        "personalized_questions": [
            {
                "id": "q_1",
                "question_number": 1,
                "text": "How do you configure Kafka consumer groups for exactly-once processing?",
                "assessed_skill": "Apache Kafka",
                "difficulty": "Hard",
                "rubric": "Candidate explains transactional producers and isolation levels.",
                "rationale": "Validates Kafka streaming claim.",
            }
        ],
        "role_readiness_summary": "Exceptional distributed systems profile.",
    })
    mock_completion.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("app.core.config.settings.GROQ_API_KEY", "gsk_test"), \
         patch("app.core.groq_client.groq_manager.get_client", return_value=mock_client):

        response = client.post(
            "/api/resume/analyze",
            files={"file": ("synthetic_resume.pdf", pdf_bytes, "application/pdf")},
            data={"target_role": "Staff Distributed Systems Engineer", "experience_level": "Staff"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data
        assert data["target_role"] == "Staff Distributed Systems Engineer"
        assert "Apache Kafka" in data["extracted_skills"]
        assert data["is_truncated"] is False
        assert data["analyzed_character_count"] is not None
        assert data["analyzed_character_count"] < 12000


def test_corrupted_pdf_upload_rejection():
    """Corrupted PDF without magic header returns HTTP 400."""
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("corrupt.pdf", b"NOT_A_REAL_PDF_HEADER_BYTES", "application/pdf")},
        data={"target_role": "Backend Engineer", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 400
    assert "missing PDF magic header" in response.json()["detail"]


def test_empty_pdf_upload_rejection():
    """Empty PDF file returns HTTP 400."""
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"target_role": "Backend Engineer", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 400
    assert "empty (0 bytes)" in response.json()["detail"]


def test_non_pdf_extension_rejection():
    """Non-PDF extension returns HTTP 400."""
    response = client.post(
        "/api/resume/analyze",
        files={"file": ("resume.docx", b"%PDF-1.4 fake docx", "application/vnd.openxmlformats")},
        data={"target_role": "Backend Engineer", "experience_level": "Mid-Level"},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


# ===========================================================================
# 3. Legacy Records Backward Compatibility
# ===========================================================================

@pytest.mark.asyncio
async def test_legacy_resume_record_without_truncation_fields():
    """Legacy resume record missing is_truncated and analyzed_character_count defaults safely."""
    aid = str(uuid.uuid4())
    legacy_doc = {
        "analysis_id": aid,
        "target_role": "Software Engineer",
        "experience_level": "Mid-Level",
        "extracted_skills": ["Python"],
        "projects_and_experience": ["Web development"],
        "skill_evaluations": [],
        "personalized_questions": [],
        "role_readiness_summary": "Legacy candidate.",
        "created_at": "2025-01-01T00:00:00+00:00",
        # Notice: is_truncated and analyzed_character_count are missing!
    }
    _in_memory_analyses[aid] = legacy_doc

    result = await get_resume_analysis(aid)
    assert result is not None
    assert result.analysis_id == aid
    assert result.is_truncated is False
    assert result.analyzed_character_count is None
