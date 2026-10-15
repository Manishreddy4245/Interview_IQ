from typing import Optional
from pydantic import BaseModel, Field


class AudioTranscriptionResponse(BaseModel):
    """Structured response for candidate spoken audio transcription."""

    transcript: str = Field(..., description="Transcribed spoken text")
    detected_language: Optional[str] = Field(default="en", description="Detected or requested language code")
    model_used: str = Field(..., description="Active Groq Whisper transcription model used")
    duration_seconds: Optional[float] = Field(default=None, description="Audio duration if deterministically parsed")
    file_size_bytes: int = Field(..., description="Uploaded audio payload size in bytes")
