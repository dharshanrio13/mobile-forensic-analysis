"""
Manual test-run script for the Mobile Device Forensic Analysis System
backend.

This is NOT pytest - it's a plain script you run directly, so no test
framework needs to be installed. It walks through every module in the
backend (config, models, parsers, services, and the FastAPI app
itself) and does a small real exercise of each one: importing it,
constructing real objects, and checking the result is what's expected.

Run it from the backend/ directory (with your venv active):

    python test_run.py

What it does when a file doesn't exist yet:
    Each test is wrapped so a missing module is reported as SKIPPED,
    not FAILED - this script is meant to be run at any point in the
    project, including before every file exists yet.

Exit code:
    0 if everything that ran passed, 1 if anything failed. Skips
    don't affect the exit code.
"""

import sys
import tempfile
import os
import zipfile
from datetime import datetime, timezone

# ---------------------------------------------------------------------
# tiny test runner
# ---------------------------------------------------------------------

_results = []  # list of (name, "PASS" | "FAIL" | "SKIP", detail)


def run_test(name, fn):
    try:
        fn()
        _results.append((name, "PASS", ""))
    except ModuleNotFoundError as exc:
        _results.append((name, "SKIP", f"module not found yet: {exc}"))
    except AssertionError as exc:
        _results.append((name, "FAIL", str(exc)))
    except Exception as exc:  # noqa: BLE001 - report anything unexpected as a failure
        _results.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))


# ---------------------------------------------------------------------
# app/core/config.py
# ---------------------------------------------------------------------

def test_config_defaults():
    from app.core.config import settings

    assert isinstance(settings.APP_NAME, str) and settings.APP_NAME
    assert isinstance(settings.DEBUG, bool)
    assert isinstance(settings.UPLOAD_DIR, str) and settings.UPLOAD_DIR
    assert isinstance(settings.TEMP_DIR, str) and settings.TEMP_DIR


def test_config_env_override():
    import importlib
    import app.core.config as config_module

    os.environ["APP_NAME"] = "Test Override Name"
    try:
        importlib.reload(config_module)
        assert config_module.settings.APP_NAME == "Test Override Name"
    finally:
        del os.environ["APP_NAME"]
        importlib.reload(config_module)  # restore normal defaults for later tests


# ---------------------------------------------------------------------
# app/models/*.py
# ---------------------------------------------------------------------

def test_model_case():
    from app.models.case import Case

    case = Case(name="Case 001", description="Simulated device analysis")
    assert case.id
    assert case.name == "Case 001"
    assert case.created_at is not None


def test_model_evidence():
    from app.models.evidence import Evidence, EvidenceType

    ev = Evidence(
        case_id="CASE-001",
        filename="call_log.json",
        evidence_type=EvidenceType.CALL_LOG,
        file_path="/uploads/call_log.json",
    )
    assert ev.id
    assert ev.case_id == "CASE-001"
    assert ev.uploaded_at is not None


def test_model_event():
    from app.models.event import Event, EventCategory

    ev = Event(
        case_id="CASE-001",
        timestamp=datetime.now(timezone.utc),
        category=EventCategory.CALL,
        event_type="call_incoming",
        source="call_log_parser",
        description="Incoming call",
        metadata={"duration": 42},
    )
    assert ev.id
    assert ev.metadata["duration"] == 42


# ---------------------------------------------------------------------
# app/parsers/*.py
# ---------------------------------------------------------------------

def test_parser_app():
    from app.parsers.app_parser import parse_app_activity_batch

    records = [{"timestamp": "2026-09-17T09:00:00Z", "app": "WhatsApp", "action": "OPEN"}]
    result = parse_app_activity_batch(records, case_id="CASE-001")
    assert len(result.events) == 1
    assert result.events[0].category == "app"
    assert not result.errors


