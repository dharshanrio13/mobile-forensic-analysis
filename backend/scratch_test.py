from datetime import datetime, timezone
from app.database.connection import engine, SessionLocal
from app.database.base import Base
import app.models  # registers Case, Evidence, Event, Location
from app.models import Case, Evidence, Event, Location

# Create all tables (safe to run repeatedly — won't duplicate existing tables)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Insert a Case with related records
case = Case(name="Case 001", description="Simulated device analysis")
case.evidence_items.append(Evidence(
    filename="call_log.json",
    evidence_type="call_log",
    file_path="/evidence/call_log.json",
))
case.events.append(Event(
    timestamp=datetime.now(timezone.utc),
    category="call",
    event_type="incoming_call",
    source="call_log.json",
    description="Incoming call from unknown number",
    event_metadata={"duration_seconds": 42, "number": "+1555..."},
))
case.locations.append(Location(
    timestamp=datetime.now(timezone.utc),
    latitude=12.9716,
    longitude=77.5946,
    source="location_history.json",
))

db.add(case)
db.commit()

# Read it back
fetched = db.query(Case).first()
print("Case:", fetched)
print("Evidence:", fetched.evidence_items)
print("Events:", fetched.events, "| metadata:", fetched.events[0].event_metadata)
print("Locations:", fetched.locations)

db.close()