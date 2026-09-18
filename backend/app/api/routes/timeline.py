"""
Timeline route.

Defines GET /cases/{case_id}/timeline - the chronologically ordered
Unified Events for a case.

All sorting and time-range filtering is delegated to
app.services.timeline_service.build_timeline. This route only reads
state, applies the category/event_type selection, and shapes the
response.
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.routes.cases import get_case_or_404
from app.models.event import Event, EventCategory
from app.schemas.event import EventResponse
from app.services.timeline_service import SortOrder, build_timeline
from app.state import app_state

router = APIRouter(prefix="/cases", tags=["timeline"])


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    Make a query-supplied datetime timezone-aware.

    Event timestamps are always timezone-aware (the parsers produce
    them that way, and processing_service backfills UTC for anything
    that arrived without an offset). Comparing an aware datetime with a
    naive one raises TypeError in Python, so a client that passes
    `2026-09-17T09:00:00` without an offset has it read as UTC rather
    than causing an error.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _matches(event: Event, category: Optional[str], event_type: Optional[str]) -> bool:
    """Category/event_type selection, both optional and case-insensitive."""
    if category is not None and str(event.category).lower() != category.lower():
        return False
    if event_type is not None and event.event_type.lower() != event_type.lower():
        return False
    return True


@router.get(
    "/{case_id}/timeline",
    response_model=List[EventResponse],
    summary="Chronological Unified Event timeline for a case",
)
def get_timeline(
    case_id: str,
    category: Optional[EventCategory] = Query(
        None, description="Only return events in this category."
    ),
    event_type: Optional[str] = Query(
        None, description="Only return events with this event_type (e.g. 'call_incoming')."
    ),
    start_time: Optional[datetime] = Query(
        None, description="Exclude events before this ISO-8601 time (inclusive bound)."
    ),
    end_time: Optional[datetime] = Query(
        None, description="Exclude events after this ISO-8601 time (inclusive bound)."
    ),
    order: SortOrder = Query(SortOrder.ASCENDING, description="Sort direction."),
) -> List[EventResponse]:
    """
    Return the case's normalized events, sorted chronologically.

    Returns an empty list when the case exists but has no events yet,
    and 404 when the case doesn't exist.
    """
    get_case_or_404(case_id)

    events = app_state.get_events(case_id)

    try:
        timeline = build_timeline(
            events,
            order=order,
            start_time=_as_utc(start_time),
            end_time=_as_utc(end_time),
        )
    except TypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not apply the requested time range: {exc}",
        ) from exc

    category_value = category.value if category is not None else None
    selected = [event for event in timeline if _matches(event, category_value, event_type)]

    return [EventResponse(**event.model_dump()) for event in selected]
