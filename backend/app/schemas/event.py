"""
Event API schema.

This is the response shape for the Unified Event structure at the API
boundary - what a client receives when the timeline/correlation/
analysis layers hand back events. It mirrors app.models.event.Event
field-for-field so that any Event produced internally can be returned
through the API without transformation, while still keeping the
model/schema boundary explicit (see app/schemas/case.py and
app/schemas/evidence.py for the same pattern).

No database, ORM, route, or analysis logic lives here - just a
response shape with simple validation.
"""

from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field

from app.models.event import EventCategory


class EventResponse(BaseModel):
    """
    Shape of a Unified Event as returned by the API.

    Attributes:
        id: Unique identifier for this event.
        case_id: Identifier of the case this event belongs to.
        timestamp: When the event occurred (UTC).
        category: High-level bucket this event falls into (see EventCategory).
        event_type: Specific kind of event within its category
            (e.g. "app_launch", "call_incoming", "gps_fix").
        source: Where this event was derived from (e.g. a parser name
            or originating evidence id).
        description: Short, human-readable summary of what happened.
        metadata: Flexible, JSON-like bag of category/event-type-
            specific details. Kept untyped to accommodate the wide
            variety of evidence sources this system supports.
    """

    id: str
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
