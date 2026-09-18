from app.parsers.location_parser import parse_location_batch
records = [
    {"timestamp": "2026-09-17T11:00:00+05:30", "latitude": 91.0, "longitude": 80.0},     # latitude out of range
    {"timestamp": "2026-09-17T11:10:00+05:30", "latitude": 12.6, "longitude": 200.0},    # longitude out of range
    {"timestamp": "2026-09-17T11:20:00+05:30", "latitude": "not-a-number", "longitude": 80.0},  # non-numeric
    {"timestamp": "2026-09-17T11:30:00+05:30", "latitude": True, "longitude": 80.0},     # bool, rejected on purpose
    {"timestamp": "2026-09-17T11:40:00+05:30", "longitude": 80.0},                       # missing latitude
]

result = parse_location_batch(records, case_id="CASE-2026-0042")
print(len(result.events), "parsed successfully")
for err in result.errors:
    print(" ", err["reason"])