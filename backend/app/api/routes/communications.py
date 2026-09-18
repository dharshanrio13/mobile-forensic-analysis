"""
Communications route.

Defines GET /cases/{case_id}/communications - the CALL and MESSAGE
events for a case.

Records are returned as Unified Events (the same EventResponse shape the
timeline uses), so no fields are invented here. A frontend tells calls
and messages apart via `category` ("call" or "message"); the per-record
details it needs (caller/receiver/sender/direction/duration/content) are
already in each event's `metadata`, exactly as the existing call and
message parsers wrote them.
"""

from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.routes.cases import get_case_or_404
from app.models.event import EventCategory
from app.schemas.event import EventResponse
from app.services.timeline_service import build_timeline
from app.state import app_state

router = APIRouter(prefix="/cases", tags=["communications"])

_COMMUNICATION_CATEGORIES = {EventCategory.CALL.value, EventCategory.MESSAGE.value}


class CommunicationsResponse(BaseModel):
    """Calls and messages for a case, with simple observed counts."""

    case_id: str
    total: int = Field(..., description="Number of communication records returned.")
    total_calls: int
    total_messages: int
    records: List[EventResponse] = Field(
        ..., description="Call and message events in chronological order."
    )


@router.get(
    "/{case_id}/communications",
    response_model=CommunicationsResponse,
    summary="Call and message records for a case",
)
def get_communications(
    case_id: str,
    category: Optional[str] = Query(
        None,
        pattern="^(call|message)$",
        description="Restrict to just 'call' or just 'message'. Omit for both.",
    ),
) -> CommunicationsResponse:
    """
    Return the case's call and message events in chronological order.

    Returns empty results when the case has no communications, and 404
    when the case doesn't exist.
    """
    get_case_or_404(case_id)

    wanted = {category} if category else _COMMUNICATION_CATEGORIES
    events = [
        event
        for event in build_timeline(app_state.get_events(case_id))
        if str(event.category) in wanted
    ]

    call_count = sum(1 for event in events if str(event.category) == EventCategory.CALL.value)
    message_count = sum(1 for event in events if str(event.category) == EventCategory.MESSAGE.value)

    return CommunicationsResponse(
        case_id=case_id,
        total=len(events),
        total_calls=call_count,
        total_messages=message_count,
        records=[EventResponse(**event.model_dump()) for event in events],
    )
