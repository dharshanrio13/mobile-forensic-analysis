from app.models.event import Event, EventCategory

# APP event
app_ev = Event(
    case_id='CASE-2026-0042',
    timestamp='2026-09-18T09:02:11Z',
    category=EventCategory.APP,
    event_type='app_launch',
    source='app_usage_parser',
    description='WhatsApp launched',
    metadata={'package_name': 'com.whatsapp', 'foreground_duration_seconds': 342},
)
print('APP OK:', app_ev.model_dump())

# CALL event
call_ev = Event(
    case_id='CASE-2026-0042',
    timestamp='2026-09-18T10:15:30Z',
    category=EventCategory.CALL,
    event_type='call_incoming',
    source='call_log_parser',
    description='Incoming call from +1-555-0199',
    metadata={'phone_number': '+1-555-0199', 'duration_seconds': 184},
)
print('CALL OK:', call_ev.model_dump())

# LOCATION event
loc_ev = Event(
    case_id='CASE-2026-0042',
    timestamp='2026-09-18T10:20:00Z',
    category=EventCategory.LOCATION,
    event_type='gps_fix',
    source='location_history_parser',
    description='Device location recorded',
    metadata={'latitude': 12.6271, 'longitude': 80.1927},
)
print('LOCATION OK:', loc_ev.model_dump())

print('All three events created successfully.')
