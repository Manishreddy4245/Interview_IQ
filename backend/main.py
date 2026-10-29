"""
InterviewIQ ASGI Entry Point for Production Deployment Platforms (Railway, Render, Fly.io).

Re-exports the core FastAPI `app` instance from `app.main`.
Supports both:
  1. uvicorn app.main:app --host 0.0.0.0 --port $PORT
  2. uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import os
import uvicorn
from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
