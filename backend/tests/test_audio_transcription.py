from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app
from app.core.security import (
    create_access_token,
    ROLE_CANDIDATE,
    ROLE_REVIEWER,
    ROLE_ADMIN,
)
from app.services.session_service import _in_memory_sessions

client = TestClient(app)


@pytest.fixture
def candidate_token():
    return create_access_token(user_id="usr_cand_01", role=ROLE_CANDIDATE, name="Test Candidate")


@pytest.fixture
def other_candidate_token():
    return create_access_token(user_id="usr_cand_02", role=ROLE_CANDIDATE, name="Other Candidate")


@pytest.fixture
def reviewer_token():
    return create_access_token(user_id="usr_rev_01", role=ROLE_REVIEWER, name="Test Reviewer")


def test_transcribe_unauthenticated_rejected():
    """Verify unauthenticated requests are rejected with 401."""
    files = {"file": ("recording.webm", b"\x00" * 500, "audio/webm")}
    response = client.post("/api/audio/transcribe", files=files)
    assert response.status_code == 401
    assert "authentication required" in response.json()["detail"].lower()


def test_transcribe_invalid_token_rejected():
    """Verify invalid token signature is rejected with 401."""
    files = {"file": ("recording.webm", b"\x00" * 500, "audio/webm")}
    response = client.post(
        "/api/audio/transcribe",
        files=files,
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


@patch("app.routers.audio.groq_manager.execute_audio_transcription", new_callable=AsyncMock)
def test_transcribe_valid_audio_success(mock_transcribe, candidate_token):
    """Verify valid audio file upload transcribes successfully."""
    mock_transcribe.return_value = "I spearheaded the distributed cache migration using Redis and Raft consensus."

    audio_bytes = b"RIFF" + b"\x00" * 1000
    files = {"file": ("answer.webm", audio_bytes, "audio/webm")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["transcript"] == "I spearheaded the distributed cache migration using Redis and Raft consensus."
    assert data["model_used"] == "whisper-large-v3"
    assert data["detected_language"] == "en"
    assert data["file_size_bytes"] == len(audio_bytes)
    assert mock_transcribe.await_count == 1


def test_transcribe_empty_file_rejected(candidate_token):
    """Verify empty (0-byte) audio file is rejected with 400 Bad Request."""
    files = {"file": ("empty.webm", b"", "audio/webm")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_transcribe_file_too_small_rejected(candidate_token):
    """Verify corrupted or tiny audio payload (< 100 bytes) is rejected with 400."""
    files = {"file": ("tiny.webm", b"too small", "audio/webm")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 400
    assert "too small" in response.json()["detail"].lower()


def test_transcribe_oversized_file_rejected(candidate_token):
    """Verify files exceeding 25 MB are rejected with 413 Payload Too Large."""
    oversized_bytes = b"\x00" * (25 * 1024 * 1024 + 1024)
    files = {"file": ("huge.webm", oversized_bytes, "audio/webm")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 413
    assert "exceeds the maximum limit of 25 mb" in response.json()["detail"].lower()


def test_transcribe_unsupported_format_rejected(candidate_token):
    """Verify unsupported file extensions/MIME types are rejected with 415."""
    files = {"file": ("script.sh", b"#!/bin/bash\necho hello" * 10, "text/x-shellscript")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 415
    assert "unsupported audio format" in response.json()["detail"].lower()


def test_transcribe_cross_candidate_ownership_rejected(candidate_token):
    """Verify candidate cannot transcribe audio for another candidate's private session."""
    session_id = "sess_private_cand_02"
    _in_memory_sessions[session_id] = {
        "session_id": session_id,
        "owner_id": "usr_cand_02",  # Belongs to candidate 2
        "role": "Backend Engineer",
        "questions": [],
    }

    files = {"file": ("answer.webm", b"RIFF" + b"\x00" * 500, "audio/webm")}
    data = {"session_id": session_id}
    headers = {"Authorization": f"Bearer {candidate_token}"}  # Candidate 1 token

    response = client.post("/api/audio/transcribe", files=files, data=data, headers=headers)
    assert response.status_code == 403
    assert "cannot transcribe audio for another candidate" in response.json()["detail"].lower()


@patch("app.routers.audio.groq_manager.execute_audio_transcription", new_callable=AsyncMock)
def test_transcribe_own_session_allowed(mock_transcribe, candidate_token):
    """Verify candidate can transcribe audio for their own session."""
    mock_transcribe.return_value = "Candidate answer."

    session_id = "sess_own_cand_01"
    _in_memory_sessions[session_id] = {
        "session_id": session_id,
        "owner_id": "usr_cand_01",
        "role": "Frontend Engineer",
        "questions": [],
    }

    files = {"file": ("answer.webm", b"RIFF" + b"\x00" * 500, "audio/webm")}
    data = {"session_id": session_id}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, data=data, headers=headers)
    assert response.status_code == 200
    assert response.json()["transcript"] == "Candidate answer."


@patch("app.routers.audio.groq_manager.execute_audio_transcription", new_callable=AsyncMock)
def test_transcribe_reviewer_can_transcribe_any_session(mock_transcribe, reviewer_token):
    """Verify reviewer can transcribe audio even if session belongs to a candidate."""
    mock_transcribe.return_value = "Reviewer transcribed audio note."

    session_id = "sess_cand_01_for_reviewer"
    _in_memory_sessions[session_id] = {
        "session_id": session_id,
        "owner_id": "usr_cand_01",
        "role": "DevOps Engineer",
        "questions": [],
    }

    files = {"file": ("answer.webm", b"RIFF" + b"\x00" * 500, "audio/webm")}
    data = {"session_id": session_id}
    headers = {"Authorization": f"Bearer {reviewer_token}"}

    response = client.post("/api/audio/transcribe", files=files, data=data, headers=headers)
    assert response.status_code == 200
    assert response.json()["transcript"] == "Reviewer transcribed audio note."


@patch("app.routers.audio.groq_manager.execute_audio_transcription", new_callable=AsyncMock)
def test_transcribe_groq_rate_limit_handled(mock_transcribe, candidate_token):
    """Verify rate limit errors from Groq propagate cleanly as 429."""
    mock_transcribe.side_effect = HTTPException(
        status_code=429,
        detail="Rate limit exceeded: AI audio transcription is temporarily busy.",
    )

    files = {"file": ("answer.webm", b"RIFF" + b"\x00" * 500, "audio/webm")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


@patch("app.routers.audio.groq_manager.execute_audio_transcription", new_callable=AsyncMock)
def test_transcribe_groq_timeout_handled(mock_transcribe, candidate_token):
    """Verify timeout errors propagate as 504."""
    mock_transcribe.side_effect = HTTPException(
        status_code=504,
        detail="Audio transcription request timed out. Please try again with a shorter recording.",
    )

    files = {"file": ("answer.webm", b"RIFF" + b"\x00" * 500, "audio/webm")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


@patch("app.routers.audio.groq_manager.execute_audio_transcription", new_callable=AsyncMock)
def test_transcribe_filename_sanitization(mock_transcribe, candidate_token):
    """Verify path traversal in filename is sanitized safely."""
    mock_transcribe.return_value = "Sanitized filename audio."

    files = {"file": ("../../etc/passwd.webm", b"RIFF" + b"\x00" * 500, "audio/webm")}
    headers = {"Authorization": f"Bearer {candidate_token}"}

    response = client.post("/api/audio/transcribe", files=files, headers=headers)
    assert response.status_code == 200
    # Verify file_tuple received a safe filename
    called_tuple = mock_transcribe.call_args[1]["file_tuple"]
    assert ".." not in called_tuple[0]
    assert "/" not in called_tuple[0]
    assert "\\" not in called_tuple[0]
