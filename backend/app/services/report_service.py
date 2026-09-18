"""
Forensic report service.

This service takes data that has ALREADY been produced by the rest of
the system - a Case, the Evidence items registered for it, and the
Unified Events already normalized by app/parsers/ + the normalization
service - and assembles it into one structured, JSON-compatible report
dictionary.

It does not compute anything the rest of the system doesn't already
know. Specifically, this file does NOT:
    - parse any evidence (that's app/parsers/)
    - access a database
    - define any API route
    - generate a PDF or any other rendered document - the output is a
      plain, JSON-serializable Python dict; turning that into a PDF is
      a separate concern for later
    - perform correlation analysis - if a correlation service exists
      elsewhere and has already produced results, this service can
      include them (passed in via `correlations`), but it never
      invents or calculates relationships between events itself
    - make any claim, finding, or suggestion of guilt, wrongdoing, or
      intent. Every section is either a plain restatement of evidence
      that was observed, or a neutral statistical count derived from
      it (a number of calls, a date range, a list of distinct
      contacts) - never an interpretation of what that data means.

Report structure and evidentiary labeling
------------------------------------------
The report is intentionally split into clearly labeled sections so a
reader always knows what kind of claim they're looking at:

    - `case_information`         - facts about the case itself.
    - `observed_evidence`        - a direct restatement of the
      Evidence items on file (what was uploaded, not what it means).
    - `calculated_analysis`      - deterministic statistics computed
      from the normalized Events (counts, date ranges, distinct
      contacts). These are arithmetic summaries, not conclusions.
    - `potentially_related_events` - relationships between events,
      IF a correlation result was supplied by the caller. This
      section is explicitly named "potentially related" and carries
      its own disclaimer, since any such relationship is a candidate
      for human review, not an established fact.
    - `report_integrity`         - metadata about the report itself
      (when it was generated, how much data it covers, whether any
      records failed to normalize).

Every top-level report also carries a `disclaimer` field restating
that nothing in the report constitutes a finding of guilt or
wrongdoing.
"""

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.case import Case
from app.models.evidence import Evidence
from app.models.event import Event

REPORT_DISCLAIMER = (
    "This report presents observed evidence and neutral, deterministic "
    "statistical summaries derived from it. It does not draw, imply, or "
    "support any conclusion about guilt, wrongdoing, or intent. Any items "
    "listed under 'potentially_related_events' indicate only that events "
    "share certain attributes (such as timing or participants) and require "
    "independent human investigative review before any inference is drawn."
)

# Categories treated as "communication" for the communication summary.
_COMMUNICATION_CATEGORIES = {"call", "message"}

# Placeholder values used by the parsers that should not be counted as
# real, identifiable contacts when listing distinct communication parties.
_NON_CONTACT_PLACEHOLDERS = {"self", "unknown", None}


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """Serialize a datetime to an ISO-8601 string, or None if absent."""
    if dt is None:
        return None
    return dt.isoformat()


def _build_case_information(case: Case) -> Dict[str, Any]:
    """Plain restatement of the case's own fields - no derived data."""
    return {
        "id": case.id,
        "name": case.name,
        "description": case.description,
        "created_at": _iso(case.created_at),
    }


def _build_observed_evidence(evidence_items: List[Evidence]) -> Dict[str, Any]:
    """
    Direct restatement of the Evidence items registered for this case.

    This section describes what was uploaded/registered as evidence -
    it makes no claim about the contents or significance of that
    evidence.
    """
    type_counts = Counter(item.evidence_type for item in evidence_items)

    return {
        "total_items": len(evidence_items),
        "counts_by_evidence_type": dict(type_counts),
        "items": [
            {
                "id": item.id,
                "filename": item.filename,
                "evidence_type": item.evidence_type,
                "uploaded_at": _iso(item.uploaded_at),
            }
            for item in evidence_items
        ],
    }


def _build_timeline_summary(events: List[Event]) -> Dict[str, Any]:
    """
    Deterministic statistics about the normalized events: how many
    there are, the earliest/latest timestamp, and a count per
    category. This intentionally stops at simple aggregate arithmetic
    (min/max/count) - it does not construct or order a full event
    timeline (that is the timeline service's responsibility, not
    this one's).
    """
    if not events:
        return {
            "event_count": 0,
            "earliest_event_at": None,
            "latest_event_at": None,
            "counts_by_category": {},
        }

    timestamps = [event.timestamp for event in events]
    category_counts = Counter(event.category for event in events)

    return {
        "event_count": len(events),
        "earliest_event_at": _iso(min(timestamps)),
        "latest_event_at": _iso(max(timestamps)),
        "counts_by_category": dict(category_counts),
    }


