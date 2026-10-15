import logging
from typing import Optional, Dict, Any
import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("interviewiq.database")


class DatabaseManager:
    """Manages the MongoDB Atlas client lifecycle and database connections."""

    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None

    def connect(self) -> None:
        """
        Initialize the AsyncIOMotorClient instance.
        Fails explicitly if MONGODB_URI is not configured; does not fall back to localhost.
        """
        if not settings.is_mongodb_configured:
            logger.warning(
                "MongoDB Atlas URI is not configured. Database operations will be unavailable."
            )
            return

        try:
            client_kwargs: Dict[str, Any] = {
                "serverSelectionTimeoutMS": 15000,
                "connectTimeoutMS": 15000,
                "socketTimeoutMS": 15000,
            }
            try:
                client_kwargs["tlsCAFile"] = certifi.where()
            except Exception:
                pass

            self.client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                **client_kwargs,
            )
            self._db = self.client[settings.MONGODB_DATABASE]
            logger.info("MongoDB client initialized for database: %s", settings.MONGODB_DATABASE)
        except Exception as exc:
            self.client = None
            self._db = None
            logger.error("Failed to initialize MongoDB client: %s", type(exc).__name__)
            raise RuntimeError(f"Failed to initialize MongoDB client: {type(exc).__name__}") from exc

    def disconnect(self) -> None:
        """Close the MongoDB client connection cleanly."""
        if self.client is not None:
            self.client.close()
            self.client = None
            self._db = None
            logger.info("MongoDB connection closed.")

    def get_database(self) -> AsyncIOMotorDatabase:
        """
        Get the current database instance.
        Raises RuntimeError if not connected.
        """
        if not settings.is_mongodb_configured:
            raise RuntimeError(
                "MongoDB configuration error: MONGODB_URI is not set in the environment."
            )
        import asyncio
        try:
            current_loop = asyncio.get_running_loop()
            if self.client is not None:
                client_loop = getattr(self.client, "io_loop", None)
                if client_loop and client_loop is not current_loop:
                    self.client = None
                    self._db = None
        except RuntimeError:
            pass

        if self._db is None or self.client is None:
            self.connect()
        if self._db is None or self.client is None:
            raise RuntimeError("Database connection has not been initialized.")
        return self._db

    async def check_health(self) -> Dict[str, Any]:
        """
        Execute an admin ping command to verify active MongoDB Atlas connectivity.
        Fails clearly if MONGODB_URI is missing or unreachable.
        """
        if not settings.is_mongodb_configured:
            return {
                "status": "unconfigured",
                "detail": "MONGODB_URI is not configured in the environment.",
                "database": settings.MONGODB_DATABASE,
            }

        import asyncio
        try:
            current_loop = asyncio.get_running_loop()
            if self.client is not None:
                client_loop = getattr(self.client, "io_loop", None)
                if client_loop and client_loop is not current_loop:
                    self.client = None
                    self._db = None
        except RuntimeError:
            pass

        if self.client is None:
            # Attempt lazy connection if configured
            try:
                self.connect()
            except Exception as exc:
                return {
                    "status": "error",
                    "detail": f"Failed to connect to MongoDB Atlas: {type(exc).__name__}",
                    "database": settings.MONGODB_DATABASE,
                }

        if self.client is None:
            return {
                "status": "error",
                "detail": "MongoDB client is uninitialized.",
                "database": settings.MONGODB_DATABASE,
            }

        try:
            # Execute standard MongoDB ping command against admin db
            await self.client.admin.command("ping")
            return {
                "status": "connected",
                "detail": "MongoDB Atlas connection is healthy.",
                "database": settings.MONGODB_DATABASE,
            }
        except Exception as exc:
            logger.error("MongoDB Atlas health check failed: %s", type(exc).__name__)
            try:
                if self.client is not None:
                    self.client.close()
            except Exception:
                pass
            self.client = None
            self._db = None
            return {
                "status": "unreachable",
                "detail": f"MongoDB Atlas ping failed: {type(exc).__name__}",
                "database": settings.MONGODB_DATABASE,
            }


db_manager = DatabaseManager()
