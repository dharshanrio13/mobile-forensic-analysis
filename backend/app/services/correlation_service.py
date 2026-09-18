"""
Deterministic event-correlation service.

This service looks at a list of already-normalized
app.models.event.Event objects and flags pairs/groups of events that
are POTENTIALLY related, using a small set of explicit, explainable
rules:

    1. time_window        - events that occurred within a configurable
                             time window of each other
    2. shared_identifier   - events that reference the same contact/
                             person identifier (e.g. the same phone
                             number as a call's caller/receiver or a
                             message's sender/receiver)
    3. location_proximity  - a location event occurring close in time
                             to some other (non-location) activity

Every rule is a plain, inspectable comparison over Event fields and
metadata - there is no machine learning, heuristics-with-confidence-
scores, or external service involved. Given the same input list and
the same configuration, this service always produces the same output
(see "Determinism" below).

FORENSIC WORDING - READ BEFORE CHANGING ANY MESSAGE STRING
------------------------------------------------------------
This service NEVER states or implies that a correlation proves
wrongdoing, guilt, identity, or criminal activity. A correlation here
means only "these events share an observable, explainable pattern" -
nothing about intent or culpability. All reason/description text uses
neutral, explicitly hedged language such as "potentially related",
"temporal correlation", and "shared identifier". Every result also
carries the raw context (timestamps, gaps, identifier values) so a
human reviewer can evaluate the pattern themselves rather than being
told a conclusion.

This service does NOT:
    - parse raw evidence (see app/parsers/)
    - read files or extract archives
    - touch a database
    - call any AI model or external service
    - build a timeline (see app/services/timeline_service.py)
    - define any API route

Determinism
------------
- Rules only compare fields already present on the Event objects
  given - no randomness, no wall-clock "now", no external state.
- Candidate correlations are collected in a fixed, sorted order
  (by the participating events' timestamps and ids) before
  correlation_ids are assigned, so re-running this service on the
  same input always produces the same correlation_ids in the same
  order.
- correlation_id is a sequential, rule-prefixed string (e.g.
  "CORR-TW-0001"), not a random UUID - this is what makes output
  byte-for-byte reproducible across runs, which matters for
  forensic tooling.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from itertools import combinations
from typing import Any, Dict, List, Set

from app.models.event import Event, EventCategory

# Default window used by the time-window and location-proximity rules
# when the caller doesn't specify one.
DEFAULT_TIME_WINDOW = timedelta(minutes=15)

# Metadata keys that may hold a party-identifying value (e.g. a phone
# number) for the shared_identifier rule. Only fields that identify a
# *party* are used here - free-text fields like a message's "content"
# are deliberately excluded, since matching on message text would be
# a very different (and far less reliable) kind of correlation.
_IDENTIFIER_METADATA_KEYS = ("caller", "receiver", "sender", "contact")

# Placeholder values the existing parsers use when a party is unknown
# or is the device owner - these are never treated as a shared
# identifier, since "unknown" matching "unknown" or "self" matching
# "self" across events says nothing meaningful.
_NON_IDENTIFYING_VALUES = {"unknown", "self"}


@dataclass
class CorrelationResult:
    """
    One potential relationship between two or more events.

    Attributes:
        correlation_id: Deterministic, rule-prefixed identifier for
            this correlation (e.g. "CORR-TW-0001"). Stable across runs
            for the same input - not a random UUID.
        related_event_ids: The ids of the events flagged as
            potentially related by this correlation.
        reason: A short, neutral, explainable description of *why*
            these events were flagged (e.g. "Temporal correlation:
            events occurred within 5 minutes of each other."). This
            describes an observed pattern only - never a conclusion
            about identity, intent, or wrongdoing.
        rule: Which correlation rule produced this result:
            "time_window", "shared_identifier", or
            "location_proximity".
        context: Supporting time/context information - e.g. the
            timestamps involved, the gap between them, or the shared
            identifier value - so a human reviewer can evaluate the
            correlation themselves. Contains only facts, never a
            judgment.
    """

    correlation_id: str
    related_event_ids: List[str]
    reason: str
    rule: str
    context: Dict[str, Any] = field(default_factory=dict)


def _extract_identifiers(event: Event) -> Set[str]:
    """
    Pull candidate shared-identifier values (e.g. phone numbers) out
    of an event's metadata.

    Only the structural identifier fields listed in
    _IDENTIFIER_METADATA_KEYS are considered, and placeholder values
    such as "unknown" or "self" are excluded, since those don't
    identify a specific real-world party.
    """
    identifiers: Set[str] = set()
    for key in _IDENTIFIER_METADATA_KEYS:
        value = event.metadata.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned and cleaned.lower() not in _NON_IDENTIFYING_VALUES:
                identifiers.add(cleaned)
    return identifiers


def _sort_key(event_pair_or_ids, events_by_id: Dict[str, Event]):
    """Deterministic sort key: earliest timestamp, then event ids, in a group."""
    ids = sorted(event_pair_or_ids)
    timestamps = sorted(events_by_id[eid].timestamp for eid in ids)
    return (timestamps[0], tuple(ids))


def correlate_by_time_window(
    events: List[Event],
    time_window: timedelta = DEFAULT_TIME_WINDOW,
) -> List[CorrelationResult]:
    """
    Flag every pair of events that occurred within `time_window` of
    each other as potentially related (rule: "time_window").

    This is a simple, explainable proximity-in-time check - it makes
    no claim about *why* two events happened close together, only
    that they did.
    """
    events_by_id = {event.id: event for event in events}
    candidates = []

    for event_a, event_b in combinations(events, 2):
        gap = abs(event_a.timestamp - event_b.timestamp)
        if gap <= time_window:
            candidates.append(({event_a.id, event_b.id}, gap))

    candidates.sort(key=lambda item: _sort_key(item[0], events_by_id))

    results = []
    for index, (ids, gap) in enumerate(candidates, start=1):
        ordered_ids = sorted(ids, key=lambda eid: events_by_id[eid].timestamp)
        results.append(
            CorrelationResult(
                correlation_id=f"CORR-TW-{index:04d}",
                related_event_ids=ordered_ids,
                reason=(
                    f"Temporal correlation: events occurred within "
                    f"{int(gap.total_seconds())} seconds of each other."
                ),
                rule="time_window",
                context={
                    "time_window_seconds": int(time_window.total_seconds()),
                    "gap_seconds": int(gap.total_seconds()),
                    "timestamps": [events_by_id[eid].timestamp.isoformat() for eid in ordered_ids],
                },
            )
        )
    return results


def correlate_by_shared_identifier(events: List[Event]) -> List[CorrelationResult]:
    """
    Group events that reference the same party identifier (e.g. the
    same phone number as a caller/receiver/sender/contact) and flag
    each group as potentially related (rule: "shared_identifier").

    A shared identifier means only that the same reference appears on
    multiple events - it says nothing about who that identifier
    belongs to or what the relationship between the events means.
    """
    events_by_id = {event.id: event for event in events}
    events_by_identifier: Dict[str, Set[str]] = {}

    for event in events:
        for identifier in _extract_identifiers(event):
            events_by_identifier.setdefault(identifier, set()).add(event.id)

    candidates = [
        (identifier, ids)
        for identifier, ids in events_by_identifier.items()
        if len(ids) >= 2
    ]
    candidates.sort(key=lambda item: _sort_key(item[1], events_by_id))

    results = []
    for index, (identifier, ids) in enumerate(candidates, start=1):
        ordered_ids = sorted(ids, key=lambda eid: events_by_id[eid].timestamp)
        results.append(
            CorrelationResult(
                correlation_id=f"CORR-SI-{index:04d}",
                related_event_ids=ordered_ids,
                reason=(
                    f"Shared identifier: {len(ordered_ids)} events reference "
                    f"the same contact/person identifier."
                ),
                rule="shared_identifier",
                context={
                    "identifier": identifier,
                    "timestamps": [events_by_id[eid].timestamp.isoformat() for eid in ordered_ids],
                },
            )
        )
    return results


def correlate_by_location_proximity(
    events: List[Event],
    time_window: timedelta = DEFAULT_TIME_WINDOW,
) -> List[CorrelationResult]:
    """
    Flag a location event and any non-location event that occurred
    within `time_window` of it as potentially related (rule:
    "location_proximity") - e.g. "a location fix was recorded close
    in time to some other recorded activity."

    This rule only considers time proximity between a location event
    and other activity; it makes no claim that the device owner
    performed that activity at that location, only that the two
    records are close together in time.
    """
    events_by_id = {event.id: event for event in events}
    location_events = [e for e in events if e.category == EventCategory.LOCATION]
    other_events = [e for e in events if e.category != EventCategory.LOCATION]

    candidates = []
    for location_event in location_events:
        for other_event in other_events:
            gap = abs(location_event.timestamp - other_event.timestamp)
            if gap <= time_window:
                candidates.append(({location_event.id, other_event.id}, gap))

    candidates.sort(key=lambda item: _sort_key(item[0], events_by_id))

    results = []
    for index, (ids, gap) in enumerate(candidates, start=1):
        ordered_ids = sorted(ids, key=lambda eid: events_by_id[eid].timestamp)
        results.append(
            CorrelationResult(
                correlation_id=f"CORR-LP-{index:04d}",
                related_event_ids=ordered_ids,
                reason=(
                    f"Location proximity: a location record and another "
                    f"recorded event occurred within "
                    f"{int(gap.total_seconds())} seconds of each other."
                ),
                rule="location_proximity",
                context={
                    "time_window_seconds": int(time_window.total_seconds()),
                    "gap_seconds": int(gap.total_seconds()),
                    "timestamps": [events_by_id[eid].timestamp.isoformat() for eid in ordered_ids],
                },
            )
        )
    return results


def correlate_events(
    events: List[Event],
    time_window: timedelta = DEFAULT_TIME_WINDOW,
) -> List[CorrelationResult]:
    """
    Run every correlation rule over `events` and return all results
    together.

    Results are grouped by rule (time_window, then shared_identifier,
    then location_proximity), and within each rule they're in the
    same deterministic order produced by that rule's own function.
    This grouping - rather than a single interleaved list - keeps
    each rule's output independently inspectable, since the three
    rules answer different questions and a result from one is never a
    substitute for a result from another.
    """
    return [
        *correlate_by_time_window(events, time_window=time_window),
        *correlate_by_shared_identifier(events),
        *correlate_by_location_proximity(events, time_window=time_window),
    ]
