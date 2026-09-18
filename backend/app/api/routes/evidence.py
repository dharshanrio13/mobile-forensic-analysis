"""
Evidence upload route.

Defines a single endpoint: POST /cases/{case_id}/evidence.

This route does exactly three things:
    1. Verifies the case exists, by reusing the existing case-lookup
       mechanism in app.api.routes.cases (the same in-memory `_cases`
       dict and the same 404 behavior - nothing about case storage or
       lookup is reimplemented here).
    2. Writes the uploaded file to a temporary path and hands it to
       app.services.evidence_service.intake_evidence_package, which
       already owns validation, saving, identifier generation, and
       invoking the extraction service.
    3. Returns whatever that service reports, as structured JSON.

It does NOT extract ZIPs itself (that's app.services.extraction_service,
called indirectly via evidence_service), does NOT duplicate any of
evidence_service's validation/save/intake logic, does NOT touch a
database, and does NOT perform any analysis, timeline, correlation, or
AI processing - this route is intake only.
"""

import os
import shutil
import tempfile
from typing import Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.routes.cases import get_case
from app.core.config import settings
from app.services.evidence_service import intake_evidence_package

router = APIRouter(prefix="/cases", tags=["evidence"])


class EvidenceUploadResult(BaseModel):
    """
    Structured response for a completed (successful) evidence upload.

    Mirrors app.services.evidence_service.EvidenceIntakeResult - this
    is purely a response shape, not a reimplementation of the intake
    logic that produced these values.
    """

    success: bool
    case_id: str
    evidence_id: str
    original_filename: str
    saved_path: Optional[str] = None
    extracted_files: List[str] = []
    skipped_entries: List[Dict[str, str]] = []


@router.post(
    "cases/{case_id}/evidence",
    response_model=EvidenceUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(case_id: str, file: UploadFile = File(...)) -> EvidenceUploadResult:
    """
    Upload a simulated evidence ZIP for an existing case.

    Flow:
        1. Confirm `case_id` refers to a case that actually exists
           (raises 404 via the existing case-lookup mechanism if not -
           this happens before the upload is even read, so an upload
           against a bad case_id fails fast).
        2. Stream the uploaded file to a temp path under
           settings.TEMP_DIR.
        3. Delegate all validation, saving, and extraction to
           `intake_evidence_package` (evidence_service.py).
        4. Delete the temp file (evidence_service already made its own
           saved copy under settings.UPLOAD_DIR - this route's temp
           copy is scratch space only).
        5. Return a 201 with the structured result, or a 400 if
           intake_evidence_package reports a failure (bad extension,
           unsafe ZIP, etc.).
    """
    # Step 1: verify the case exists. get_case() already raises a 404
    # HTTPException itself if case_id isn't found - reusing it means
    # this route never needs its own case-existence check.
    get_case(case_id)

    # Step 2: write the upload to a temp path so evidence_service (which
    # works with file paths, not upload streams) can process it.
    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    _, extension = os.path.splitext(file.filename or "")
    fd, temp_path = tempfile.mkstemp(prefix="evidence_upload_", suffix=extension, dir=settings.TEMP_DIR)

    try:
        with os.fdopen(fd, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        # Step 3: hand off to evidence_service - all validation, saving,
        # identifier generation, and extraction happens there.
        result = intake_evidence_package(
            source_file_path=temp_path,
            original_filename=file.filename or "",
            case_id=case_id,
        )
    finally:
        # Step 4: this route's own temp copy is no longer needed either
        # way - evidence_service made its own persistent copy on success.
        if os.path.exists(temp_path):
            os.remove(temp_path)

    if not result.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error)

    # Step 5: structured, successful result.
    return EvidenceUploadResult(
        success=result.success,
        case_id=result.case_id,
        evidence_id=result.evidence_id,
        original_filename=result.original_filename,
        saved_path=result.saved_path,
        extracted_files=result.extraction.extracted_file_paths if result.extraction else [],
        skipped_entries=result.extraction.skipped_entries if result.extraction else [],
    )
