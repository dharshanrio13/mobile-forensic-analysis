"""
SQLAlchemy declarative base.

All future database models (Case, Evidence, Event, Location,
Communication, etc.) will inherit from this `Base` class. Defining it
in its own module avoids circular imports: models import `Base` from
here, and `connection.py` imports it too when it needs to create
tables.

No models are defined yet - this file only provides the base class
that future models will build on.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
