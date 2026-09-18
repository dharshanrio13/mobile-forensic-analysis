"""
Evidence integrity service.

Calculates and verifies SHA-256 hashes of simulated evidence files, so
a file's integrity can be checked at any later point (e.g. "is this
still the exact same file that was originally ingested, byte for
byte?").

This service does NOT:
    - parse or interpret evidence contents (see app/parsers/)
    - extract archives (see app/services/extraction_service.py)
    - touch a database
    - define any API route
    - perform correlation or timeline logic

It only reads bytes off disk and hashes them.

Why chunked reading
--------------------
Evidence files can be large. Reading an entire file into memory with
`f.read()` before hashing it would mean memory usage scales with file
size, which doesn't hold up as evidence files grow. Instead, every
function here reads the file in fixed-size chunks and feeds each
chunk into the hash incrementally, so memory usage stays roughly
constant (~DEFAULT_CHUNK_SIZE bytes) regardless of how large the file
on disk is.

Determinism
------------
SHA-256 is a deterministic, cryptographic hash function: the exact
same file bytes always produce the exact same 64-character hex
digest, on any machine, any number of times. Reading the file in
chunks rather than all at once doesn't change this - the hash is
computed incrementally over the same byte stream either way, so
`calculate_sha256` always returns the same result for the same file
contents.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

# 64 KB - a reasonably sized read chunk that keeps memory usage low
# without making too many small read() calls for large files.
DEFAULT_CHUNK_SIZE = 65536


@dataclass
class IntegrityResult:
    """
    Outcome of checking one file's integrity.

    Attributes:
        file_path: The file that was checked, as given by the caller.
        sha256: The file's calculated SHA-256 hex digest, or None if
            hashing failed (see `error`).
        expected_sha256: The hash the caller wanted to compare
            against, if one was supplied. None if this was a plain
            "just calculate the hash" call with nothing to compare to.
        match: True if `sha256` matches `expected_sha256`, False if it
            doesn't, or None if no `expected_sha256` was supplied (so
            there was nothing to compare) or if hashing itself failed.
        success: Whether the file was read and hashed successfully.
            False means `sha256` and `match` are both None and `error`
            explains why - this function never raises for expected
            failure conditions (missing file, unreadable file); it
            reports them in the result instead.
        error: Human-readable reason hashing failed, if `success` is
            False. None otherwise.
    """

    file_path: str
    sha256: Optional[str]
    expected_sha256: Optional[str]
    match: Optional[bool]
    success: bool
    error: Optional[str] = None


def calculate_sha256(file_path: Union[str, Path], chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """
    Calculate the SHA-256 hex digest of a file, reading it in chunks.

    Args:
        file_path: Path to the file to hash.
        chunk_size: How many bytes to read per chunk. Defaults to
            DEFAULT_CHUNK_SIZE (64 KB); the resulting hash is identical
            no matter what chunk size is used, since it only affects
            how the bytes are batched, not the bytes themselves.

    Returns:
        The 64-character lowercase hex digest of the file's contents.

    Raises:
        FileNotFoundError: If `file_path` doesn't exist.
        IsADirectoryError: If `file_path` points at a directory.
        PermissionError: If the file can't be read due to permissions.
        OSError: For any other file-read failure.

    This function raises rather than swallowing errors, since it's the
    low-level building block; `verify_file_integrity` below wraps it
    with the same error handling turned into a structured result for
    callers who don't want to catch exceptions themselves.
    """
    hasher = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


def compare_hashes(current_hash: str, expected_hash: str) -> bool:
    """
    Compare two SHA-256 hex digests for equality.

    Comparison is case-insensitive and ignores surrounding whitespace,
    since hashes are sometimes copied from tools/logs that uppercase
    them or leave a trailing newline - none of that changes what hash
    was actually meant.
    """
    return current_hash.strip().lower() == expected_hash.strip().lower()


def verify_file_integrity(
    file_path: Union[str, Path],
    expected_sha256: Optional[str] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> IntegrityResult:
    """
    Calculate a file's SHA-256 hash and, if `expected_sha256` is
    given, compare against it - all wrapped into one clear,
    non-raising result.

    Args:
        file_path: Path to the file to check.
        expected_sha256: A previously recorded hash to compare the
            file's current hash against (e.g. the hash recorded at
            evidence intake time). Omit this to just calculate the
            current hash with nothing to compare it to.
        chunk_size: Passed through to `calculate_sha256`.

    Returns:
        An IntegrityResult describing what happened. This function
        never raises for expected failure conditions (a missing file,
        a path that's a directory, a permissions error) - `success`
        is False and `error` explains why instead.
    """
    path_str = str(file_path)

    try:
        actual_hash = calculate_sha256(file_path, chunk_size=chunk_size)
    except FileNotFoundError:
        return IntegrityResult(
            file_path=path_str,
            sha256=None,
            expected_sha256=expected_sha256,
            match=None,
            success=False,
            error=f"File not found: {path_str}",
        )
    except IsADirectoryError:
        return IntegrityResult(
            file_path=path_str,
            sha256=None,
            expected_sha256=expected_sha256,
            match=None,
            success=False,
            error=f"Path is a directory, not a file: {path_str}",
        )
    except PermissionError:
        return IntegrityResult(
            file_path=path_str,
            sha256=None,
            expected_sha256=expected_sha256,
            match=None,
            success=False,
            error=f"Permission denied reading file: {path_str}",
        )
    except OSError as exc:
        return IntegrityResult(
            file_path=path_str,
            sha256=None,
            expected_sha256=expected_sha256,
            match=None,
            success=False,
            error=f"Failed to read file: {exc}",
        )

    match = compare_hashes(actual_hash, expected_sha256) if expected_sha256 is not None else None

    return IntegrityResult(
        file_path=path_str,
        sha256=actual_hash,
        expected_sha256=expected_sha256,
        match=match,
        success=True,
    )
