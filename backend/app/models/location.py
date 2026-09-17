"""
Location model.

A Location represents a single timestamped GPS coordinate extracted
from (simulated) device evidence, e.g. from location history or
geotagged app activity. No parsing logic is implemented here - this
is just the data structure.
"""

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database.base import Base


class Location(Base):
    """A single timestamped location belonging to a Case."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)

    # Which case this location belongs to. Indexed for fast "locations
    # for this case" lookups.
    case_id = Column(ForeignKey("cases.id"), nullable=False, index=True)

    # When this location was recorded (per the evidence). Indexed since
    # locations will commonly be queried/sorted by time.
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Where this location data came from, e.g. "location_history.json"
    # or "app_activity" (for geotagged app events).
    source = Column(String(255), nullable=True)

    # Each Location belongs to exactly one Case.
    case = relationship("Case", back_populates="locations")

    def __repr__(self):
        return f"<Location id={self.id} lat={self.latitude} lng={self.longitude}>"
