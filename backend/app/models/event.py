"""
Event model.

An Event represents a single timestamped occurrence extracted from
(simulated) device evidence - e.g. a call, a message, an app launch,
or a system log entry. Events are the building blocks of a case
timeline. No parsing logic is implemented here - this is just the
data structure.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database.base import Base


class Event(Base):
    """A single timestamped event belonging to a Case."""

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    # Which case this event belongs to. Indexed for fast "events for
    # this case" lookups.
    case_id = Column(ForeignKey("cases.id"), nullable=False, index=True)

    # When the event occurred (per the evidence), not when the row was
    # created. Indexed since events will commonly be queried/sorted by
    # time to build a timeline.
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Broad grouping, e.g. "call", "message", "app_activity", "system".
    category = Column(String(100), nullable=False)

    # More specific type within the category, e.g. "incoming_call",
    # "sms_sent", "app_launch".
    event_type = Column(String(100), nullable=False)

    # Where this event came from, e.g. the originating evidence file
    # or extraction source (e.g. "call_log.json").
    source = Column(String(255), nullable=True)

    # Human-readable summary of the event.
    description = Column(Text, nullable=True)

    # Flexible JSON-like data for anything that doesn't fit the fixed
    # columns above (e.g. raw extracted fields). Uses SQLAlchemy's
    # JSON type, which stores as TEXT under SQLite but automatically
    # serializes/deserializes Python dicts and lists for you.
    #
    # The attribute is named `event_metadata` (with a trailing
    # underscore-free alias) because `metadata` is a reserved name on
    # every SQLAlchemy declarative model (it's used internally for
    # table/schema metadata). The actual database column is still
    # named "metadata" via the explicit Column("metadata", ...) below.
    event_metadata = Column("metadata", JSON, nullable=True)

    # Each Event belongs to exactly one Case.
    case = relationship("Case", back_populates="events")

    def __repr__(self):
        return f"<Event id={self.id} type={self.event_type!r} timestamp={self.timestamp!r}>"
