"""
Standalone command-line test for app/services/correlation_service.py.

Run it from the backend/ directory (with your venv active):

    python test_correlation.py

No pytest needed - this is a plain script. It builds a small,
realistic set of Event objects, runs them through every correlation
rule, prints what was found and why, and then runs a handful of
sanity checks (including a determinism check and a forensic-wording
check) so you can see at a glance whether the service is behaving
correctly.

Exit code: 0 if every check passes, 1 if any check fails.
"""

import sys
from datetime import datetime, timezone

from app.models.event import Event, EventCategory
from app.services.correlation_service import correlate_events, DEFAULT_TIME_WINDOW

_checks_failed = []


def check(description, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {description}")
    if not condition:
        _checks_failed.append(description)


def make_event(hour, minute, category, event_type, description, metadata=None):
    return Event(
        case_id="CASE-001",
        timestamp=datetime(2026, 9, 17, hour, minute, tzinfo=timezone.utc),
        category=category,
        event_type=event_type,
        source="demo",
        description=description,
        metadata=metadata or {},
    )


def main():
    phone = "+1-555-0199"

    events = [
        make_event(  # #1
            10, 0, EventCategory.CALL, "call_incoming", "Incoming call",
            metadata={"caller": phone, "receiver": "self", "direction": "incoming"},
        ),
        make_event(  # #2 - shares phone number with #1, and close in time to it
            10, 5, EventCategory.MESSAGE, "message_outgoing", "Outgoing message",
            metadata={"sender": "self", "receiver": phone, "direction": "outgoing"},
        ),
        make_event(  # #3 - a location fix, close in time to #1 and #2, shares no identifier
            10, 3, EventCategory.LOCATION, "gps_fix", "Location recorded near Downtown office",
            metadata={"latitude": 12.6271, "longitude": 80.1927},
        ),
        make_event(  # #4 - unrelated: far away in time, no shared identifier
            20, 0, EventCategory.APP, "app_open", "Camera opened",
            metadata={"app": "Camera", "action": "OPEN"},
        ),
    ]
    id_to_label = {event.id: f"#{i + 1}" for i, event in enumerate(events)}

    print("--- INPUT EVENTS ---")
    for label, event in zip(id_to_label.values(), events):
        print(f"{label}: {event.timestamp.strftime('%H:%M')}  {event.category:9s} {event.event_type:16s} {event.description}")
    print()

    print(f"--- CORRELATIONS (default window = {int(DEFAULT_TIME_WINDOW.total_seconds() // 60)} min) ---")
    results = correlate_events(events)
    for result in results:
        labels = [id_to_label[eid] for eid in result.related_event_ids]
        print(f"{result.correlation_id}  [{result.rule}]  related={labels}")
        print(f"    reason : {result.reason}")
        print(f"    context: {result.context}")
    print()

    # --- sanity checks ---
    print("--- CHECKS ---")

    rules_found = {r.rule for r in results}
    check(
        "all three rule types produced at least one result",
        rules_found == {"time_window", "shared_identifier", "location_proximity"},
    )

    call_and_message = next(
        (r for r in results if r.rule == "shared_identifier"), None
    )
    check(
        "shared_identifier correlation links the call (#1) and message (#2)",
        call_and_message is not None
        and set(call_and_message.related_event_ids) == {events[0].id, events[1].id},
    )

    event_4_id = events[3].id
    check(
        "the unrelated event (#4) appears in zero correlations",
        all(event_4_id not in r.related_event_ids for r in results),
    )

    results_again = correlate_events(events)
    check(
        "running correlate_events twice on the same input gives identical output (determinism)",
        [(r.correlation_id, r.related_event_ids) for r in results]
        == [(r.correlation_id, r.related_event_ids) for r in results_again],
    )

    forbidden_words = ["prove", "proves", "proven", "guilt", "guilty", "criminal", "perpetrator"]
    all_reason_text = " ".join(r.reason for r in results).lower()
    check(
        "no accusatory/conclusive wording (prove, guilt, criminal, ...) appears in any reason",
        not any(word in all_reason_text for word in forbidden_words),
    )

    print()
    if _checks_failed:
        print(f"{len(_checks_failed)} check(s) FAILED:")
        for description in _checks_failed:
            print(f"  - {description}")
        sys.exit(1)
    else:
        print("All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
