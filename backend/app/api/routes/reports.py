"""
Report route.

Defines GET /cases/{case_id}/report - the structured forensic report
for a case.

Report assembly belongs entirely to
app.services.report_service.generate_forensic_report. This route only
gathers what that service needs from application state (the case, its
evidence items, its normalized events, its normalization errors) plus
freshly-computed correlations from the correlation service, and hands
them over.

The report separates OBSERVED EVIDENCE from CALCULATED ANALYSIS from
POTENTIALLY RELATED EVENTS, and carries its own disclaimer - none of
that wording is altered here.
"""

from dataclasses import asdict
from typing import Any, Dict

from fastapi import APIRouter

from app.api.routes.cases import get_case_or_404
from app.services.correlation_service import correlate_events
from app.services.report_service import generate_forensic_report
from app.state import app_state

router = APIRouter(prefix="/cases", tags=["reports"])


@router.get(
    "/{case_id}/report",
    response_model=Dict[str, Any],
    summary="Structured forensic report for a case",
)
def get_report(case_id: str) -> Dict[str, Any]:
    """
    Build and return the case's forensic report.

    The response shape is whatever `generate_forensic_report` produces:
    `disclaimer`, `case_information`, `observed_evidence`,
    `calculated_analysis`, `potentially_related_events` and
    `report_integrity`. Returns 404 when the case doesn't exist.
    """
    case = get_case_or_404(case_id)

    events = app_state.get_events(case_id)
    evidence_items = app_state.get_evidence_items(case_id)
    normalization_errors = app_state.get_normalization_errors(case_id)

    correlations = [asdict(correlation) for correlation in correlate_events(events)]

    return generate_forensic_report(
        case=case,
        evidence_items=evidence_items,
        events=events,
        correlations=correlations,
        normalization_errors=normalization_errors,
    )
