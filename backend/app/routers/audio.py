import logging
import os
import re
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.groq_client import groq_manager
from app.core.security import (
    ROLE_CANDIDATE,
    get_current_user,
)
from app.schemas.audio import AudioTranscriptionResponse
from app.services.session_service import get_session

logger = logging.getLogger("interviewiq.audio_router")

router = APIRouter(prefix="/api/audio", tags=["Audio Intelligence"])

MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB max payload for Whisper transcription

# Valid audio extensions supported by Whisper
SUPPORTED_EXTENSIONS = {
    ".webm",
    ".wav",
    ".mp3",
    ".m4a",
    ".ogg",
    ".flac",
    ".mp4",
    ".mpeg",
    ".mpga",
}

# Recognized MIME types
SUPPORTED_MIME_PREFIXES = (
    "audio/webm",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mp3",
    "audio/mpeg",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/ogg",
    "audio/flac",
    "video/webm",
    "video/mp4",
    "application/octet-stream",
)


def _sanitize_audio_filename(raw_filename: Optional[str], content_type: Optional[str]) -> str:
    """Sanitize filename to prevent path traversal and guarantee a supported extension."""
    base_name = os.path.basename(raw_filename or "audio.webm")
    # Remove any dangerous characters
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", base_name)
    _, ext = os.path.splitext(cleaned.lower())

    if ext in SUPPORTED_EXTENSIONS:
        return cleaned

    # Fallback to extension based on content_type
    c_lower = (content_type or "").lower()
    if "wav" in c_lower:
        return f"{cleaned}.wav"
    if "mp3" in c_lower or "mpeg" in c_lower:
        return f"{cleaned}.mp3"
    if "mp4" in c_lower or "m4a" in c_lower:
        return f"{cleaned}.m4a"
    if "ogg" in c_lower:
        return f"{cleaned}.ogg"
    if "flac" in c_lower:
        return f"{cleaned}.flac"

    return f"{cleaned}.webm"


def _is_supported_format(filename: str, content_type: Optional[str]) -> bool:
    """Check if file has an accepted extension or audio MIME type."""
    _, ext = os.path.splitext(filename.lower())
    if ext in SUPPORTED_EXTENSIONS:
        return True

    if content_type:
        clean_mime = content_type.split(";")[0].strip().lower()
        if any(clean_mime.startswith(prefix) for prefix in SUPPORTED_MIME_PREFIXES):
            return True

    return False


@router.post(
    "/transcribe",
    response_model=AudioTranscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe Spoken Candidate Audio",
    description=(
        "Transcribes candidate speech to text using Groq's Whisper model. "
        "Requires Bearer authentication. Enforces a 25 MB payload limit and validated audio formats. "
        "Verifies session ownership if a session_id is provided."
    ),
)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio recording file (WebM, WAV, MP3, M4A, OGG, etc.)"),
    session_id: Optional[str] = Form(None, description="Optional interview session ID to verify candidate ownership"),
    question_id: Optional[str] = Form(None, description="Optional question ID associated with this answer"),
    language: Optional[str] = Form("en", description="Spoken language code (default: en)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> AudioTranscriptionResponse:
    """
    Transcribe candidate audio recording using Groq Whisper model.
    Enforces authentication, ownership, payload bounds, and privacy directives.
    """
    # 1. Enforce candidate ownership if session_id is supplied
    if session_id and session_id.strip():
        session = await get_session(session_id.strip())
        if session:
            session_owner = session.get("owner_id")
            if session_owner:
                if (
                    current_user.get("role") == ROLE_CANDIDATE
                    and session_owner != current_user.get("user_id")
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access forbidden: You cannot transcribe audio for another candidate's private session.",
                    )

    # 2. Validate file format
    raw_name = file.filename or "recording.webm"
    content_type = file.content_type or "audio/webm"
    if not _is_supported_format(raw_name, content_type):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Unsupported audio format. Supported formats include: "
                "WebM, WAV, MP3, M4A, OGG, FLAC, MP4."
            ),
        )

    # 3. Read content and validate size bounds
    try:
        content = await file.read()
    except Exception as exc:
        logger.error("Failed to read uploaded audio file: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded audio file payload.",
        ) from exc

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty. Please record a spoken answer before transcribing.",
        )

    if len(content) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file size exceeds the maximum limit of 25 MB ({len(content)} bytes received).",
        )

    if len(content) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file payload is too small or does not contain valid audio data.",
        )

    # 4. Prepare sanitized file tuple
    safe_filename = _sanitize_audio_filename(raw_name, content_type)
    clean_mime = content_type.split(";")[0].strip() or "audio/webm"

    # 5. Execute transcription via GroqManager
    # Safe logging: strictly log technical metadata, never raw audio or candidate speech
    logger.info(
        "Audio transcription started: user_id=%s, format=%s, size_bytes=%d",
        current_user.get("user_id"),
        safe_filename.split(".")[-1],
        len(content),
    )

    clean_language = language.strip() if language and language.strip() else "en"
    transcript_text = await groq_manager.execute_audio_transcription(
        file_tuple=(safe_filename, content, clean_mime),
        model=settings.GROQ_TRANSCRIPTION_MODEL,
        language=clean_language,
    )

    return AudioTranscriptionResponse(
        transcript=transcript_text,
        detected_language=clean_language,
        model_used=settings.GROQ_TRANSCRIPTION_MODEL,
        file_size_bytes=len(content),
    )
