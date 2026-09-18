"""
Standalone command-line test for app/services/integrity_service.py.

Run it from the backend/ directory (with your venv active):

    python test_integrity.py

No pytest needed - this is a plain script. It creates a real temp
file, hashes it, demonstrates a matching and a mismatching hash
comparison, demonstrates that the same content hashed twice always
produces the same digest, and checks a few error cases (missing
file, a directory instead of a file). All temp files are cleaned up
automatically when the script finishes.

Exit code: 0 if every check passes, 1 if any check fails.
"""

import hashlib
import os
import sys
import tempfile

from app.services.integrity_service import (
    calculate_sha256,
    compare_hashes,
    verify_file_integrity,
)

_checks_failed = []


def check(description, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {description}")
    if not condition:
        _checks_failed.append(description)


def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # --- a small test "evidence" file with known content ---
        file_path = os.path.join(tmp_dir, "evidence_sample.json")
        original_content = b'{"note": "simulated evidence file for integrity testing"}'
        with open(file_path, "wb") as f:
            f.write(original_content)

        # The independently-computed "known correct" hash, using the
        # standard library directly (not the service under test), so
        # the demonstration doesn't just check the service against
        # itself.
        expected_hash = hashlib.sha256(original_content).hexdigest()

        print("--- HASHING A TEST FILE ---")
        calculated_hash = calculate_sha256(file_path)
        print(f"file            : {file_path}")
        print(f"calculated hash : {calculated_hash}")
        print(f"expected hash   : {expected_hash}")
        print()
        check("calculate_sha256 matches an independently computed hashlib digest", calculated_hash == expected_hash)

        print()
        print("--- MATCHING HASH ---")
        match_result = verify_file_integrity(file_path, expected_sha256=expected_hash)
        print(match_result)
        check("verify_file_integrity reports success=True for a readable file", match_result.success)
        check("verify_file_integrity reports match=True when the hash is correct", match_result.match is True)

        print()
        print("--- MISMATCHING HASH (simulating a tampered/corrupted file) ---")
        wrong_hash = "0" * 64
        mismatch_result = verify_file_integrity(file_path, expected_sha256=wrong_hash)
        print(mismatch_result)
        check("verify_file_integrity reports match=False when the hash is wrong", mismatch_result.match is False)
        check("verify_file_integrity still reports success=True (the file itself was read fine)", mismatch_result.success)

        print()
        print("--- CASE-INSENSITIVE / WHITESPACE-TOLERANT COMPARISON ---")
        messy_hash = f"  {expected_hash.upper()}\n"
        loose_match = compare_hashes(calculated_hash, messy_hash)
        print(f"compare_hashes(calculated, {messy_hash!r}) -> {loose_match}")
        check("compare_hashes tolerates case and surrounding whitespace", loose_match is True)

        print()
        print("--- DETERMINISM: hashing the same content twice ---")
        second_hash = calculate_sha256(file_path)
        check("hashing the same file twice gives the identical digest", calculated_hash == second_hash)

        print()
        print("--- ERROR HANDLING ---")
        missing_result = verify_file_integrity(os.path.join(tmp_dir, "does_not_exist.json"))
        print(missing_result)
        check("a missing file returns success=False with an error message (no exception raised)", not missing_result.success and missing_result.error)

        directory_result = verify_file_integrity(tmp_dir)
        print(directory_result)
        check("passing a directory returns success=False with an error message (no exception raised)", not directory_result.success and directory_result.error)

        print()
        print("--- LARGE-ISH FILE (confirms chunked reading works, not just tiny files) ---")
        big_file_path = os.path.join(tmp_dir, "big_evidence_file.bin")
        big_content = os.urandom(5 * 1024 * 1024)  # 5 MB of random bytes
        with open(big_file_path, "wb") as f:
            f.write(big_content)
        big_expected = hashlib.sha256(big_content).hexdigest()
        big_calculated = calculate_sha256(big_file_path, chunk_size=8192)  # force many small chunks
        check("a 5 MB file hashed in small 8 KB chunks matches the expected digest", big_calculated == big_expected)

    print()
    if _checks_failed:
        print(f"{len(_checks_failed)} check(s) FAILED:")
        for description in _checks_failed:
            print(f"  - {description}")
        sys.exit(1)
    else:
        print("All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()