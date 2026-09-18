"""
Location record parser.

Turns simulated mobile "location history" data - already loaded from
JSON into plain Python lists/dicts - into normalized
app.models.event.Event objects (category=LOCATION), following the same
pattern as app_parser.py, call_parser.py, and message_parser.py so
downstream consumers (normalization, timeline, correlation) can treat
every evidence type uniformly.

This module does NOT read files, render maps, touch a database, call
any web framework, or perform correlation. It only validates and
reshapes already-in-memory data.

Expected input shape (per record), e.g. from a locations.json like:

    {"timestamp": "2026-09-17T09:00:00+05:30", "latitude": 12.6271,
     "longitude": 80.1927, "label": "Downtown office"}

Latitude/longitude are validated both for being numeric and for
falling within valid geographic bounds (-90..90 for latitude,
-180..180 for longitude) - a "coordinate" outside those ranges isn't
a real location, so it's treated as a malformed record rather than
silently accepted.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.event import Event, EventCategory

# Accepted alternative key names for each logical field. First match wins.
_FIELD_ALIASES: Dict[str, List[str]] = {
    "timestamp": ["timestamp", "time", "datetime", "date_time"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng", "long"],
    "label": ["label", "place", "name", "description"],
    "accuracy": ["accuracy", "accuracy_meters", "accuracy_m"],
    "provider": ["provider", "location_provider"],
}

_LATITUDE_MIN, _LATITUDE_MAX = -90.0, 90.0
_LONGITUDE_MIN, _LONGITUDE_MAX = -180.0, 180.0

PARSER_SOURCE_NAME = "location_history_parser"


@dataclass
class ParsedLocationResult:
    """
    Result of parsing a batch of location records.

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


def _parse_coordinate(raw_value: Any, field_name: str, min_bound: float, max_bound: float) -> float:
    """
    Parse and validate a single coordinate value.

    Raises ValueError if the value isn't numeric, or if it's numeric
    but outside the valid geographic range for that field.
    """
    if isinstance(raw_value, bool):
        # bool is technically an int subclass in Python; explicitly
        # reject it so True/False can't silently become 1.0/0.0.
        raise ValueError(f"Field '{field_name}' must be numeric, got bool")

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"Field '{field_name}' must be numeric, got {type(raw_value).__name__}: {raw_value!r}")

    if not (min_bound <= value <= max_bound):
        raise ValueError(f"Field '{field_name}'={value} is outside valid range [{min_bound}, {max_bound}]")

    return value


def parse_location_record(
    record: Dict[str, Any],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> Event:
    """
    Parse a single location record into an Event.

    `timestamp`, `latitude`, and `longitude` are required. Latitude
    must be numeric and within [-90, 90]; longitude must be numeric
    and within [-180, 180]. Anything else present (label, accuracy,
    provider) is optional and carried through to metadata when given.
    Raises ValueError with a human-readable message if the record
    can't be parsed. Use `parse_location_batch` if you want bad
    records skipped instead of raised.
    """
    if not isinstance(record, dict):
        raise ValueError(f"Record must be a dict, got {type(record).__name__}")

    raw_timestamp = _get_field(record, "timestamp")
    raw_latitude = _get_field(record, "latitude")
    raw_longitude = _get_field(record, "longitude")

    missing = [
        name
        for name, value in (
            ("timestamp", raw_timestamp),
            ("latitude", raw_latitude),
            ("longitude", raw_longitude),
        )
        if value is None
    ]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    try:
        timestamp = _parse_timestamp(raw_timestamp)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid timestamp '{raw_timestamp}': {exc}") from exc

    latitude = _parse_coordinate(raw_latitude, "latitude", _LATITUDE_MIN, _LATITUDE_MAX)
    longitude = _parse_coordinate(raw_longitude, "longitude", _LONGITUDE_MIN, _LONGITUDE_MAX)

    label = _get_field(record, "label")
    accuracy = _get_field(record, "accuracy")
    provider = _get_field(record, "provider")

    description = f"Location recorded at ({latitude}, {longitude})"
    if isinstance(label, str) and label.strip():
        description = f"Location recorded near {label.strip()}"

    metadata: Dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
    }
    if isinstance(label, str) and label.strip():
        metadata["label"] = label.strip()
    if accuracy is not None:
        metadata["accuracy"] = accuracy
    if isinstance(provider, str) and provider.strip():
        metadata["provider"] = provider.strip()

    return Event(
        case_id=case_id,
        timestamp=timestamp,
        category=EventCategory.LOCATION,
        event_type="gps_fix",
        source=source,
        description=description,
        metadata=metadata,
    )


def parse_location_batch(
    records: List[Dict[str, Any]],
    case_id: str,
    source: str = PARSER_SOURCE_NAME,
) -> ParsedLocationResult:
    """
    Parse a list of location records.

    Never raises on a bad individual record - each failure is
    collected into `result.errors` (with the offending record and the
    reason) so one malformed entry doesn't discard the whole batch.
    Order of `result.events` matches the order of valid input records.
    """
    result = ParsedLocationResult()

    if not isinstance(records, list):
        result.errors.append(
            {"record": records, "reason": f"Expected a list of records, got {type(records).__name__}"}
        )
        return result

    for record in records:
        try:
            event = parse_location_record(record, case_id=case_id, source=source)
            result.events.append(event)
        except ValueError as exc:
            result.errors.append({"record": record, "reason": str(exc)})

    return result
