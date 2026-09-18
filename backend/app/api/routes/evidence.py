"""
Evidence upload route.

Defines two endpoints:
    POST /cases/{case_id}/evidence  - upload and process an evidence ZIP
    GET  /cases/{case_id}/evidence  - list what has already been registered

The GET exists because the frontend's evidence table would otherwise be
empty after a page reload: the upload response is the only place that
information appears, and the browser has nowhere to keep it.

This route only orchestrates - it contains no ZIP handling, no JSON
parsing, no normalization and no analysis:

    1. Confirms the case exists (reusing the shared 404 helper in
       app.api.routes.cases).
    2. Streams the upload to a temporary path.
    3. Hands that path to app.services.processing_service, which runs
       the whole pipeline: save original ZIP -> SHA-256 -> extract ->
       load JSON -> normalize via the existing parsers.
    4. Stores the resulting evidence/events/errors in the centralized
       in-memory store (app.state).
    5. Returns a structured summary.

Uploaded archives are treated strictly as data. Nothing in them is
executed, imported or evaluated. The extraction service's existing
path-traversal and zip-bomb protections are left untouched and are
still the only way files leave the archive.
"""

import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.api.routes.cases import get_case_or_404
from app.core.config import settings
from app.services.processing_service import process_evidence_package
from app.state import app_state

router = APIRouter(prefix="/cases", tags=["evidence"])


class ProcessedEvidenceFile(BaseModel):
    """One evidence file that was extracted and registered."""

    id: str = Field(..., description="Identifier of the Evidence record for this file.")
    filename: str = Field(..., description="Name of the evidence file inside the package.")
    evidence_type: str = Field(..., description="Category label from EvidenceType.")


class EvidenceUploadResult(BaseModel):
    """
    Structured response for a completed evidence upload.

    Deliberately does NOT include server filesystem paths - the client
    has no use for them and they are internal detail.
    """

    success: bool
    case_id: str
    evidence_id: str = Field(
        ...,
        description="Identifier for this upload. Individual files get their own ids in evidence_items.",
    )
    original_filename: str
    processing_status: str = Field(
        ...,
        description="'processed' when at least one event was produced, "
        "'processed_with_warnings' when files were extracted but produced no events "
        "or had problems, 'no_supported_evidence' when the archive held nothing usable.",
    )
    sha256: Optional[str] = Field(None, description="SHA-256 digest of the uploaded package.")
    extracted_files: List[str] = Field(default_factory=list, description="Filenames extracted.")
    skipped_files: List[Dict[str, str]] = Field(
        default_factory=list, description="Archive entries not extracted, with a reason."
    )
    evidence_items: List[ProcessedEvidenceFile] = Field(default_factory=list)
    processed_event_count: int = 0
    normalization_error_count: int = 0
    device_info: Optional[Dict[str, Any]] = Field(
        None, description="Contents of device.json if the package contained one."
    )
    warnings: List[str] = Field(default_factory=list)


def _derive_processing_status(event_count: int, extracted_count: int) -> str:
    """Summarize how the upload went, in one predictable string."""
    if extracted_count == 0:
        return "no_supported_evidence"
    if event_count == 0:
        return "processed_with_warnings"
    return "processed"


@router.post(
    "/{case_id}/evidence",
    response_model=EvidenceUploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a simulated evidence ZIP",
)
async def upload_evidence(case_id: str, file: UploadFile = File(...)) -> EvidenceUploadResult:
    """
    Upload a simulated evidence ZIP for an existing case and process it
    end to end.

    Returns 404 if the case doesn't exist (checked before the upload is
    processed), or 400 if the package is rejected - a bad extension, an
    archive that isn't a valid ZIP, or one that trips the extraction
    service's safety limits.

    A malformed evidence file *inside* an otherwise valid archive is not
    a 400: the file is reported in `warnings` and counted in
    `normalization_error_count`, and the rest of the package is still
    processed.
    """
    get_case_or_404(case_id)

    os.makedirs(settings.TEMP_DIR, exist_ok=True)
    _, extension = os.path.splitext(file.filename or "")
    fd, temp_path = tempfile.mkstemp(prefix="evidence_upload_", suffix=extension, dir=settings.TEMP_DIR)

    try:
        with os.fdopen(fd, "wb") as temp_file:
            shutil.copyfileobj(file.file, temp_file)

        result = process_evidence_package(
            source_file_path=temp_path,
            original_filename=file.filename or "",
            case_id=case_id,
        )
    except Exception as exc:  # noqa: BLE001 - one bad upload must not kill the server
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evidence package could not be processed: {exc}",
        ) from exc
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    if not result.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error)

    app_state.record_processed_evidence(
        case_id=case_id,
        evidence_items=result.evidence_items,
        events=result.events,
        normalization_errors=result.normalization_errors,
        integrity_record={
            "evidence_id": result.evidence_id,
            "original_filename": result.original_filename,
            "sha256": result.sha256,
        },
        device_info=result.device_info,
        warnings=result.warnings,
    )

    return EvidenceUploadResult(
        success=True,
        case_id=case_id,
        evidence_id=result.evidence_id,
        original_filename=result.original_filename,
        processing_status=_derive_processing_status(len(result.events), len(result.extracted_files)),
        sha256=result.sha256,
        extracted_files=result.extracted_files,
        skipped_files=result.skipped_files,
        evidence_items=[
            ProcessedEvidenceFile(
                id=item.id,
                filename=item.filename,
                evidence_type=str(item.evidence_type),
            )
            for item in result.evidence_items
        ],
        processed_event_count=len(result.events),
        normalization_error_count=len(result.normalization_errors),
        device_info=result.device_info,
        warnings=result.warnings,
    )


class RegisteredEvidenceFile(BaseModel):
    """An evidence file already registered for a case."""

    id: str
    filename: str
    evidence_type: str
    uploaded_at: datetime


class EvidencePackageRecord(BaseModel):
    """An uploaded package and the digest recorded for it at intake."""

    evidence_id: str
    original_filename: str
    sha256: Optional[str] = None


class CaseEvidenceResponse(BaseModel):
    """Everything registered for a case, for the evidence view."""

    case_id: str
    total_files: int
    files: List[RegisteredEvidenceFile] = Field(default_factory=list)
    packages: List[EvidencePackageRecord] = Field(default_factory=list)
    device_info: Optional[Dict[str, Any]] = None
    total_events: int = 0
    normalization_error_count: int = 0


@router.get(
    "/{case_id}/evidence",
    response_model=CaseEvidenceResponse,
    summary="List evidence already registered for a case",
)
def list_case_evidence(case_id: str) -> CaseEvidenceResponse:
    """
    Return the evidence files and uploaded packages held in memory for
    this case. Returns empty collections when nothing has been uploaded,
    and 404 when the case doesn't exist.
    """
    get_case_or_404(case_id)

    items = app_state.get_evidence_items(case_id)
    integrity = app_state.get_integrity_records(case_id)

    return CaseEvidenceResponse(
        case_id=case_id,
        total_files=len(items),
        files=[
            RegisteredEvidenceFile(
                id=item.id,
                filename=item.filename,
                evidence_type=str(item.evidence_type),
                uploaded_at=item.uploaded_at,
            )
            for item in items
        ],
        packages=[
            EvidencePackageRecord(
                evidence_id=record.get("evidence_id", ""),
                original_filename=record.get("original_filename", ""),
                sha256=record.get("sha256"),
            )
            for record in integrity
        ],
        device_info=app_state.get_device_info(case_id),
        total_events=len(app_state.get_events(case_id)),
        normalization_error_count=len(app_state.get_normalization_errors(case_id)),
    )
