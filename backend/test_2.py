import zipfile, json
from app.services.extraction_service import extract_evidence_zip
zi_zip = zipfile.ZipFile("evil_evidence.zip", "w")
zi_zip.writestr("calls.json", "[]")
zi_zip.writestr("../../etc/evil_cron", "malicious payload")
zi_zip.close()

extract_evidence_zip("evil_evidence.zip", case_id="CASE-TEST-002")