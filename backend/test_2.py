from app.parsers.system_log_parser import parse_system_log_batch
records = [
    {"timestamp": "2026-09-17T09:00:00+05:30"},                              # neither event nor message
    {"event": "kernel_panic", "level": "critical"},                          # missing timestamp
    {"timestamp": "bad-timestamp", "event": "wifi_connected"},               # unparseable timestamp
    "not a dict",                                                            # wrong type entirely
]

result = parse_system_log_batch(records, case_id="CASE-2026-0042")
print(len(result.events), "parsed successfully")
for err in result.errors:
    print(" ", err["reason"])