"""
Evidence processing (ingestion) service.

This is the missing link between "a ZIP arrived" and "the API has
normalized Events to serve". It coordinates existing services in
order and adds nothing they already do:

    intake (evidence_service)   -> validate + save original ZIP + extract
    integrity_service           -> SHA-256 of the saved package
    json loading                -> read each extracted evidence file
    normalization_service       -> raw records -> Unified Events
                                   (which delegates to app/parsers/)

It does NOT re-implement ZIP validation, path-traversal defence,
zip-bomb limits, timestamp parsing, coordinate validation, timeline
sorting, correlation, or report building. Every one of those already
lives somewhere else and is called, not copied.

Uploaded evidence is treated strictly as DATA. Nothing extracted from
an archive is executed, imported, or evaluated - files are opened,
JSON-decoded, and handed to the parsers.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import timezone
from typing import Any, Dict, List, Optional

from app.models.event import Event
from app.models.evidence import Evidence, EvidenceType
from app.services.evidence_service import intake_evidence_package
from app.services.integrity_service import calculate_sha256
from app.services.normalization_service import (
    EvidenceCategory,
    NormalizationResult,
    normalize_records,
)

# Maps each supported evidence filename to the evidence category the
# normalization service should route it through, and the EvidenceType
# the resulting Evidence record is labelled with.
#
# The filenames here are a subset of
# extraction_service.SUPPORTED_FILENAMES - extraction decides what is
# allowed out of the archive, this table decides what to do with it.
_FILENAME_TO_CATEGORY: Dict[str, EvidenceCategory] = {
    "app_activity.json": EvidenceCategory.APP,
    "calls.json": EvidenceCategory.CALL,
    "messages.json": EvidenceCategory.MESSAGE,
    "locations.json": EvidenceCategory.LOCATION,
    "system_logs.json": EvidenceCategory.SYSTEM_LOG,
}

_FILENAME_TO_EVIDENCE_TYPE: Dict[str, EvidenceType] = {
    "app_activity.json": EvidenceType.APPLICATION_DATA,
    "calls.json": EvidenceType.CALL_LOG,
    "messages.json": EvidenceType.MESSAGE_LOG,
    "locations.json": EvidenceType.OTHER,
    "system_logs.json": EvidenceType.OTHER,
    "device.json": EvidenceType.DOCUMENT,
}

# device.json describes the device itself rather than a series of
# timestamped occurrences, so there is no parser for it and it never
# becomes Events. It is carried through as case context instead.
_DEVICE_FILENAME = "device.json"


@dataclass
class ProcessingResult:
    """
    Outcome of processing one uploaded evidence package, end to end.

    Attributes:
        success: True if the package was saved, extracted and
            processed. Per-record parse failures do NOT make this
            False - they are reported in `normalization_errors`.
        case_id: Case the package was processed for.
        evidence_id: Identifier for this upload/ingest event. Each
            extracted file also gets its own Evidence record (see
            `evidence_items`); this id identifies the package they
            came from.
        original_filename: Filename as supplied by the uploader.
        sha256: SHA-256 digest of the saved original package.
        extracted_files: Basenames of the supported files extracted.
        skipped_files: Archive entries deliberately not extracted,
            each with a reason (e.g. an unsupported filename).
        evidence_items: One Evidence record per extracted evidence
            file, ready to be stored in application state.
        events: Unified Events normalized from the package.
        normalization_errors: Source records that could not be parsed.
        device_info: Parsed device.json contents, if present.
        warnings: Non-fatal problems (e.g. a file that wasn't valid
            JSON, or timestamps missing a timezone).
        error: Why processing failed, when `success` is False.
    """

    success: bool
    case_id: str
    evidence_id: str
    original_filename: str
    sha256: Optional[str] = None
    extracted_files: List[str] = field(default_factory=list)
    skipped_files: List[Dict[str, str]] = field(default_factory=list)
    evidence_items: List[Evidence] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    normalization_errors: List[Dict[str, Any]] = field(default_factory=list)
    device_info: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None


def _load_json_file(file_path: str) -> Any:
    """
    Read and JSON-decode one extracted evidence file.

    The file is opened and decoded as data only. Raises ValueError
    with a readable message on unreadable or malformed files so a
    single bad file can be reported without aborting the upload.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"File is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Could not read file: {exc}") from exc


