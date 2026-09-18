"""
Timeline service.

This service takes a list of already-normalized app.models.event.Event
objects (produced by app/services/normalization_service.py, or from
any other source that already hands back Event objects) and arranges
them into a clean, chronologically-ordered timeline.

This service does NOT:
    - parse raw evidence records (see app/parsers/)
    - read files or extract archives
    - touch a database
    - perform correlation between events (e.g. grouping related
      events, detecting patterns) - it only orders and optionally
      filters a flat list by time
    - define any API route

It only reorders/filters the Event objects it's given.

Sort stability
--------------
Sorting uses Python's built-in `sorted`, which is stable: when two
events share the exact same timestamp, they keep their original
relative order from the input list rather than being reordered
arbitrarily. This makes `build_timeline` deterministic - the same
input list always produces the same output list.

Timezone awareness
-------------------
Event.timestamp is expected to be a timezone-aware datetime (this is
what every existing parser in app/parsers/ produces). Comparing a
timezone-aware timestamp against a naive one raises a TypeError in
Python - if you pass `start_time`/`end_time`, make sure they're
timezone-aware too, for the same reason.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from app.models.event import Event


class SortOrder(str, Enum):
    """Direction to sort a timeline in."""

    ASCENDING = "ascending"
    DESCENDING = "descending"


def build_timeline(
    events: List[Event],
    order: SortOrder = SortOrder.ASCENDING,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Event]:
    """
    Turn a list of Event objects into a clean, chronologically-ordered
    timeline.

    Args:
        events: The events to arrange into a timeline. The input list
            itself is never modified - a new list is returned.
        order: SortOrder.ASCENDING (earliest first, the default) or
            SortOrder.DESCENDING (latest first).
        start_time: If given, events strictly before this time are
            excluded (events with timestamp >= start_time are kept).
        end_time: If given, events strictly after this time are
            excluded (events with timestamp <= end_time are kept).
            Both bounds are inclusive, so passing the same value for
            both `start_time` and `end_time` keeps events at exactly
            that instant.

    Returns:
        A new list of Event objects: filtered to the given time range
        (if any), then sorted in the requested order. The input list
        is left untouched.
    """
    timeline = list(events)

    if start_time is not None:
        timeline = [event for event in timeline if event.timestamp >= start_time]

    if end_time is not None:
        timeline = [event for event in timeline if event.timestamp <= end_time]

    timeline.sort(key=lambda event: event.timestamp, reverse=(order == SortOrder.DESCENDING))

    return timeline