def test_parser_call():
    from app.parsers.call_parser import parse_call_batch

    records = [{"timestamp": "2026-09-17T10:00:00Z", "contact": "+1-555-0199", "direction": "incoming"}]
    result = parse_call_batch(records, case_id="CASE-001")
    assert len(result.events) == 1
    assert result.events[0].event_type == "call_incoming"


def test_parser_message():
    from app.parsers.message_parser import parse_message_batch

    records = [{"timestamp": "2026-09-17T11:00:00Z", "contact": "+1-555-0199", "direction": "outgoing", "content": "hi"}]
    result = parse_message_batch(records, case_id="CASE-001")
    assert len(result.events) == 1
    assert result.events[0].metadata["content"] == "hi"


def test_parser_location():
    from app.parsers.location_parser import parse_location_batch

    records = [{"timestamp": "2026-09-17T12:00:00Z", "latitude": 12.6271, "longitude": 80.1927}]
    result = parse_location_batch(records, case_id="CASE-001")
    assert len(result.events) == 1
    assert result.events[0].event_type == "gps_fix"

    # also check an out-of-range coordinate is rejected, not silently accepted
    bad_records = [{"timestamp": "2026-09-17T12:00:00Z", "latitude": 999, "longitude": 80.1927}]
    bad_result = parse_location_batch(bad_records, case_id="CASE-001")
    assert len(bad_result.events) == 0
    assert len(bad_result.errors) == 1


def test_parser_system_log():
    from app.parsers.system_log_parser import parse_system_log_batch

    records = [{"timestamp": "2026-09-17T13:00:00Z", "level": "INFO", "event": "boot_completed"}]
    result = parse_system_log_batch(records, case_id="CASE-001")
    assert len(result.events) == 1
    assert result.events[0].event_type == "system_boot_completed"


# ---------------------------------------------------------------------
# app/services/extraction_service.py
# ---------------------------------------------------------------------

