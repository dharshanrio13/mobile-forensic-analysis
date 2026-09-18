"""
Call record parser.

Turns simulated mobile "call log" data - already loaded from JSON into
plain Python lists/dicts - into normalized app.models.event.Event
objects (category=CALL), matching the same pattern used by
app_parser.py so downstream consumers (normalization, timeline,
correlation) can treat every evidence type uniformly.

This module does NOT read files, extract archives, touch a database,
call any web framework, correlate events, or build a timeline. It
only validates and reshapes already-in-memory data.

Expected input shape (per record) is flexible. Either of these work:

    {"timestamp": "...", "caller": "+1-555-0100", "receiver": "+1-555-0199",
     "direction": "outgoing", "duration_seconds": 184}

    {"timestamp": "...", "contact": "+1-555-0199", "direction": "incoming",
     "duration_seconds": 184}

The second form (a single "contact" plus a direction) is common in
simpler call-log exports; caller/receiver are then derived from
direction relative to the device owner (see _derive_parties).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.event import Event, EventCategory

# Accepted alternative key names for each logical field. First match wins.
_FIELD_ALIASES: Dict[str, List[str]] = {
    "timestamp": ["timestamp", "time", "datetime", "date_time"],
    "caller": ["caller", "from", "from_number", "originator"],
    "receiver": ["receiver", "to", "to_number", "recipient"],
    "contact": ["contact", "number", "phone_number"],
    "direction": ["direction", "call_direction"],
    "duration": ["duration", "duration_seconds", "length_seconds", "call_duration"],
}

# Normalizes recognized direction values into a canonical form.
_DIRECTION_ALIASES: Dict[str, str] = {
    "INCOMING": "incoming",
    "IN": "incoming",
    "RECEIVED": "incoming",
    "INBOUND": "incoming",
    "OUTGOING": "outgoing",
    "OUT": "outgoing",
    "DIALED": "outgoing",
    "OUTBOUND": "outgoing",
    "MISSED": "missed",
}

# Placeholder used for the device owner's own side of a call when only
# a single "contact" number is given (no explicit caller/receiver).
_DEVICE_OWNER_PLACEHOLDER = "self"
_UNKNOWN_PLACEHOLDER = "unknown"

PARSER_SOURCE_NAME = "call_log_parser"


@dataclass
class ParsedCallResult:
    """
    Result of parsing a batch of call records.

    Attributes:
        events: Successfully parsed, normalized Event objects, in the
            same order as the valid input records.
        errors: One entry per record that could not be parsed, each
            describing the original record and why it failed. A
            single bad record never aborts the batch.
    """

    events: List[Event] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


def _get_field(record: Dict[str, Any], logical_name: str) -> Optional[Any]:
    """Look up a logical field on `record` using its known aliases."""
    for alias in _FIELD_ALIASES[logical_name]:
        if alias in record and record[alias] is not None:
            return record[alias]
    return None


def _normalize_direction(raw_direction: Optional[str]) -> str:
    """
    Map a raw direction string to a canonical value.

    Unrecognized or missing values become "unknown" rather than
    raising - direction is treated as optional/best-effort context,
    not something that should block parsing a call record.
    """
    if not raw_direction or not isinstance(raw_direction, str):
        return _UNKNOWN_PLACEHOLDER
    key = raw_direction.strip().upper()
    return _DIRECTION_ALIASES.get(key, raw_direction.strip().lower())


def _derive_parties(
    raw_caller: Optional[str],
    raw_receiver: Optional[str],
    raw_contact: Optional[str],
    direction: str,
) -> tuple:
    """
    Work out (caller, receiver) from whatever combination of fields
    is available.

    Priority:
      1. Explicit caller/receiver, if both given, are used as-is.
      2. A single "contact" plus a known direction: the device owner
         fills the other slot ("self" for incoming's receiver, or
         outgoing's caller).
      3. A single "contact" with unknown direction: contact is placed
         as the caller and the receiver is left as "unknown", since
         we have no basis to guess which side the device owner is on.
      4. Nothing at all: both sides are "unknown".
    """
    if raw_caller or raw_receiver:
        return (
            raw_caller if raw_caller else _UNKNOWN_PLACEHOLDER,
            raw_receiver if raw_receiver else _UNKNOWN_PLACEHOLDER,
        )

    if raw_contact:
        if direction == "incoming":
            return raw_contact, _DEVICE_OWNER_PLACEHOLDER
        if direction == "outgoing":
            return _DEVICE_OWNER_PLACEHOLDER, raw_contact
        return raw_contact, _UNKNOWN_PLACEHOLDER

    return _UNKNOWN_PLACEHOLDER, _UNKNOWN_PLACEHOLDER


def _parse_timestamp(raw_timestamp: Any) -> datetime:
    """
    Parse a timestamp value into a datetime.

    Accepts ISO-8601 strings (including a trailing "Z" or a numeric
    UTC offset like "+05:30") or an already-constructed datetime.
    Raises ValueError on anything else - callers should catch this.
    """
    if isinstance(raw_timestamp, datetime):
        return raw_timestamp
    if isinstance(raw_timestamp, str):
        normalized = raw_timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise ValueError(f"Unsupported timestamp type: {type(raw_timestamp).__name__}")


def _parse_duration(raw_duration: Any) -> Optional[float]:
    """
    Parse a duration value into a float number of seconds, or None if
    missing/unusable. Duration is optional - a call record without one
    (e.g. a missed call) is still valid.
    """
    if raw_duration is None:
        return None
    try:
        return float(raw_duration)
    except (TypeError, ValueError):
        return None


def parse_call_record(
    record: Dict[str, Any],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> Event:
    """
    Parse a single call record into an Event.

    Only `timestamp` is strictly required, along with at least one way
    to identify the other party (`caller`/`receiver`, or `contact`).
    `direction` and `duration` are optional and handled safely when
    absent. Raises ValueError with a human-readable message if the
    record can't be parsed. Use `parse_call_batch` if you want bad
    records skipped instead of raised.
    """
    if not isinstance(record, dict):
        raise ValueError(f"Record must be a dict, got {type(record).__name__}")

    raw_timestamp = _get_field(record, "timestamp")
    if raw_timestamp is None:
        raise ValueError("Missing required field: timestamp")

    try:
        timestamp = _parse_timestamp(raw_timestamp)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid timestamp '{raw_timestamp}': {exc}") from exc

    raw_caller = _get_field(record, "caller")
    raw_receiver = _get_field(record, "receiver")
    raw_contact = _get_field(record, "contact")

    if not any([raw_caller, raw_receiver, raw_contact]):
        raise ValueError(
            "Missing required field(s): at least one of caller, receiver, or contact"
        )

    direction = _normalize_direction(_get_field(record, "direction"))
    caller, receiver = _derive_parties(raw_caller, raw_receiver, raw_contact, direction)
    duration = _parse_duration(_get_field(record, "duration"))

    event_type = f"call_{direction}" if direction != _UNKNOWN_PLACEHOLDER else "call_unknown_direction"
    other_party = raw_contact or raw_receiver or raw_caller
    description = f"{direction.capitalize()} call with {other_party}" if direction != _UNKNOWN_PLACEHOLDER else f"Call with {other_party}"

    return Event(
        case_id=case_id,
        timestamp=timestamp,
        category=EventCategory.CALL,
        event_type=event_type,
        source=source,
        description=description,
        metadata={
            "caller": caller,
            "receiver": receiver,
            "direction": direction,
            "duration": duration,
        },
    )


def parse_call_batch(
    records: List[Dict[str, Any]],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> ParsedCallResult:
    """
    Parse a list of call records.

    Never raises on a bad individual record - each failure is
    collected into `result.errors` (with the offending record and the
    reason) so one malformed entry doesn't discard the whole batch.
    Order of `result.events` matches the order of valid input records.
    """
    result = ParsedCallResult()

    if not isinstance(records, list):
        result.errors.append(
            {"record": records, "reason": f"Expected a list of records, got {type(records).__name__}"}
        )
        return result

    for record in records:
        try:
            event = parse_call_record(record, case_id=case_id, source=source)
            result.events.append(event)
        except ValueError as exc:
            result.errors.append({"record": record, "reason": str(exc)})

    return result
