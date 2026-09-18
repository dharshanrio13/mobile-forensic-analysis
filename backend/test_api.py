"""
test_api.py

A standalone test script for the Mobile Device Forensic Analysis
System backend. It talks to your ALREADY-RUNNING server over HTTP
(it does not import any app code directly), so it exercises exactly
what a real client would see.

Requirements:
    pip install requests

Usage:
    1. Start your server in one terminal:
           uvicorn main:app --reload
    2. In another terminal, run this script:
           python test_api.py

What it checks:
    1. POST /cases                          - create a case
    2. GET  /cases                          - the new case appears in the list
    3. GET  /cases/{case_id}                - fetch that case by id
    4. GET  /cases/{bad_id}                 - returns 404
    5. POST /cases/{case_id}/evidence       - upload a sample evidence ZIP
                                               (built in-memory, no external
                                               file needed) and confirm the
                                               expected JSON files were
                                               extracted
    6. POST /cases/{bad_id}/evidence        - returns 404 (case check runs
                                               before the upload is processed)
    7. POST /cases/{case_id}/evidence       - uploading a non-ZIP file
                                               returns 400

Each check prints PASS/FAIL. The script exits with code 0 if everything
passed, or 1 if anything failed, so it can be used in a simple CI step
too.
"""

import io
import json
import sys
import zipfile

import requests

BASE_URL = "http://127.0.0.1:8000"

_failures = []


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures."""
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}" + (f" -- {detail}" if detail else ""))
        _failures.append(label)


def build_sample_evidence_zip() -> bytes:
    """
    Build a small, valid simulated-evidence ZIP entirely in memory -
    no external file needed to run this script.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "app_activity.json",
            json.dumps([{"timestamp": "2026-09-17T09:00:00+05:30", "app": "WhatsApp", "action": "OPEN"}]),
        )
        zf.writestr(
            "calls.json",
            json.dumps(
                [{"timestamp": "2026-09-17T09:15:00+05:30", "contact": "+1-555-0199", "direction": "incoming"}]
            ),
        )
        zf.writestr(
            "locations.json",
            json.dumps([{"timestamp": "2026-09-17T09:20:00+05:30", "latitude": 12.6271, "longitude": 80.1927}]),
        )
        # A file that should be SKIPPED (not in the supported filename list).
        zf.writestr("readme.txt", "not evidence, should be skipped by the extraction service")
    buffer.seek(0)
    return buffer.read()


def main() -> int:
    print(f"Testing API at {BASE_URL}\n")

    # --- Sanity check: is the server even up? ---
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        check("Server is reachable (GET /health)", health.status_code == 200, health.text)
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] Could not connect to {BASE_URL}. Is `uvicorn main:app --reload` running?")
        return 1

    # --- 1. Create a case ---
    create_resp = requests.post(
        f"{BASE_URL}/cases",
        json={"name": "Phone Seizure 04-2026", "description": "Test case created by test_api.py"},
    )
    check("POST /cases returns 201", create_resp.status_code == 201, create_resp.text)

    case = create_resp.json() if create_resp.status_code == 201 else {}
    case_id = case.get("id")
    check("Created case has an id", bool(case_id))
    check("Created case has name/description/created_at", all(k in case for k in ("name", "description", "created_at")))

    if not case_id:
        print("\nCannot continue further tests without a valid case_id.")
        _print_summary()
        return 1

    # --- 2. List cases and confirm the new one is present ---
    list_resp = requests.get(f"{BASE_URL}/cases")
    check("GET /cases returns 200", list_resp.status_code == 200, list_resp.text)
    case_ids_in_list = [c.get("id") for c in list_resp.json()] if list_resp.status_code == 200 else []
    check("New case appears in GET /cases", case_id in case_ids_in_list)

    # --- 3. Get the case by id ---
    get_resp = requests.get(f"{BASE_URL}/cases/{case_id}")
    check("GET /cases/{id} returns 200", get_resp.status_code == 200, get_resp.text)
    check("GET /cases/{id} returns the same case", get_resp.status_code == 200 and get_resp.json().get("id") == case_id)

    # --- 4. Get a nonexistent case ---
    missing_resp = requests.get(f"{BASE_URL}/cases/this-case-does-not-exist")
    check("GET /cases/{bad_id} returns 404", missing_resp.status_code == 404, missing_resp.text)

    # --- 5. Upload a sample evidence ZIP to the real case ---
    zip_bytes = build_sample_evidence_zip()
    upload_resp = requests.post(
        f"{BASE_URL}/cases/{case_id}/evidence",
        files={"file": ("simulated_mobile_evidence_001.zip", zip_bytes, "application/zip")},
    )
    check("POST /cases/{id}/evidence returns 201", upload_resp.status_code == 201, upload_resp.text)

    if upload_resp.status_code == 201:
        result = upload_resp.json()
        check("Upload result reports success", result.get("success") is True)
        check("Upload result case_id matches", result.get("case_id") == case_id)
        check("Upload result has an evidence_id", bool(result.get("evidence_id")))
        check("Upload result has a saved_path", bool(result.get("saved_path")))

        extracted = result.get("extracted_files", [])
        check("3 supported files were extracted", len(extracted) == 3, f"got {len(extracted)}: {extracted}")
        check(
            "app_activity.json was extracted",
            any(path.endswith("app_activity.json") for path in extracted),
        )
        check("calls.json was extracted", any(path.endswith("calls.json") for path in extracted))
        check("locations.json was extracted", any(path.endswith("locations.json") for path in extracted))

        skipped = result.get("skipped_entries", [])
        check("readme.txt was skipped, not extracted", any("readme.txt" in entry.get("entry", "") for entry in skipped))

    # --- 6. Upload evidence against a nonexistent case ---
    bad_case_upload = requests.post(
        f"{BASE_URL}/cases/this-case-does-not-exist/evidence",
        files={"file": ("evidence.zip", zip_bytes, "application/zip")},
    )
    check("POST /cases/{bad_id}/evidence returns 404", bad_case_upload.status_code == 404, bad_case_upload.text)

    # --- 7. Upload a non-ZIP file to a real case ---
    bad_file_upload = requests.post(
        f"{BASE_URL}/cases/{case_id}/evidence",
        files={"file": ("notes.txt", b"just some text, not a zip", "text/plain")},
    )
    check("POST with a non-ZIP file returns 400", bad_file_upload.status_code == 400, bad_file_upload.text)

    return _print_summary()


def _print_summary() -> int:
    print("\n" + "-" * 50)
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for label in _failures:
            print(f"  - {label}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
