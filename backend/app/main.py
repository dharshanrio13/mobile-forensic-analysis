"""
Mobile Device Forensic Analysis System - Backend Foundation

Minimal FastAPI application. This is the starting point only:
no database, auth, upload, parsing, timeline, or AI functionality
has been added yet.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Mobile Device Forensic Analysis System",
    description="Backend foundation for analyzing simulated mobile-device evidence.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    """Simple health check to confirm the backend is running."""
    return {"status": "ok"}
