"""
Database connection helpers for the Mobile Device Forensic Analysis System.
"""

import sqlite3
from pathlib import Path

DATABASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = DATABASE_DIR / "forensic.db"


def get_connection() -> sqlite3.Connection:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection