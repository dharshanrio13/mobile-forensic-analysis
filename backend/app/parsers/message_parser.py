"""
Message record parser.

Turns simulated mobile "message log" data - already loaded from JSON
into plain Python lists/dicts - into normalized app.models.event.Event
objects (category=MESSAGE), following the same pattern as
call_parser.py and app_parser.py so downstream consumers
(normalization, timeline, correlation) can treat every evidence type
uniformly.

This module does NOT read files, extract archives, touch a database,
call any external service or web framework, or perform analysis. It
only validates and reshapes already-in-memory data.

Expected input shape (per record) is flexible. Either of these work:

    {"timestamp": "...", "sender": "+1-555-0100", "receiver": "+1-555-0199",
     "direction": "outgoing", "content": "On my way"}

    {"timestamp": "...", "contact": "+1-555-0199", "direction": "incoming",
     "content": "Running late"}

The second form (a single "contact" plus a direction) is common in
simpler message-log exports; sender/receiver are then derived from
direction relative to the device owner (see _derive_parties).

All message content is treated as simulated evidence text for this
forensic-analysis prototype.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.event import Event, EventCategory

# Accepted alternative key names for each logical field. First match wins.
_FIELD_ALIASES: Dict[str, List[str]] = {
    "timestamp": ["timestamp", "time", "datetime", "date_time"],
    "sender": ["sender", "from", "from_number", "originator"],
    "receiver": ["receiver", "to", "to_number", "recipient"],
    "contact": ["contact", "number", "phone_number"],
    "direction": ["direction", "message_direction"],
    "content": ["content", "message", "text", "body"],
}

# Normalizes recognized direction values into a canonical form.
_DIRECTION_ALIASES: Dict[str, str] = {
    "INCOMING": "incoming",
    "IN": "incoming",
    "RECEIVED": "incoming",
    "INBOUND": "incoming",
    "OUTGOING": "outgoing",
    "OUT": "outgoing",
    "SENT": "outgoing",
    "OUTBOUND": "outgoing",
}

# Placeholder used for the device owner's own side of a message when
# only a single "contact" number is given (no explicit sender/receiver).
_DEVICE_OWNER_PLACEHOLDER = "self"
_UNKNOWN_PLACEHOLDER = "unknown"

PARSER_SOURCE_NAME = "message_log_parser"


@dataclass
class ParsedMessageResult:
    """
    Result of parsing a batch of message records.

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
    not something that should block parsing a message record.
    """
    if not raw_direction or not isinstance(raw_direction, str):
        return _UNKNOWN_PLACEHOLDER
    key = raw_direction.strip().upper()
    return _DIRECTION_ALIASES.get(key, raw_direction.strip().lower())


def _derive_parties(
    raw_sender: Optional[str],
    raw_receiver: Optional[str],
    raw_contact: Optional[str],
    direction: str,
) -> tuple:
    """
    Work out (sender, receiver) from whatever combination of fields
    is available.

    Priority:
      1. Explicit sender/receiver, if either given, are used as-is
         (missing side becomes "unknown").
      2. A single "contact" plus a known direction: the device owner
         fills the other slot ("self" as sender for incoming, or as
         receiver for outgoing).
      3. A single "contact" with unknown direction: contact is placed
         as the sender and the receiver is left as "unknown", since
         we have no basis to guess which side the device owner is on.
      4. Nothing at all: both sides are "unknown".
    """
    if raw_sender or raw_receiver:
        return (
            raw_sender if raw_sender else _UNKNOWN_PLACEHOLDER,
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


def parse_message_record(
    record: Dict[str, Any],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> Event:
    """
    Parse a single message record into an Event.

    Only `timestamp` is strictly required, along with at least one way
    to identify the other party (`sender`/`receiver`, or `contact`).
    `direction` and `content` are optional and handled safely when
    absent - a record with no message text is still a valid event
    (e.g. metadata-only message logs). Raises ValueError with a
    human-readable message if the record can't be parsed. Use
    `parse_message_batch` if you want bad records skipped instead of
    raised.
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

    raw_sender = _get_field(record, "sender")
    raw_receiver = _get_field(record, "receiver")
    raw_contact = _get_field(record, "contact")

    if not any([raw_sender, raw_receiver, raw_contact]):
        raise ValueError(
            "Missing required field(s): at least one of sender, receiver, or contact"
        )

    direction = _normalize_direction(_get_field(record, "direction"))
    sender, receiver = _derive_parties(raw_sender, raw_receiver, raw_contact, direction)

    raw_content = _get_field(record, "content")
    content = raw_content.strip() if isinstance(raw_content, str) and raw_content.strip() else None

    other_party = raw_contact or raw_receiver or raw_sender
    event_type = f"message_{direction}" if direction != _UNKNOWN_PLACEHOLDER else "message_unknown_direction"
    description = (
        f"{direction.capitalize()} message with {other_party}"
        if direction != _UNKNOWN_PLACEHOLDER
        else f"Message with {other_party}"
    )

    return Event(
        case_id=case_id,
        timestamp=timestamp,
        category=EventCategory.MESSAGE,
        event_type=event_type,
        source=source,
        description=description,
        metadata={
            "sender": sender,
            "receiver": receiver,
            "direction": direction,
            "content": content,
        },
    )


def parse_message_batch(
    records: List[Dict[str, Any]],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> ParsedMessageResult:
    """
    Parse a list of message records.

    Never raises on a bad individual record - each failure is
    collected into `result.errors` (with the offending record and the
    reason) so one malformed entry doesn't discard the whole batch.
    Order of `result.events` matches the order of valid input records.
    """
    result = ParsedMessageResult()

    if not isinstance(records, list):
        result.errors.append(
            {"record": records, "reason": f"Expected a list of records, got {type(records).__name__}"}
        )
        return result

    for record in records:
        try:
            event = parse_message_record(record, case_id=case_id, source=source)
            result.events.append(event)
        except ValueError as exc:
            result.errors.append({"record": record, "reason": str(exc)})

    return result
