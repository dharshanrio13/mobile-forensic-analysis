"""
Database connection setup.

This module configures the SQLite connection, creates the SQLAlchemy
engine and session factory, and exposes a `get_db` dependency that
FastAPI routes can use to get a database session.

No tables or models are created here - only the connection machinery.
Models (Case, Evidence, Event, Location, Communication, etc.) will be
added later and will use `Base` from `base.py`.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# SQLite requires this flag when used with more than one thread, which
# is the case in a FastAPI app (each request may be handled on a
# different thread). It is not needed for other databases.
connect_args = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

# Session factory: each call to SessionLocal() creates a new database
# session. autocommit/autoflush are left off so behavior is explicit
# and predictable (you call db.commit() yourself).
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route (once models/routes exist):

        from fastapi import Depends
        from app.database.connection import get_db

        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    The session is always closed after the request finishes, even if
    an error occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
