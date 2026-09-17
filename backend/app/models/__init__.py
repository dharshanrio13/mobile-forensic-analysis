"""
Database models package.

Importing this package (or any name from it) ensures every model is
registered with `Base.metadata`, which is required before calling
`Base.metadata.create_all(engine)` to create the tables.
"""

from app.models.case import Case
from app.models.evidence import Evidence
from app.models.event import Event
from app.models.location import Location

__all__ = ["Case", "Evidence", "Event", "Location"]
