"""
Database package for the Mobile Device Forensic Analysis System.

This package owns everything related to the SQLite database:
where the file lives, how to open a connection, and how to
initialise it when the application starts.

Typical use from anywhere else in the project:

    from database import init_db, get_connection

    init_db()                       # run once at startup

    with get_connection() as conn:  # run a query
        conn.execute("SELECT 1")
"""

from .connection import DB_PATH, DATABASE_DIR, get_connection
from .init_db import init_db

__all__ = ["DB_PATH", "DATABASE_DIR", "get_connection", "init_db"]