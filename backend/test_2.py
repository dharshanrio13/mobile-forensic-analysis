from app.parsers.call_parser import parse_call_batch
records = [
    {"timestamp": "2026-09-17T11:00:00+05:30", "contact": "+1-555-0155"},                  # no direction, no duration
    {"timestamp": "2026-09-17T11:30:00+05:30", "contact": "+1-555-0166", "direction": "missed"},  # missed call, no duration
    {"contact": "+1-555-0177", "direction": "incoming"},                                    # missing timestamp
    {"timestamp": "2026-09-17T12:00:00+05:30", "direction": "incoming"},                    # no caller/receiver/contact at all
]

result = parse_call_batch(records, case_id="CASE-2026-0042")
for ev in result.events:
    print(ev.event_type, "-", ev.description, "-", ev.metadata)
print("Errors:")
for err in result.errors:
    print(" ", err["reason"])