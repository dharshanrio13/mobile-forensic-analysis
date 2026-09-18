"""
System log parser.

Turns simulated mobile "system log" data - already loaded from JSON
into plain Python lists/dicts - into normalized app.models.event.Event
objects (category=SYSTEM), following the same pattern as the other
parsers in this package (app_parser.py, call_parser.py,
message_parser.py, location_parser.py) so downstream consumers
(normalization, timeline, correlation) can treat every evidence type
uniformly.

This module does NOT read files, touch a database, call any API or
AI service, correlate events, or build a timeline. It only validates
and reshapes already-in-memory data.

Expected input shape (per record), e.g. from a system_logs.json like:

    {"timestamp": "2026-09-17T08:00:00+05:30", "level": "INFO",
     "event": "boot_completed", "message": "Device finished booting"}

System logs are the least uniform evidence type in this system - some
tools log a "level", some don't; some name the event "event", others
"type"; some records are just a free-text "message" with no
structured event name at all. This parser is deliberately permissive
about which of (event/type) or (message) is present, since a system
log with only a message is still meaningful evidence, and a system
log with only an event name and no message is too.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.event import Event, EventCategory

# Accepted alternative key names for each logical field. First match wins.
_FIELD_ALIASES: Dict[str, List[str]] = {
    "timestamp": ["timestamp", "time", "datetime", "date_time"],
    "level": ["level", "log_level", "severity"],
    "event": ["event", "type", "log_event", "event_type"],
    "message": ["message", "description", "details", "text"],
}

_UNKNOWN_LEVEL = "unknown"
_GENERIC_EVENT_TYPE = "system_log"

PARSER_SOURCE_NAME = "system_log_parser"


@dataclass
class ParsedSystemLogResult:
    """
    Result of parsing a batch of system log records.

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


def _normalize_level(raw_level: Optional[str]) -> str:
    """
    Normalize a log level/severity string.

    Missing or non-string values become "unknown" rather than
    raising - severity is treated as optional/best-effort context,
    not something that should block parsing a system log record.
    Recognized or not, whatever string is given is lowercased and
    passed through as-is so unfamiliar severities aren't lost.
    """
    if not raw_level or not isinstance(raw_level, str) or not raw_level.strip():
        return _UNKNOWN_LEVEL
    return raw_level.strip().lower()


def _normalize_event_type(raw_event: Optional[str]) -> str:
    """
    Normalize a raw event/type string into a canonical event_type.

    Falls back to a generic "system_log" event_type when no event
    name was given at all (e.g. a message-only log line).
    """
    if not raw_event or not isinstance(raw_event, str) or not raw_event.strip():
        return _GENERIC_EVENT_TYPE
    normalized = raw_event.strip().lower().replace(" ", "_")
    return normalized if normalized.startswith("system_") else f"system_{normalized}"


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


def parse_system_log_record(
    record: Dict[str, Any],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> Event:
    """
    Parse a single system log record into an Event.

    `timestamp` is required, along with at least one of `event`/`type`
    or `message` - a log entry with neither has nothing usable to
    describe. `level` is optional and defaults to "unknown" when
    absent. Raises ValueError with a human-readable message if the
    record can't be parsed. Use `parse_system_log_batch` if you want
    bad records skipped instead of raised.
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

    raw_event = _get_field(record, "event")
    raw_message = _get_field(record, "message")

    if not raw_event and not raw_message:
        raise ValueError("Missing required field(s): at least one of event, type, or message")

    level = _normalize_level(_get_field(record, "level"))
    event_type = _normalize_event_type(raw_event)
    message = raw_message.strip() if isinstance(raw_message, str) and raw_message.strip() else None

    description = message if message else f"System event: {raw_event}"

    return Event(
        case_id=case_id,
        timestamp=timestamp,
        category=EventCategory.SYSTEM,
        event_type=event_type,
        source=source,
        description=description,
        metadata={
            "level": level,
            "event": raw_event if isinstance(raw_event, str) and raw_event.strip() else None,
            "message": message,
        },
    )


def parse_system_log_batch(
    records: List[Dict[str, Any]],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> ParsedSystemLogResult:
    """
    Parse a list of system log records.

    Never raises on a bad individual record - each failure is
    collected into `result.errors` (with the offending record and the
    reason) so one malformed entry doesn't discard the whole batch.
    Order of `result.events` matches the order of valid input records.
    """
    result = ParsedSystemLogResult()

    if not isinstance(records, list):
        result.errors.append(
            {"record": records, "reason": f"Expected a list of records, got {type(records).__name__}"}
        )
        return result

    for record in records:
        try:
            event = parse_system_log_record(record, case_id=case_id, source=source)
            result.events.append(event)
        except ValueError as exc:
            result.errors.append({"record": record, "reason": str(exc)})

    return result
