"""
Unified Event data model.

This is the central data structure of the forensic analysis system.
Every piece of evidence - regardless of its original source (an app
database, a call log, a location history file, a message thread,
etc.) - is eventually normalized into one or more Event objects.

Downstream components (normalization service, timeline service,
correlation service, analysis routes) are all written against this
one shape, rather than against dozens of source-specific formats.
That's the entire point of this model: it decouples "what kind of
evidence this came from" from "how the rest of the system reasons
about it."

This is a plain Pydantic model, NOT a database model - there is no
database, ORM, or persistence layer in this project. No relationships,
foreign keys, or analysis logic live here; this file only defines the
shape of an Event.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    """
    High-level bucket an event falls into.

    Kept intentionally broad and evidence-source-agnostic so new
    evidence parsers can map into these categories without requiring
    changes to the timeline/correlation/analysis layers.
    """

    APP = "app"
    CALL = "call"
    MESSAGE = "message"
    LOCATION = "location"
    CONTACT = "contact"
    MEDIA = "media"
    NETWORK = "network"
    SYSTEM = "system"
    OTHER = "other"


class Event(BaseModel):
    """
    A single normalized, timestamped occurrence extracted from evidence.

    Attributes:
        id: Unique identifier for this event.
        case_id: Identifier of the case this event belongs to.
        timestamp: When the event occurred (UTC).
        category: High-level bucket this event falls into (see EventCategory).
        event_type: Specific kind of event within its category
            (e.g. "app_launch", "call_incoming", "gps_fix"). Kept as a
            free-form string rather than an enum since new evidence
            parsers will keep introducing new event types over time.
        source: Where this event was derived from (e.g. the originating
            evidence filename/id, or a parser name like
            "whatsapp_parser" or "call_log_parser").
        description: Short, human-readable summary of what happened.
        metadata: Flexible, JSON-like bag for any category/event-type-
            specific details that don't belong in the fixed fields
            above (e.g. phone numbers, coordinates, app package names,
            message content, duration). Because evidence types vary so
            widely, this is intentionally untyped rather than forcing
            every possible field onto the base Event.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    case_id: str
    timestamp: datetime
    category: EventCategory
    event_type: str
    source: str
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id": "9e2a4b1c-6d3f-4a2e-8b7c-1f0d9e8a7b6c",
                "case_id": "CASE-2026-0042",
                "timestamp": "2026-09-18T10:15:30Z",
                "category": "call",
                "event_type": "call_incoming",
                "source": "call_log_parser",
                "description": "Incoming call from +1-555-0199",
                "metadata": {
                    "phone_number": "+1-555-0199",
                    "duration_seconds": 184,
                    "call_direction": "incoming",
                },
            }
        }
