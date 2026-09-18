"""
Evidence API schemas.

These are response shapes for the API boundary - what gets sent back
to a client after evidence has been (simulated as) uploaded, or when
a client asks for evidence metadata. They are separate from
app.models.evidence.Evidence, which is the internal data model used
throughout the rest of the application.

No database, ORM, upload logic, parsing, or route logic lives here -
just response shapes with simple validation.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceType


class EvidenceUploadResponse(BaseModel):
    """
    Shape returned to a client immediately after evidence has been
    (simulated as) uploaded/ingested.

    Includes everything the client needs to know the upload succeeded
    and where the resulting record lives - the full picture of the
    evidence item as the application now understands it.
    """

    id: str
    case_id: str
    filename: str
    evidence_type: EvidenceType
    file_path: str
    uploaded_at: datetime

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "3f9a1c2e-8b4d-4e6a-9c1a-7d2f5b6e9a10",
                "case_id": "CASE-2026-0042",
                "filename": "call_log_export.xml",
                "evidence_type": "call_log",
                "file_path": "/evidence/case-0042/call_log_export.xml",
                "uploaded_at": "2026-09-18T10:15:30Z",
            }
        }


class EvidenceMetadata(BaseModel):
    """
    Lighter-weight shape describing an evidence item, without exposing
    where the file physically lives.

    Useful for listing/browsing evidence (e.g. "show me everything
    uploaded for this case") where a client needs to identify and
    reference evidence items but doesn't need - or shouldn't
    necessarily be given - the underlying storage path.
    """

    id: str
    case_id: str
    filename: str
    evidence_type: EvidenceType
    uploaded_at: datetime

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "3f9a1c2e-8b4d-4e6a-9c1a-7d2f5b6e9a10",
                "case_id": "CASE-2026-0042",
                "filename": "call_log_export.xml",
                "evidence_type": "call_log",
                "uploaded_at": "2026-09-18T10:15:30Z",
            }
        }
