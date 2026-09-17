"""
Database connection setup.

Uses Python's built-in `sqlite3` module, so there is nothing to install.
SQLite stores the whole database in a single file on disk.
"""

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Where the database file lives
# ---------------------------------------------------------------------------
# __file__ is this file (.../database/connection.py)
# .resolve() turns it into a full path
# .parent  is the folder that contains it -> .../database/
DATABASE_DIR = Path(__file__).resolve().parent

# The actual database file. It sits inside the database/ folder.
DB_PATH = DATABASE_DIR / "forensic.db"


def get_connection() -> sqlite3.Connection:
    """
    Open and return a connection to the SQLite database.

    If the file does not exist yet, SQLite creates it automatically the
    first time we connect. That is why the application never has to
    "create" the database file by hand.

    Returns:
        sqlite3.Connection: an open connection. Close it when you are done,
        or use it with a `with` block.
    """
    # Make sure the folder exists before SQLite tries to write into it.
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    # Rows come back as dict-like objects instead of plain tuples,
    # so you can write row["case_id"] instead of row[0]. Easier to read.
    connection.row_factory = sqlite3.Row

    # SQLite does not enforce foreign keys unless you ask it to.
    # Turning it on now means the team's future tables behave correctly.
    connection.execute("PRAGMA foreign_keys = ON;")

    return connection