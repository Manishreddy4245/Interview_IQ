import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import db_manager
from app.routers import health, interview, resume, decision, auth, communication, audio, roles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("interviewiq.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle manager.
    Connects to MongoDB Atlas on startup if configured, and closes on shutdown.
    """
    logger.info("Starting InterviewIQ backend service (Environment: %s)", settings.ENVIRONMENT)

    # Initialize MongoDB client if configured
    if settings.is_mongodb_configured:
        try:
            db_manager.connect()
            logger.info("Attempted MongoDB Atlas initialization.")
        except Exception as exc:
            logger.warning("MongoDB initial connection error: %s", type(exc).__name__)
    else:
        logger.info(
            "MONGODB_URI is not set in environment. Database features will remain unconfigured."
        )

    # Pre-warm Text Assessment ML Model (SentenceTransformer)
    try:
        from app.services.text_assessment_service import text_assessment_service
        text_assessment_service.load_model()
        logger.info("Text Assessment ML model initialized successfully.")
    except Exception as exc:
        logger.warning("Could not pre-warm Text Assessment ML model at startup: %s", type(exc).__name__)

    yield

    # Clean shutdown
    logger.info("Shutting down InterviewIQ backend service.")
    db_manager.disconnect()


app = FastAPI(
    title="InterviewIQ API",
    description="Modular FastAPI backend for InterviewIQ - Real-world AI Interview Practice & Intelligence Platform.",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(interview.router)
app.include_router(resume.router)
app.include_router(decision.router)
app.include_router(auth.router)
app.include_router(communication.router)
app.include_router(audio.router)
app.include_router(roles.router)
