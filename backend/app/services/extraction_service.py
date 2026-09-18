"""
Evidence extraction service.

This service has exactly one job: given a path to a simulated evidence
ZIP package, safely extract the supported evidence files it contains
into a temporary, case-specific directory, and return the resulting
file paths.

It does NOT:
    - parse or interpret the contents of the extracted JSON files
    - normalize anything into Event objects
    - perform any analysis, correlation, or timeline building
    - touch a database
    - expose an API route

Reading and normalizing the extracted files is the job of the parsers
in app/parsers/ - this service only gets the raw files safely onto
disk and hands back their paths.

Security notes
---------------
ZIP archives can contain entries crafted to escape the intended
extraction directory ("zip slip" / path traversal), e.g. an entry
named "../../etc/cron.d/evil" or an absolute path like "/etc/passwd".
This service defends against that in two independent, layered ways:

    1. Every entry name is normalized and checked to ensure the
       resolved extraction path stays inside the target directory
       before anything is written (see `_resolve_safe_target`).
    2. Regardless of (1), only the file's basename is ever used when
       writing to disk - any directory components in the archive
       entry's name are stripped. Combined with the whitelist of
       expected evidence filenames, this means a malicious path can
       never influence where a file lands, even if some future edit
       weakens check (1).

Basic zip-bomb protection is also included: both the number of entries
and the total uncompressed size are capped.
"""

import os
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.config import settings

# Evidence filenames this service will extract. Anything else found in
# the archive is skipped (not an error - a ZIP may legitimately contain
# extra files we simply don't care about).
SUPPORTED_FILENAMES = {
    "device.json",
    "app_activity.json",
    "calls.json",
    "messages.json",
    "locations.json",
    "system_logs.json",
}

# Basic zip-bomb guardrails.
_MAX_ENTRIES = 100
_MAX_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB


class UnsafeZipError(Exception):
    """Raised when a ZIP archive contains an entry that attempts path
    traversal, an absolute path, or otherwise looks unsafe to extract."""


class ZipBombError(Exception):
    """Raised when a ZIP archive exceeds the entry-count or total
    uncompressed-size guardrails."""


@dataclass
class ExtractionResult:
    """
    Result of extracting one evidence ZIP.

    Attributes:
        extracted_file_paths: Absolute paths of every supported file
            that was successfully extracted to disk. This is the
            primary output of the service.
        skipped_entries: Archive entries that were present but not
            extracted (e.g. directories, or filenames not in
            SUPPORTED_FILENAMES), each with a short reason. Not an
            error condition - just a record of what was ignored.
        extraction_dir: The case-specific temporary directory the
            files were extracted into.
    """

    extracted_file_paths: List[str] = field(default_factory=list)
    skipped_entries: List[Dict[str, str]] = field(default_factory=list)
    extraction_dir: str = ""


def _resolve_safe_target(entry_name: str, target_dir: str) -> Optional[str]:
    """
    Compute the path an archive entry would be written to, and verify
    it stays inside `target_dir`.

    Returns the resolved absolute path if safe, or None if the entry
    name is an absolute path, contains a parent-directory traversal
    component, or otherwise resolves outside of `target_dir`.
    """
    if os.path.isabs(entry_name):
        return None

    normalized = os.path.normpath(entry_name)

    if normalized.startswith("..") or normalized in (".", ""):
        return None

    candidate = os.path.join(target_dir, normalized)
    resolved_candidate = os.path.realpath(candidate)
    resolved_target = os.path.realpath(target_dir)

    if resolved_candidate != resolved_target and not resolved_candidate.startswith(
        resolved_target + os.sep
    ):
        return None

    return resolved_candidate


def _check_zip_bomb_limits(zf: zipfile.ZipFile) -> None:
    """Raise ZipBombError if the archive exceeds basic size/count guardrails."""
    infos = zf.infolist()
    if len(infos) > _MAX_ENTRIES:
        raise ZipBombError(f"Archive has too many entries ({len(infos)} > {_MAX_ENTRIES})")

    total_uncompressed = sum(info.file_size for info in infos)
    if total_uncompressed > _MAX_TOTAL_UNCOMPRESSED_BYTES:
        raise ZipBombError(
            f"Archive's total uncompressed size ({total_uncompressed} bytes) "
            f"exceeds the limit ({_MAX_TOTAL_UNCOMPRESSED_BYTES} bytes)"
        )


def extract_evidence_zip(
    zip_path: str,
    case_id: str,
    base_temp_dir: Optional[str] = None,
) -> ExtractionResult:
    """
    Safely extract supported evidence files from a ZIP into a
    case-specific temporary directory.

    Args:
        zip_path: Path to the ZIP file to extract.
        case_id: Identifier of the case this evidence belongs to. Used
            to name the extraction directory so evidence from
            different cases never lands in the same place.
        base_temp_dir: Parent directory under which the case-specific
            extraction directory is created. Defaults to
            `settings.TEMP_DIR`.

    Returns:
        An ExtractionResult with the extracted file paths, any
        skipped entries, and the directory they were extracted into.

    Raises:
        FileNotFoundError: If `zip_path` doesn't exist.
        ValueError: If `zip_path` is not a valid ZIP file.
        ZipBombError: If the archive exceeds entry-count or
            total-uncompressed-size guardrails.
        UnsafeZipError: If the archive contains an entry that attempts
            path traversal or an absolute path.
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"Not a valid ZIP file: {zip_path}")

    base_dir = base_temp_dir if base_temp_dir else settings.TEMP_DIR
    os.makedirs(base_dir, exist_ok=True)

    extraction_dir = tempfile.mkdtemp(prefix=f"case_{case_id}_", dir=base_dir)

    result = ExtractionResult(extraction_dir=extraction_dir)

    with zipfile.ZipFile(zip_path, "r") as zf:
        _check_zip_bomb_limits(zf)

        for info in zf.infolist():
            if info.is_dir():
                result.skipped_entries.append({"entry": info.filename, "reason": "directory entry"})
                continue

            safe_target = _resolve_safe_target(info.filename, extraction_dir)
            if safe_target is None:
                raise UnsafeZipError(
                    f"Refusing to extract unsafe archive entry: {info.filename!r}"
                )

            basename = os.path.basename(safe_target)
            if basename not in SUPPORTED_FILENAMES:
                result.skipped_entries.append(
                    {"entry": info.filename, "reason": f"unsupported filename: {basename}"}
                )
                continue

            # Flatten to just the basename inside extraction_dir, even
            # though _resolve_safe_target already confirmed containment.
            # This is a second, independent guarantee that a crafted
            # path can never place a file outside the intended folder.
            final_path = os.path.join(extraction_dir, basename)

            with zf.open(info, "r") as source, open(final_path, "wb") as dest:
                dest.write(source.read())

            result.extracted_file_paths.append(final_path)

    return result
