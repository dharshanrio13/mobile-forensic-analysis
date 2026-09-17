"""
Very small test: does the database get created and can it be opened?

Run from the project root (mobile-forensic-analysis/):

    python tests/test_database.py

or, if you have pytest installed:

    pytest tests/
"""

import sys
from pathlib import Path

# Allow running this file directly, without installing the project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import DATABASE_PATH, get_connection, init_db


def test_database_can_be_opened():
    init_db()

    # 1. The file exists on disk.
    assert DATABASE_PATH.exists(), f"Database file missing: {DATABASE_PATH}"

    # 2. SQLite answers a query through it.
    connection = get_connection()
    try:
        result = connection.execute("SELECT 1 AS ok;").fetchone()
        assert result["ok"] == 1
    finally:
        connection.close()


if __name__ == "__main__":
    test_database_can_be_opened()
    print("PASS - database created and opened successfully.")
