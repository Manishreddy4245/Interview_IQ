from pathlib import Path
from typing import List, Optional
from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=[
            str(_BACKEND_DIR / ".env"),
            str(_ROOT_DIR / ".env"),
            ".env",
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="development", description="Application environment")
    PORT: int = Field(default=8000, description="Server port")
    HOST: str = Field(default="0.0.0.0", description="Server host")
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated allowed CORS origins",
    )

    # MongoDB Atlas settings
    MONGODB_URI: Optional[str] = Field(
        default=None,
        description="MongoDB Atlas connection URI. Required for database operations.",
    )
    MONGODB_DATABASE: str = Field(
        default="interviewiq",
        description="MongoDB database name",
    )

    # Groq settings
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Groq API Key. Required for intelligence modules.",
    )
    GROQ_MODEL: str = Field(
        default="openai/gpt-oss-20b",
        description="Active Groq chat model for question generation, evaluation, and synthesis",
    )
    GROQ_TRANSCRIPTION_MODEL: str = Field(
        default="whisper-large-v3",
        description="Active Groq speech-to-text model for audio transcription",
    )

    # JWT Authentication & RBAC settings
    JWT_SECRET: str = Field(
        default="interviewiq_insecure_default_dev_secret_replace_in_production_key_32bytes",
        description="Secret key for JWT token signing. Must be overridden in production via environment.",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT cryptographic algorithm",
    )
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24,  # 24 hours
        description="JWT access token expiry in minutes",
    )

    # Code execution provider settings
    CODE_EXECUTION_PROVIDER: str = Field(
        default="auto",
        description="Execution provider: 'auto', 'local', 'piston', 'judge0'",
    )
    PISTON_API_URL: Optional[str] = Field(
        default=None,
        description="Piston execute endpoint (e.g. self-hosted instance or hosted provider)",
    )
    PISTON_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional API key for Piston-compatible hosted instance",
    )
    JUDGE0_API_URL: Optional[str] = Field(
        default=None,
        description="Judge0 submissions endpoint (e.g. https://judge0-ce.p.rapidapi.com/submissions?wait=true)",
    )
    JUDGE0_API_KEY: Optional[str] = Field(
        default=None,
        description="RapidAPI key or authentication key for Judge0",
    )
    JUDGE0_HOST: str = Field(
        default="judge0-ce.p.rapidapi.com",
        description="Judge0 RapidAPI host header",
    )

    @computed_field
    @property
    def cors_origin_list(self) -> List[str]:
        """Parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_mongodb_configured(self) -> bool:
        """Check if MONGODB_URI is provided without empty whitespace."""
        return bool(self.MONGODB_URI and self.MONGODB_URI.strip())

    @property
    def is_groq_configured(self) -> bool:
        """Check if GROQ_API_KEY is provided without empty whitespace."""
        return bool(self.GROQ_API_KEY and self.GROQ_API_KEY.strip())

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        """Disallow insecure default secret if ENVIRONMENT is production."""
        if self.ENVIRONMENT.lower() == "production":
            if not self.JWT_SECRET or "insecure_default" in self.JWT_SECRET:
                raise ValueError("Insecure default JWT_SECRET cannot be used in production environment.")
        return self


settings = Settings()
