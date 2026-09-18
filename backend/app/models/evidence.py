"""
Evidence data model.

This module defines a lightweight, Pydantic-based representation of a
simulated mobile forensic evidence item. It is a pure data model:
no database, no ORM, and no CRUD logic live here.
"""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    """Enumerates the kinds of evidence artifacts this model can represent."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    CALL_LOG = "call_log"
    MESSAGE_LOG = "message_log"
    CONTACT_LIST = "contact_list"
    APPLICATION_DATA = "application_data"
    OTHER = "other"


class Evidence(BaseModel):
    """
    Represents a single piece of simulated mobile forensic evidence.

    Attributes:
        id: Unique identifier for this evidence record.
        case_id: Identifier of the case this evidence belongs to.
        filename: Original name of the evidence file.
        evidence_type: Category describing what kind of artifact this is.
        file_path: Location (path or URI) where the evidence file is stored.
        uploaded_at: Timestamp of when the evidence was uploaded/ingested.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    case_id: str
    filename: str
    evidence_type: EvidenceType
    file_path: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

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
