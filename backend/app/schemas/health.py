from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Basic health check response schema."""

    status: str = Field(..., description="Service health status, e.g., 'ok'")
    service: str = Field(default="interviewiq-backend", description="Service identifier")
    environment: str = Field(default="development", description="Current operating environment")


class DatabaseHealthResponse(BaseModel):
    """Database connectivity health check response schema."""

    status: str = Field(
        ...,
        description="Database status: 'connected', 'unreachable', 'unconfigured', or 'error'",
    )
    detail: str = Field(..., description="Status description or error diagnosis")
    database: str = Field(..., description="Target database name")


class GroqHealthResponse(BaseModel):
    """Groq client configuration health check response schema."""

    configured: bool = Field(..., description="Whether GROQ_API_KEY is configured")
    status: str = Field(..., description="Configuration status")
    detail: str = Field(..., description="Status description")


class MLModelHealthResponse(BaseModel):
    """Machine learning model health check response schema."""

    loaded: bool = Field(..., description="Whether the SentenceTransformer neural model is loaded")
    model_name: str = Field(..., description="Name of the loaded model")
    status: str = Field(..., description="Model readiness status")
    detail: str = Field(..., description="Status description")
