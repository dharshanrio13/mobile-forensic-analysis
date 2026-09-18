"""
Analysis route.

Defines GET /cases/{case_id}/analysis - the deterministic correlation
results for a case.

All correlation logic belongs to app.services.correlation_service and is
called, not reimplemented. That service applies three explicit rules
(time_window, shared_identifier, location_proximity) and produces stable,
reproducible correlation ids for the same input.

FORENSIC WORDING: results describe OBSERVED patterns only - that events
occurred close together in time, reference the same identifier, or that a
location record sits near other activity in time. Nothing here asserts,
implies, or scores guilt, intent, identity or wrongdoing, and no
confidence value is invented. Each result carries its raw context so a
human reviewer can evaluate the pattern themselves.
"""

from collections import Counter
from datetime import timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.routes.cases import get_case_or_404
from app.services.correlation_service import DEFAULT_TIME_WINDOW, correlate_events
from app.state import app_state

router = APIRouter(prefix="/cases", tags=["analysis"])

ANALYSIS_DISCLAIMER = (
    "Correlations below record observed patterns between events - closeness in "
    "time, a shared identifier, or a location record near other activity in time. "
    "They are candidates for human review and are not a determination that the "
    "events are actually connected, nor any statement about conduct or intent."
)


class CorrelationItem(BaseModel):
    """One potential relationship, exactly as the correlation service produced it."""

    correlation_id: str = Field(..., description="Deterministic, rule-prefixed id, e.g. 'CORR-TW-0001'.")
    related_event_ids: List[str] = Field(..., description="Ids of the events flagged as potentially related.")
    reason: str = Field(..., description="Neutral explanation of the observed pattern.")
    rule: str = Field(..., description="'time_window', 'shared_identifier' or 'location_proximity'.")
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Supporting facts (timestamps, gaps, identifier values)."
    )


class AnalysisResponse(BaseModel):
    """Correlation analysis for one case."""

    case_id: str
    total_events: int
    total_correlations: int
    correlations: List[CorrelationItem]
    summary: Dict[str, Any] = Field(
        ..., description="Counts per rule, counts per event category, and the time window used."
    )
    disclaimer: str


@router.get(
    "/{case_id}/analysis",
    response_model=AnalysisResponse,
    summary="Deterministic correlation analysis for a case",
)
def get_analysis(
    case_id: str,
    time_window_minutes: int = Query(
        int(DEFAULT_TIME_WINDOW.total_seconds() // 60),
        ge=1,
        le=1440,
        description="Window used by the time_window and location_proximity rules.",
    ),
) -> AnalysisResponse:
    """
    Run every correlation rule over the case's normalized events.

    Returns an empty correlation list when the case has fewer than two
    events, and 404 when the case doesn't exist.
    """
    get_case_or_404(case_id)

    events = app_state.get_events(case_id)
    correlations = correlate_events(events, time_window=timedelta(minutes=time_window_minutes))

    rule_counts = Counter(correlation.rule for correlation in correlations)
    category_counts = Counter(str(event.category) for event in events)

    return AnalysisResponse(
        case_id=case_id,
        total_events=len(events),
        total_correlations=len(correlations),
        correlations=[
            CorrelationItem(
                correlation_id=correlation.correlation_id,
                related_event_ids=correlation.related_event_ids,
                reason=correlation.reason,
                rule=correlation.rule,
                context=correlation.context,
            )
            for correlation in correlations
        ],
        summary={
            "time_window_minutes": time_window_minutes,
            "correlations_by_rule": dict(rule_counts),
            "events_by_category": dict(category_counts),
        },
        disclaimer=ANALYSIS_DISCLAIMER,
    )
