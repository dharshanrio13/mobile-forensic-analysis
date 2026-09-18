from app.parsers.message_parser import parse_message_batch
records = [
    {"timestamp": "2026-09-17T15:00:00+05:30", "contact": "+1-555-0155"},        # no direction, no content
    {"timestamp": "2026-09-17T15:10:00+05:30", "contact": "+1-555-0166", "direction": "incoming", "content": "   "},  # blank content
    {"contact": "+1-555-0177", "direction": "incoming"},                          # missing timestamp
    {"timestamp": "2026-09-17T16:00:00+05:30", "direction": "outgoing"},          # no sender/receiver/contact at all
]

result = parse_message_batch(records, case_id="CASE-2026-0042")
for ev in result.events:
    print(ev.event_type, "-", ev.metadata)
print("Errors:")
for err in result.errors:
    print(" ", err["reason"])