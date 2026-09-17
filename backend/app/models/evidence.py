"""
Evidence model.

An Evidence record represents a single piece of collected evidence
(e.g. a simulated app-activity export, call log file, message dump,
etc.) that belongs to a Case. No parsing or upload handling is
implemented here - this is just the data structure.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database.base import Base


class Evidence(Base):
    """A single piece of evidence belonging to a Case."""

    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)

    # Which case this evidence belongs to. Indexed since evidence will
    # almost always be looked up "by case".
    case_id = Column(ForeignKey("cases.id"), nullable=False, index=True)

    # Original filename of the evidence item, e.g. "call_log.json".
    filename = Column(String(255), nullable=False)

    # What kind of evidence this is, e.g. "call_log", "messages",
    # "app_activity", "location_data", "system_log". Kept as a plain
    # string for now rather than an enum, to stay flexible.
    evidence_type = Column(String(100), nullable=False)

    # Where the underlying file lives (path or reference string).
    # Actual upload/storage handling is not implemented yet.
    file_path = Column(String(500), nullable=False)

    uploaded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Each Evidence item belongs to exactly one Case.
    case = relationship("Case", back_populates="evidence_items")

    def __repr__(self):
        return f"<Evidence id={self.id} filename={self.filename!r}>"
