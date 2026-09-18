from app.parsers.app_parser import parse_app_activity_batch
records = [
    {"timestamp": "2026-09-17T09:00:00+05:30", "app": "WhatsApp", "action": "OPEN"},  # valid
    {"timestamp": "2026-09-17T09:08:00+05:30", "action": "CLOSE"},                    # missing "app"
    {"timestamp": "not-a-real-date", "app": "Chrome", "action": "OPEN"},              # bad timestamp
    {"timestamp": "2026-09-17T10:00:00+05:30", "app": "", "action": "OPEN"},          # empty app name
    "not even a dict",                                                                # wrong type entirely
]

result = parse_app_activity_batch(records, case_id="CASE-2026-0042")
print(len(result.events), "parsed successfully")
for err in result.errors:
    print(err["reason"])