"""
Mobile Device Forensic Analysis System - Backend Foundation

Minimal FastAPI application. This is the starting point only:
no database, auth, upload, parsing, timeline, or AI functionality
has been added yet.
"""

from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend foundation for analyzing simulated mobile-device evidence.",
    version="0.1.0",
    debug=settings.DEBUG,
)


@app.get("/health")
def health_check():
    """Simple health check to confirm the backend is running."""
    return {"status": "ok"}
