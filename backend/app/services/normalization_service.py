"""
Unified Event normalization service.

Every evidence category (app activity, calls, messages, locations,
system logs) already has its own parser in app/parsers/ that knows
how to turn that category's raw, already-in-memory records (plain
Python lists/dicts, e.g. loaded from an app_activity.json or
calls.json) into app.models.event.Event objects. Each of those
parsers is independent and category-specific - callers who only care
about one evidence type can (and do) use them directly.

This service is the single front door that sits above all of them.
Given raw records for one or more evidence categories, it dispatches
each category's records to the correct existing parser and hands
back one combined, uniformly-shaped collection of Event objects -
plus any per-record errors - regardless of which category (or
categories) the evidence came from. This is what lets downstream
components (timeline, correlation, analysis) work against a single
Event shape instead of five different evidence formats.

This service does NOT:
    - read files or extract ZIPs (see app/services/extraction_service.py)
    - call any API or AI service
    - touch a database
    - build a timeline or sort events
    - correlate events
    - parse record contents itself - all actual field-level parsing,
      timestamp normalization, and metadata construction is delegated
      to the existing per-category parsers in app/parsers/, so the
      normalization rules for each evidence type live in exactly one
      place.

Determinism
------------
Normalizing the same input twice produces the same output:
    - categories are always processed in a fixed order (the order
      EvidenceCategory declares them below), regardless of the order
      keys appear in the input dict
    - within a category, events preserve the input record order
      (guaranteed by the underlying parser's batch function)
    - no wall-clock time, randomness, or external state influences
      which events are produced or how they're ordered - the only
      generated values (Event.id) are UUIDs and are not part of what
      makes output "deterministic" here; the *set and order* of
      normalized events for a given input is what stays stable
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.models.event import Event
from app.parsers.app_parser import parse_app_activity_batch
from app.parsers.call_parser import parse_call_batch
from app.parsers.location_parser import parse_location_batch
from app.parsers.message_parser import parse_message_batch
from app.parsers.system_log_parser import parse_system_log_batch


class EvidenceCategory(str, Enum):
    """
    The evidence categories this service knows how to normalize.

    Declaration order here is also the fixed processing order used by
    `normalize_evidence_package`, which is what makes its output
    deterministic regardless of input dict ordering.
    """

    APP = "app"
    CALL = "call"
    MESSAGE = "message"
    LOCATION = "location"
    SYSTEM_LOG = "system_log"


# Maps each evidence category to the existing parser's batch function.
# Every one of these already returns a dataclass with `.events` and
# `.errors` attributes (ParsedAppActivityResult, ParsedCallResult,
# etc.) - this service relies on that shared shape rather than
# re-implementing any parsing logic itself.
_CATEGORY_TO_PARSER: Dict[EvidenceCategory, Callable[..., Any]] = {
    EvidenceCategory.APP: parse_app_activity_batch,
    EvidenceCategory.CALL: parse_call_batch,
    EvidenceCategory.MESSAGE: parse_message_batch,
    EvidenceCategory.LOCATION: parse_location_batch,
    EvidenceCategory.SYSTEM_LOG: parse_system_log_batch,
}


@dataclass
class NormalizationResult:
    """
    Outcome of normalizing one or more batches of raw records.

    Attributes:
        events: Successfully normalized Event objects.
        errors: One entry per record that could not be normalized,
            each describing the original record, its evidence
            category, and why it failed. A bad record in one category
            never prevents other records (in the same or a different
            category) from being normalized.
    """

    events: List[Event] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


def normalize_records(
    category: EvidenceCategory,
    records: List[Dict[str, Any]],
    case_id: str,
    source: Optional[str] = None,
) -> NormalizationResult:
    """
    Normalize one batch of raw records belonging to a single evidence
    category into Event objects.

    Args:
        category: Which evidence category `records` belongs to. This
            determines which existing parser is used.
        records: Raw, already-in-memory records for that category
            (e.g. the list already loaded from an app_activity.json).
            This function does not read files itself.
        case_id: Case these events belong to. Passed straight through
            to the underlying parser, which stamps it onto every
            Event it produces.
        source: Optional override for where these events are recorded
            as having come from (e.g. a specific evidence filename or
            id). When omitted, each parser's own default source name
            is used (e.g. "call_log_parser"), which is how source
            information is preserved even when the caller doesn't
            supply anything more specific.

    Returns:
        A NormalizationResult with the normalized events and any
        per-record errors, both taken directly from the underlying
        parser's batch result.
    """
    parser_batch_fn = _CATEGORY_TO_PARSER.get(category)
    if parser_batch_fn is None:
        # Defensive: EvidenceCategory and _CATEGORY_TO_PARSER are kept
        # in sync above, so this should be unreachable in practice.
        return NormalizationResult(
            errors=[{"category": category, "record": None, "reason": f"Unsupported category: {category!r}"}]
        )

    parsed = parser_batch_fn(records, case_id=case_id, source=source) if source else parser_batch_fn(records, case_id=case_id)

    errors_with_category = [{"category": category.value, **error} for error in parsed.errors]
    return NormalizationResult(events=parsed.events, errors=errors_with_category)


def normalize_evidence_package(
    case_id: str,
    records_by_category: Dict[EvidenceCategory, List[Dict[str, Any]]],
) -> NormalizationResult:
    """
    Normalize an entire evidence package - raw records from any mix of
    supported categories - into one combined collection of Events.

    This is the typical entry point once evidence has been extracted
    and each category's JSON has been loaded into memory: hand this
    function a dict of {category: records}, and it returns every
    normalized Event across all of them, ready for a timeline or
    correlation step to consume.

    Args:
        case_id: Case all of this evidence belongs to.
        records_by_category: Raw records for each evidence category
            present in this package. A category with no records for
            this case can simply be omitted or given an empty list -
            missing optional evidence categories are handled safely
            and don't affect the categories that are present.

    Returns:
        A NormalizationResult combining every category's events (in
        the fixed category order defined by EvidenceCategory, with
        each category's own record order preserved) and every
        category's errors.
    """
    combined = NormalizationResult()

    for category in EvidenceCategory:
        records = records_by_category.get(category)
        if not records:
            continue

        result = normalize_records(category, records, case_id=case_id)
        combined.events.extend(result.events)
        combined.errors.extend(result.errors)

    return combined
