"""
Locations route.

Defines GET /cases/{case_id}/locations - the location-category events
for a case, flattened into a shape a frontend map can consume directly.

The latitude/longitude values come straight from the metadata the
existing location parser produced (which already validated that they
are numeric and within valid geographic bounds). This route does not
re-validate, re-project, cluster, or render anything - map rendering is
entirely the frontend's job.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.routes.cases import get_case_or_404
from app.models.event import EventCategory
from app.services.timeline_service import build_timeline
from app.state import app_state

router = APIRouter(prefix="/cases", tags=["locations"])


class LocationRecord(BaseModel):
    """One recorded location point, derived from a LOCATION Event."""

    id: str = Field(..., description="Id of the underlying Unified Event.")
    timestamp: datetime
    latitude: float
    longitude: float
    source: str = Field(..., description="Parser the event came from.")
    event_type: str
    description: str
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Full location metadata (may include label, accuracy, provider).",
    )


@router.get(
    "/{case_id}/locations",
    response_model=List[LocationRecord],
    summary="Location records for a case, ready for a map",
)
def get_locations(
    case_id: str,
    limit: Optional[int] = Query(
        None, ge=1, description="Return at most this many records (earliest first)."
    ),
) -> List[LocationRecord]:
    """
    Return the case's location events in chronological order.

    Events whose metadata is missing a usable latitude/longitude pair
    are skipped rather than returned with nulls, so every record in the
    response is directly plottable. Returns an empty list when there are
    no locations, and 404 when the case doesn't exist.
    """
    get_case_or_404(case_id)

    events = app_state.get_events(case_id)
    location_events = [
        event for event in build_timeline(events) if str(event.category) == EventCategory.LOCATION.value
    ]

    records: List[LocationRecord] = []
    for event in location_events:
        metadata = event.metadata or {}
        latitude = metadata.get("latitude")
        longitude = metadata.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            continue

        records.append(
            LocationRecord(
                id=event.id,
                timestamp=event.timestamp,
                latitude=float(latitude),
                longitude=float(longitude),
                source=event.source,
                event_type=event.event_type,
                description=event.description,
                metadata=metadata,
            )
        )

    if limit is not None:
        records = records[:limit]

    return records