def _coerce_records(payload: Any) -> List[Dict[str, Any]]:
    """
    Accept either a bare JSON list of records, or an object wrapping
    one under a common key, and return the list of records.

    Some simulated exports write `[{...}, {...}]` while others write
    `{"records": [{...}]}` or `{"calls": [{...}]}`. Anything else is
    handed to the parser unchanged, which will report it as an error
    in the normal way rather than this function guessing.
    """
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("records", "entries", "items", "data", "events",
                    "calls", "messages", "locations", "logs", "activity"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    return payload


def _ensure_timezone_aware(events: List[Event]) -> int:
    """
    Make sure every Event timestamp is timezone-aware, assuming UTC
    for any that isn't.

    Why this exists: the timeline and correlation services compare
    timestamps against each other and against query bounds, and Python
    raises TypeError when comparing an aware datetime with a naive one.
    Simulated evidence that omits a UTC offset would otherwise make
    those endpoints fail at request time. Coercing once here, at the
    ingestion boundary, keeps every downstream consumer safe without
    changing any parser.

    Returns the number of events that had to be adjusted.
    """
    adjusted = 0
    for event in events:
        if event.timestamp.tzinfo is None:
            event.timestamp = event.timestamp.replace(tzinfo=timezone.utc)
            adjusted += 1
    return adjusted


def _process_extracted_files(
    extracted_paths: List[str],
    case_id: str,
    evidence_id: str,
) -> ProcessingResult:
    """
    Load each extracted evidence file and normalize it into Events.

    A file that can't be read, isn't valid JSON, or isn't a recognized
    evidence filename is recorded and skipped - it never aborts
    processing of the remaining files.
    """
    partial = ProcessingResult(
        success=True,
        case_id=case_id,
        evidence_id=evidence_id,
        original_filename="",
    )

    for file_path in sorted(extracted_paths):
        filename = os.path.basename(file_path)
        partial.extracted_files.append(filename)

        try:
            payload = _load_json_file(file_path)
        except ValueError as exc:
            partial.warnings.append(f"{filename}: {exc}")
            partial.normalization_errors.append(
                {"category": None, "record": None, "reason": f"{filename}: {exc}"}
            )
            continue

        if filename == _DEVICE_FILENAME:
            if isinstance(payload, dict):
                partial.device_info = payload
            else:
                partial.warnings.append(
                    f"{filename}: expected a JSON object describing the device; stored no device info"
                )
            partial.evidence_items.append(
                Evidence(
                    case_id=case_id,
                    filename=filename,
                    evidence_type=_FILENAME_TO_EVIDENCE_TYPE[filename],
                    file_path=file_path,
                )
            )
            continue

        category = _FILENAME_TO_CATEGORY.get(filename)
        if category is None:
            # Extraction let it through but this service has no
            # category for it. Reported, not fatal.
            partial.warnings.append(f"{filename}: no evidence category mapped; file not normalized")
            continue

        records = _coerce_records(payload)
        result: NormalizationResult = normalize_records(
            category=category,
            records=records,
            case_id=case_id,
        )

        partial.events.extend(result.events)
        partial.normalization_errors.extend(
            [{**error, "file": filename} for error in result.errors]
        )
        partial.evidence_items.append(
            Evidence(
                case_id=case_id,
                filename=filename,
                evidence_type=_FILENAME_TO_EVIDENCE_TYPE.get(filename, EvidenceType.OTHER),
                file_path=file_path,
            )
        )

    adjusted = _ensure_timezone_aware(partial.events)
    if adjusted:
        partial.warnings.append(
            f"{adjusted} event timestamp(s) had no timezone offset and were interpreted as UTC"
        )

    return partial


def process_evidence_package(
    source_file_path: str,
    original_filename: str,
    case_id: str,
) -> ProcessingResult:
    """
    Run one uploaded evidence package through the full pipeline.

    Steps, in order:
        1. `intake_evidence_package` validates the upload, saves the
           original ZIP under settings.UPLOAD_DIR, and extracts the
           supported files via the extraction service (which keeps its
           own path-traversal and zip-bomb protections).
        2. `calculate_sha256` hashes the saved original package.
        3. Each extracted file is JSON-decoded.
        4. Each file's records go to `normalize_records`, which
           dispatches to the existing per-category parser.
        5. One Evidence record is built per extracted evidence file.

    Args:
        source_file_path: Path the API layer wrote the upload to.
        original_filename: Filename supplied by the uploader.
        case_id: Case this evidence belongs to. Callers are expected
            to have already confirmed the case exists.

    Returns:
        A ProcessingResult. Expected failures (bad extension, unsafe
        or oversized archive, unreadable file) set `success` to False
        with `error` explaining why, rather than raising.
    """
    intake = intake_evidence_package(
        source_file_path=source_file_path,
        original_filename=original_filename,
        case_id=case_id,
    )

    if not intake.success:
        return ProcessingResult(
            success=False,
            case_id=intake.case_id,
            evidence_id=intake.evidence_id,
            original_filename=original_filename,
            error=intake.error,
        )

    result = ProcessingResult(
        success=True,
        case_id=intake.case_id,
        evidence_id=intake.evidence_id,
        original_filename=original_filename,
    )

    if intake.saved_path:
        try:
            result.sha256 = calculate_sha256(intake.saved_path)
        except OSError as exc:
            result.warnings.append(f"Could not calculate SHA-256 of the saved package: {exc}")

    extraction = intake.extraction
    if extraction is None:
        result.success = False
        result.error = "Extraction did not produce a result"
        return result

    result.skipped_files = list(extraction.skipped_entries)

    processed = _process_extracted_files(
        extracted_paths=extraction.extracted_file_paths,
        case_id=intake.case_id,
        evidence_id=intake.evidence_id,
    )

    result.extracted_files = processed.extracted_files
    result.evidence_items = processed.evidence_items
    result.events = processed.events
    result.normalization_errors = processed.normalization_errors
    result.device_info = processed.device_info
    result.warnings.extend(processed.warnings)

    if not result.extracted_files:
        result.warnings.append(
            "The archive contained no supported evidence files; no events were produced"
        )

    return result