def _build_location_summary(events: List[Event]) -> Dict[str, Any]:
    """
    Aggregate statistics about location-category events. Lists the
    recorded points as observed - does not infer movement patterns,
    speed, dwell time, or anything else beyond what was recorded.
    """
    location_events = [event for event in events if event.category == "location"]

    recorded_points = []
    for event in location_events:
        metadata = event.metadata or {}
        recorded_points.append(
            {
                "timestamp": _iso(event.timestamp),
                "latitude": metadata.get("latitude"),
                "longitude": metadata.get("longitude"),
                "label": metadata.get("label"),
            }
        )

    return {
        "location_event_count": len(location_events),
        "recorded_points": recorded_points,
    }


def _extract_contacts_from_event(event: Event) -> List[str]:
    """Pull out any identifiable (non-placeholder) contact values from
    a call or message event's metadata."""
    metadata = event.metadata or {}
    contacts = []
    for key in ("caller", "receiver", "sender"):
        value = metadata.get(key)
        if value not in _NON_CONTACT_PLACEHOLDERS:
            contacts.append(value)
    return contacts


def _build_communication_summary(events: List[Event]) -> Dict[str, Any]:
    """
    Aggregate statistics about call and message events: counts by
    category and direction, and the set of distinct contacts observed
    across all communication events. Does not characterize the
    content or nature of any communication.
    """
    comm_events = [event for event in events if event.category in _COMMUNICATION_CATEGORIES]

    call_events = [event for event in comm_events if event.category == "call"]
    message_events = [event for event in comm_events if event.category == "message"]

    call_direction_counts = Counter((event.metadata or {}).get("direction", "unknown") for event in call_events)
    message_direction_counts = Counter(
        (event.metadata or {}).get("direction", "unknown") for event in message_events
    )

    distinct_contacts = set()
    for event in comm_events:
        distinct_contacts.update(_extract_contacts_from_event(event))

    return {
        "total_calls": len(call_events),
        "total_messages": len(message_events),
        "call_counts_by_direction": dict(call_direction_counts),
        "message_counts_by_direction": dict(message_direction_counts),
        "distinct_contacts_observed": sorted(distinct_contacts),
    }


def _build_potentially_related_events(correlations: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Wraps externally-supplied correlation results, if any, with an
    explicit disclaimer. This function does not compute correlations
    itself - it only presents whatever the caller already computed
    elsewhere (e.g. a future correlation service), clearly labeled as
    candidates for review rather than established relationships.
    """
    items = correlations if correlations else []
    return {
        "note": (
            "Entries below indicate that two or more events share attributes "
            "(such as close timing, a common contact, or a common location) "
            "and are flagged for human review. This is not a determination "
            "that the events are actually connected."
        ),
        "count": len(items),
        "items": items,
    }


def _build_report_integrity(
    evidence_items: List[Evidence],
    events: List[Event],
    normalization_errors: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Metadata describing the report's own generation and completeness -
    not evidence content, but information about how much of the
    evidence this report actually reflects.
    """
    errors = normalization_errors if normalization_errors else []
    return {
        "generated_at": _iso(datetime.now(timezone.utc)),
        "evidence_items_included": len(evidence_items),
        "events_included": len(events),
        "records_that_failed_normalization": len(errors),
        "note": (
            "This report reflects simulated evidence for prototype/testing "
            "purposes. 'records_that_failed_normalization' counts source "
            "records that could not be parsed into events and are therefore "
            "NOT reflected anywhere else in this report."
        ),
    }


def generate_forensic_report(
    case: Case,
    evidence_items: List[Evidence],
    events: List[Event],
    correlations: Optional[List[Dict[str, Any]]] = None,
    normalization_errors: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Assemble a structured forensic report from already-processed data.

    Args:
        case: The Case this report is for.
        evidence_items: Evidence records registered for this case
            (e.g. from app.services.evidence_service intake results).
        events: Unified Events already normalized for this case (e.g.
            from app.services.normalization_service).
        correlations: Optional, already-computed candidate
            relationships between events, if some other part of the
            system has produced them. Each item's shape is up to the
            caller - this service only wraps and labels them, it does
            not validate or compute them.
        normalization_errors: Optional list of records that failed to
            normalize into events, surfaced here purely as a
            completeness/integrity note.

    Returns:
        A plain, JSON-compatible dict with the sections described in
        this module's docstring.
    """
    return {
        "disclaimer": REPORT_DISCLAIMER,
        "case_information": _build_case_information(case),
        "observed_evidence": _build_observed_evidence(evidence_items),
        "calculated_analysis": {
            "timeline_summary": _build_timeline_summary(events),
            "location_summary": _build_location_summary(events),
            "communication_summary": _build_communication_summary(events),
        },
        "potentially_related_events": _build_potentially_related_events(correlations),
        "report_integrity": _build_report_integrity(evidence_items, events, normalization_errors),
    }