def test_extraction_service():
    from app.services.extraction_service import extract_evidence_zip

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = os.path.join(tmp_dir, "evidence.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("calls.json", "[]")
            zf.writestr("not_evidence.txt", "should be skipped")

        result = extract_evidence_zip(zip_path, case_id="CASE-001", base_temp_dir=tmp_dir)
        assert len(result.extracted_file_paths) == 1
        assert result.extracted_file_paths[0].endswith("calls.json")
        assert len(result.skipped_entries) == 1


def test_extraction_service_rejects_path_traversal():
    from app.services.extraction_service import extract_evidence_zip, UnsafeZipError

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = os.path.join(tmp_dir, "evil.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../etc/calls.json", "[]")

        raised = False
        try:
            extract_evidence_zip(zip_path, case_id="CASE-002", base_temp_dir=tmp_dir)
        except UnsafeZipError:
            raised = True
        assert raised, "expected UnsafeZipError for a path-traversal entry"


# ---------------------------------------------------------------------
# app/services/evidence_service.py
# ---------------------------------------------------------------------

def test_evidence_service_intake():
    from app.services.evidence_service import intake_evidence_package
    import app.core.config as config_module

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Point the service's upload/temp dirs at a throwaway location
        # for this test only, so it never touches your real uploads/.
        config_module.settings.UPLOAD_DIR = os.path.join(tmp_dir, "uploads")
        config_module.settings.TEMP_DIR = os.path.join(tmp_dir, "temp")

        source_zip = os.path.join(tmp_dir, "incoming.zip")
        with zipfile.ZipFile(source_zip, "w") as zf:
            zf.writestr("calls.json", "[]")

        result = intake_evidence_package(source_zip, original_filename="incoming.zip")
        assert result.success, result.error
        assert os.path.isfile(result.saved_path)
        assert result.extraction is not None
        assert len(result.extraction.extracted_file_paths) == 1


def test_evidence_service_rejects_bad_extension():
    from app.services.evidence_service import intake_evidence_package

    with tempfile.TemporaryDirectory() as tmp_dir:
        source_file = os.path.join(tmp_dir, "not_a_zip.txt")
        with open(source_file, "w") as f:
            f.write("hello")

        result = intake_evidence_package(source_file, original_filename="not_a_zip.txt")
        assert not result.success
        assert "extension" in result.error.lower()


# ---------------------------------------------------------------------
# app/services/normalization_service.py
# ---------------------------------------------------------------------

def test_normalization_service_each_category():
    from app.services.normalization_service import EvidenceCategory, normalize_records

    cases = {
        EvidenceCategory.APP: [{"timestamp": "2026-09-17T09:00:00Z", "app": "WhatsApp", "action": "OPEN"}],
        EvidenceCategory.CALL: [{"timestamp": "2026-09-17T10:00:00Z", "contact": "+1", "direction": "incoming"}],
        EvidenceCategory.MESSAGE: [{"timestamp": "2026-09-17T11:00:00Z", "contact": "+1", "content": "hi"}],
        EvidenceCategory.LOCATION: [{"timestamp": "2026-09-17T12:00:00Z", "latitude": 1.0, "longitude": 1.0}],
        EvidenceCategory.SYSTEM_LOG: [{"timestamp": "2026-09-17T13:00:00Z", "message": "boot"}],
    }
    for category, records in cases.items():
        result = normalize_records(category, records, case_id="CASE-001")
        assert len(result.events) == 1, f"{category} produced no event"
        assert result.events[0].case_id == "CASE-001"


def test_normalization_service_package_and_determinism():
    from app.services.normalization_service import EvidenceCategory, normalize_evidence_package

    package = {
        EvidenceCategory.LOCATION: [{"timestamp": "2026-09-17T12:00:00Z", "latitude": 1.0, "longitude": 1.0}],
        EvidenceCategory.APP: [{"timestamp": "2026-09-17T09:00:00Z", "app": "WhatsApp", "action": "OPEN"}],
    }
    result_1 = normalize_evidence_package("CASE-001", package)
    result_2 = normalize_evidence_package("CASE-001", package)

    categories_1 = [e.category for e in result_1.events]
    categories_2 = [e.category for e in result_2.events]
    assert categories_1 == categories_2, "output order should be deterministic"
    assert categories_1 == ["app", "location"], "app should come before location regardless of input dict order"


# ---------------------------------------------------------------------
# app/main.py
# ---------------------------------------------------------------------

def test_main_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------
# run everything
# ---------------------------------------------------------------------

ALL_TESTS = [
    ("config: defaults load", test_config_defaults),
    ("config: env var override", test_config_env_override),
    ("models: Case", test_model_case),
    ("models: Evidence", test_model_evidence),
    ("models: Event", test_model_event),
    ("parsers: app_parser", test_parser_app),
    ("parsers: call_parser", test_parser_call),
    ("parsers: message_parser", test_parser_message),
    ("parsers: location_parser", test_parser_location),
    ("parsers: system_log_parser", test_parser_system_log),
    ("services: extraction_service", test_extraction_service),
    ("services: extraction_service rejects path traversal", test_extraction_service_rejects_path_traversal),
    ("services: evidence_service intake", test_evidence_service_intake),
    ("services: evidence_service rejects bad extension", test_evidence_service_rejects_bad_extension),
    ("services: normalization_service per category", test_normalization_service_each_category),
    ("services: normalization_service package + determinism", test_normalization_service_package_and_determinism),
    ("app: /health endpoint", test_main_health_endpoint),
]


def main():
    for name, fn in ALL_TESTS:
        run_test(name, fn)

    name_width = max(len(name) for name, _, _ in _results)
    for name, status, detail in _results:
        marker = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
        line = f"{marker} {name.ljust(name_width)}"
        if detail:
            line += f"  -  {detail}"
        print(line)

    passed = sum(1 for _, status, _ in _results if status == "PASS")
    failed = sum(1 for _, status, _ in _results if status == "FAIL")
    skipped = sum(1 for _, status, _ in _results if status == "SKIP")

    print()
    print(f"{passed} passed, {failed} failed, {skipped} skipped (of {len(_results)} total)")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
