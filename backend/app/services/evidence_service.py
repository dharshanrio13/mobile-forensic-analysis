"""
Evidence intake service.

This service is the high-level entry point for bringing a simulated
evidence package (a ZIP file) into the system. It coordinates - but
does not duplicate - the lower-level pieces that already exist:

    - app.core.config.settings for where things get saved
    - app.services.extraction_service for safely extracting the ZIP

Responsibilities of this file, and only this file:
    - accept an already-uploaded file (as a path on disk, e.g. a temp
      file the API layer received) plus its original filename
    - validate that it looks like an expected evidence package
    - save it into the configured upload location
    - generate case/evidence identifiers when the caller doesn't
      supply them
    - invoke the existing extraction service
    - return one structured result describing what happened

This service does NOT parse evidence contents (see app/parsers/),
build a timeline, correlate events, touch a database, or define any
API route. It has no FastAPI import at all - the API layer is
expected to receive the upload, write it to a temporary path, and
pass that path plus the original filename in here.
"""

import os
import shutil
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings
from app.services.extraction_service import (
    ExtractionResult,
    UnsafeZipError,
    ZipBombError,
    extract_evidence_zip,
)

# File extensions considered a plausible evidence package. Anything
# else is rejected before we even try to save or extract it.
_ALLOWED_EXTENSIONS = {".zip"}


@dataclass
class EvidenceIntakeResult:
    """
    Structured outcome of processing one evidence package upload.

    Attributes:
        success: Whether the package was validated, saved, and
            extracted without error.
        case_id: The case this evidence belongs to (generated if the
            caller didn't provide one).
        evidence_id: Identifier for this specific upload event.
        original_filename: The filename as provided by the uploader.
        saved_path: Where the uploaded package was saved under
            settings.UPLOAD_DIR.
        extraction: The ExtractionResult from the extraction service,
            if extraction was attempted (None if validation failed
            before extraction was reached).
        error: Human-readable reason for failure, if success is False.
    """

    success: bool
    case_id: str
    evidence_id: str
    original_filename: str
    saved_path: Optional[str] = None
    extraction: Optional[ExtractionResult] = None
    error: Optional[str] = None


def _validate_filename(original_filename: str) -> Optional[str]:
    """
    Check that `original_filename` has an extension we accept as an
    evidence package. Returns an error message if invalid, or None if
    it's fine.
    """
    if not original_filename or not original_filename.strip():
        return "No filename provided"

    _, ext = os.path.splitext(original_filename)
    if ext.lower() not in _ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS))
        return f"Unsupported file extension '{ext}'. Expected one of: {allowed}"

    return None


def _generate_case_id() -> str:
    """Generate a new case identifier when the caller doesn't supply one."""
    return f"CASE-{uuid.uuid4()}"


def _generate_evidence_id() -> str:
    """Generate an identifier for this specific upload/intake event."""
    return str(uuid.uuid4())


def _save_uploaded_package(source_file_path: str, case_id: str, evidence_id: str, original_filename: str) -> str:
    """
    Copy the already-received file at `source_file_path` into
    settings.UPLOAD_DIR under a collision-resistant name, and return
    the saved path.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    safe_original_name = os.path.basename(original_filename)
    saved_filename = f"{case_id}_{evidence_id}_{safe_original_name}"
    saved_path = os.path.join(settings.UPLOAD_DIR, saved_filename)

    shutil.copyfile(source_file_path, saved_path)
    return saved_path


def intake_evidence_package(
    source_file_path: str,
    original_filename: str,
    case_id: Optional[str] = None,
) -> EvidenceIntakeResult:
    """
    Process the intake of one simulated evidence package.

    Args:
        source_file_path: Path to the already-uploaded file on disk
            (e.g. a temp path the API layer wrote the upload to).
            This service does not receive raw upload bytes directly -
            that's the API layer's job.
        original_filename: The filename as provided by whoever
            uploaded it (used for extension validation and to build a
            readable saved filename).
        case_id: Case this evidence belongs to. If omitted, a new
            case_id is generated - useful for a first-time upload that
            starts a new case.

    Returns:
        An EvidenceIntakeResult describing what happened. On failure,
        `success` is False and `error` explains why - this function
        does not raise for expected failure conditions (bad
        extension, missing file, unsafe/oversized ZIP); it only raises
        for genuinely unexpected errors it can't reason about.
    """
    resolved_case_id = case_id if case_id else _generate_case_id()
    evidence_id = _generate_evidence_id()

    result = EvidenceIntakeResult(
        success=False,
        case_id=resolved_case_id,
        evidence_id=evidence_id,
        original_filename=original_filename,
    )

    filename_error = _validate_filename(original_filename)
    if filename_error:
        result.error = filename_error
        return result

    if not os.path.isfile(source_file_path):
        result.error = f"Uploaded file not found at expected path: {source_file_path}"
        return result

    try:
        saved_path = _save_uploaded_package(
            source_file_path, resolved_case_id, evidence_id, original_filename
        )
        result.saved_path = saved_path
    except OSError as exc:
        result.error = f"Failed to save uploaded package: {exc}"
        return result

    try:
        extraction = extract_evidence_zip(saved_path, case_id=resolved_case_id)
        result.extraction = extraction
    except (FileNotFoundError, ValueError, ZipBombError, UnsafeZipError) as exc:
        result.error = f"Extraction failed: {exc}"
        return result

    result.success = True
    return result
