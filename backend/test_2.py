import os
import shutil
import zipfile
import json

from app.services.evidence_service import intake_evidence_package
from app.core.config import settings


def make_test_zip(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("app_activity.json", json.dumps([
            {"timestamp": "2026-09-17T09:00:00+05:30", "app": "WhatsApp", "action": "OPEN"}
        ]))
        zf.writestr("calls.json", json.dumps([
            {"timestamp": "2026-09-17T09:15:00+05:30", "contact": "+1-555-0199", "direction": "incoming"}
        ]))


def test_valid_intake():
    make_test_zip("valid_evidence.zip")
    result = intake_evidence_package("valid_evidence.zip", original_filename="evidence.zip")
    assert result.success is True
    assert result.case_id.startswith("CASE-")
    assert os.path.isfile(result.saved_path)
    assert len(result.extraction.extracted_file_paths) == 2
    print("test_valid_intake: PASS")


def test_reuses_existing_case_id():
    make_test_zip("valid_evidence.zip")
    result = intake_evidence_package("valid_evidence.zip", original_filename="evidence.zip", case_id="CASE-2026-0042")
    assert result.case_id == "CASE-2026-0042"
    print("test_reuses_existing_case_id: PASS")


def test_rejects_bad_extension():
    result = intake_evidence_package("valid_evidence.zip", original_filename="evidence.rar")
    assert result.success is False
    assert "extension" in result.error.lower()
    print("test_rejects_bad_extension: PASS")


def test_rejects_missing_source_file():
    result = intake_evidence_package("does_not_exist.zip", original_filename="evidence.zip")
    assert result.success is False
    assert "not found" in result.error.lower()
    print("test_rejects_missing_source_file: PASS")


def cleanup():
    if os.path.exists("valid_evidence.zip"):
        os.remove("valid_evidence.zip")
    for d in (settings.UPLOAD_DIR, settings.TEMP_DIR):
        if os.path.isdir(d):
            shutil.rmtree(d)


if __name__ == "__main__":
    test_valid_intake()
    test_reuses_existing_case_id()
    test_rejects_bad_extension()
    test_rejects_missing_source_file()
    cleanup()
    print("\nAll tests passed.")