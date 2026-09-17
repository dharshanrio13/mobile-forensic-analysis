"""
Database package for the Mobile Device Forensic Analysis System.

Teammates should import from here:

    from database import init_db, get_connection
"""

from .connection import DATABASE_DIR, DATABASE_PATH, get_connection
from .init_db import init_db

__all__ = ["DATABASE_DIR", "DATABASE_PATH", "get_connection", "init_db"]
