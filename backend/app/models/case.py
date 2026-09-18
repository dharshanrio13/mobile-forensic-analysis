"""
Case data model.

This is a plain Pydantic model, NOT a database model - there is no
database in this project. It represents an investigation case as an
in-memory/API data structure: something a route can accept as input,
return as output, or a service can pass around internally.

Since there's no database to auto-generate IDs or timestamps, both
`id` and `created_at` are given sensible defaults here so a Case can
be created easily (e.g. `Case(name="...", description="...")`) while
still being fully overridable when needed.
"""

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Case(BaseModel):
    """An investigation case."""

    # Unique identifier for the case. Defaults to a randomly generated
    # UUID string so callers don't have to supply one themselves.
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Short human-readable name/title for the case.
    name: str

    # Longer free-text description of what the case covers.
    description: str

    # When the case was created. Defaults to "now" (UTC) at creation
    # time, similar to how a database would auto-populate a timestamp.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))