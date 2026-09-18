"""
FastAPI application entry point.

Creates the app, configures development CORS, and registers every
router. There is no database, so there is no startup/shutdown hook for
connections or migrations - application state lives in app/state.py for
the lifetime of this process.

Run it from the backend/ directory:

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analysis import router as analysis_router
from app.api.routes.cases import router as cases_router
from app.api.routes.communications import router as communications_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.locations import router as locations_router
from app.api.routes.reports import router as reports_router
from app.api.routes.timeline import router as timeline_router
from app.core.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Backend for analyzing SIMULATED mobile-device evidence. "
        "Reports observed evidence, deterministic statistical analysis, and "
        "potentially related events - never conclusions about conduct or intent."
    ),
    version="1.0.0",
    debug=settings.DEBUG,
)

# Development CORS. The frontend is served separately (a different
# origin), so the browser needs these headers to allow it to call this
# API. Override the allowed origins with the CORS_ORIGINS environment
# variable (comma-separated) - see app/core/config.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases_router)
app.include_router(evidence_router)
app.include_router(timeline_router)
app.include_router(locations_router)
app.include_router(communications_router)
app.include_router(analysis_router)
app.include_router(reports_router)


@app.get("/health", tags=["health"])
def health_check():
    """Liveness check used by clients and the integration test runner."""
    return {"status": "ok"}
