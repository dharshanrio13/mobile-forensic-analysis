from fastapi import FastAPI

from app.core.config import settings
from app.api.routes.cases import router as cases_router
from app.api.routes.evidence import router as evidence_router   # <- is this line present?

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend foundation for analyzing simulated mobile-device evidence.",
    version="0.1.0",
    debug=settings.DEBUG,
)

app.include_router(cases_router)
app.include_router(evidence_router)   # <- is this line present?


@app.get("/health")
def health_check():
    return {"status": "ok"}