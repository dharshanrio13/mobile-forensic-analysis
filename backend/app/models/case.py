"""
Case model.

A Case represents a single forensic investigation. All other records
(Evidence, Event, Location, and later Communication /
ChainOfCustody) belong to a Case.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship

from app.database.base import Base


class Case(Base):
    """A forensic investigation case."""

    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)

    # Short human-readable name/title for the case, e.g. "Case #2026-014".
    name = Column(String(255), nullable=False)

    # Free-text description of the case (optional).
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # A Case can have many Evidence items, Events, and Locations.
    # `back_populates` keeps both sides of the relationship in sync.
    # `cascade="all, delete-orphan"` means deleting a Case also removes
    # its related records, so the database never keeps orphaned rows.
    evidence_items = relationship(
        "Evidence", back_populates="case", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="case", cascade="all, delete-orphan"
    )
    locations = relationship(
        "Location", back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Case id={self.id} name={self.name!r}>"
