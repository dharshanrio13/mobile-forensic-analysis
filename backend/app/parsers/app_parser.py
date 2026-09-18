"""
Application activity parser.

Turns simulated mobile "app activity" data - already loaded from JSON
into plain Python lists/dicts - into normalized app.models.event.Event
objects.

This module does NOT read files, extract archives, touch a database,
call any web framework, correlate events, or build a timeline. It
only validates and reshapes already-in-memory data. Reading the JSON
off disk and feeding it here is the caller's job.

Expected input shape (per record), e.g. from an app_activity.json
like:
    {"timestamp": "2026-09-17T09:00:00+05:30", "app": "WhatsApp", "action": "OPEN"}

Some tolerance is built in for common naming variations (see
_FIELD_ALIASES below), since different export tools name these
fields differently.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.event import Event, EventCategory

# Accepted alternative key names for each logical field. First match wins.
_FIELD_ALIASES: Dict[str, List[str]] = {
    "timestamp": ["timestamp", "time", "datetime", "date_time"],
    "app": ["app", "app_name", "application", "package", "package_name"],
    "action": ["action", "event", "status", "state"],
}

# Normalizes recognized action/status values into a canonical event_type
# suffix. Anything not listed here falls back to a lowercased, sanitized
# version of whatever value was provided (see _normalize_action).
_ACTION_TO_EVENT_TYPE: Dict[str, str] = {
    "OPEN": "app_open",
    "OPENED": "app_open",
    "LAUNCH": "app_open",
    "LAUNCHED": "app_open",
    "FOREGROUND": "app_open",
    "CLOSE": "app_close",
    "CLOSED": "app_close",
    "EXIT": "app_close",
    "BACKGROUND": "app_close",
    "INSTALL": "app_install",
    "INSTALLED": "app_install",
    "UNINSTALL": "app_uninstall",
    "UNINSTALLED": "app_uninstall",
}

PARSER_SOURCE_NAME = "app_activity_parser"


@dataclass
class ParsedAppActivityResult:
    """
    Result of parsing a batch of app activity records.

    Attributes:
        events: Successfully parsed, normalized Event objects, in the
            same order as the valid input records.
        errors: One entry per record that could not be parsed, each
            describing the original record and why it failed. Nothing
            in `errors` prevents parsing of the remaining records -
            a single bad record never aborts the batch.
    """

    events: List[Event] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)


def _get_field(record: Dict[str, Any], logical_name: str) -> Optional[Any]:
    """Look up a logical field on `record` using its known aliases."""
    for alias in _FIELD_ALIASES[logical_name]:
        if alias in record and record[alias] is not None:
            return record[alias]
    return None


def _normalize_action(raw_action: str) -> str:
    """
    Map a raw action/status string to a canonical event_type suffix.

    Recognized values (see _ACTION_TO_EVENT_TYPE) map to a fixed
    vocabulary. Anything else is lowercased and has spaces replaced
    with underscores so unfamiliar-but-valid actions still produce a
    predictable, non-crashing event_type instead of being rejected.
    """
    key = raw_action.strip().upper()
    if key in _ACTION_TO_EVENT_TYPE:
        return _ACTION_TO_EVENT_TYPE[key]
    return "app_" + raw_action.strip().lower().replace(" ", "_")


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
        # datetime.fromisoformat doesn't accept a trailing "Z" before
        # Python 3.11, so normalize it to an explicit UTC offset first.
        normalized = raw_timestamp.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise ValueError(f"Unsupported timestamp type: {type(raw_timestamp).__name__}")


def parse_app_activity_record(
    record: Dict[str, Any],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> Event:
    """
    Parse a single app activity record into an Event.

    Raises ValueError with a human-readable message if the record is
    missing a required field or has a value that can't be interpreted.
    Use `parse_app_activity_batch` if you want bad records skipped
    instead of raised.
    """
    if not isinstance(record, dict):
        raise ValueError(f"Record must be a dict, got {type(record).__name__}")

    raw_timestamp = _get_field(record, "timestamp")
    raw_app = _get_field(record, "app")
    raw_action = _get_field(record, "action")

    missing = [
        name
        for name, value in (("timestamp", raw_timestamp), ("app", raw_app), ("action", raw_action))
        if value is None
    ]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    if not isinstance(raw_app, str) or not raw_app.strip():
        raise ValueError("Field 'app' must be a non-empty string")
    if not isinstance(raw_action, str) or not raw_action.strip():
        raise ValueError("Field 'action' must be a non-empty string")

    try:
        timestamp = _parse_timestamp(raw_timestamp)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid timestamp '{raw_timestamp}': {exc}") from exc

    app_name = raw_app.strip()
    event_type = _normalize_action(raw_action)
    description = f"{app_name} {raw_action.strip().lower()}"

    return Event(
        case_id=case_id,
        timestamp=timestamp,
        category=EventCategory.APP,
        event_type=event_type,
        source=source,
        description=description,
        metadata={
            "app": app_name,
            "action": raw_action.strip(),
        },
    )


def parse_app_activity_batch(
    records: List[Dict[str, Any]],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> ParsedAppActivityResult:
    """
    Parse a list of app activity records.

    Never raises on a bad individual record - each failure is
    collected into `result.errors` (with the offending record and the
    reason) so one malformed entry doesn't discard the whole batch.
    Order of `result.events` matches the order of valid input records.
    """
    result = ParsedAppActivityResult()

    if not isinstance(records, list):
        result.errors.append(
            {"record": records, "reason": f"Expected a list of records, got {type(records).__name__}"}
        )
        return result

    for record in records:
        try:
            event = parse_app_activity_record(record, case_id=case_id, source=source)
            result.events.append(event)
        except ValueError as exc:
            result.errors.append({"record": record, "reason": str(exc)})

    return result
