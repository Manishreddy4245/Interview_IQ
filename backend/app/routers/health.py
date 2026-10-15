from fastapi import APIRouter, status, Response
from app.core.config import settings
from app.core.database import db_manager
from app.core.groq_client import groq_manager
from app.schemas.health import (
    HealthResponse,
    DatabaseHealthResponse,
    GroqHealthResponse,
    MLModelHealthResponse,
)
from app.services.text_assessment_service import text_assessment_service

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application Health Check",
    description="Returns minimal JSON response indicating the FastAPI application is running.",
)
async def get_health() -> HealthResponse:
    """Return basic health status of the FastAPI backend service."""
    return HealthResponse(
        status="ok",
        service="interviewiq-backend",
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    summary="MongoDB Atlas Health Check",
    description="Verifies the active connection to MongoDB Atlas by executing a ping command.",
)
async def get_database_health(response: Response) -> DatabaseHealthResponse:
    """
    Ping MongoDB Atlas to verify live connectivity.
    Returns 503 Service Unavailable if unconfigured or connection fails.
    """
    health_result = await db_manager.check_health()
    if health_result["status"] != "connected":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return DatabaseHealthResponse(
        status=health_result["status"],
        detail=health_result["detail"],
        database=health_result["database"],
    )


@router.get(
    "/health/groq",
    response_model=GroqHealthResponse,
    summary="Groq Configuration Health Check",
    description="Checks whether Groq API credentials are configured without making model calls.",
)
async def get_groq_health(response: Response) -> GroqHealthResponse:
    """Check Groq configuration readiness for Phase 2."""
    config_result = groq_manager.check_configuration()
    if not config_result["configured"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return GroqHealthResponse(
        configured=config_result["configured"],
        status=config_result["status"],
        detail=config_result["detail"],
    )


@router.get(
    "/health/ml",
    response_model=MLModelHealthResponse,
    summary="Text Assessment ML Model Health Check",
    description="Verifies readiness of the SentenceTransformer neural model refactored from Text_Assessment_Model.ipynb.",
)
async def get_ml_health(response: Response) -> MLModelHealthResponse:
    """Check whether the Text Assessment SentenceTransformer model is loaded and ready for inference."""
    is_ready = text_assessment_service.is_loaded
    if not is_ready:
        try:
            text_assessment_service.load_model()
            is_ready = text_assessment_service.is_loaded
        except Exception as exc:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return MLModelHealthResponse(
                loaded=False,
                model_name=text_assessment_service.model_name,
                status="unhealthy",
                detail=f"Model failed to load: {type(exc).__name__} - {str(exc)}",
            )

    return MLModelHealthResponse(
        loaded=is_ready,
        model_name=text_assessment_service.model_name,
        status="ready" if is_ready else "unloaded",
        detail="SentenceTransformer neural model is loaded and ready for embedding inference.",
    )
