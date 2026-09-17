"""
A very small test: can we create and open the database?

Run it with either:
    python tests/test_database_connection.py
    pytest tests/test_database_connection.py
"""

import sys
from pathlib import Path

# Let this file find the `database` package by adding the project root
# (one folder up from tests/) to Python's import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import DB_PATH, get_connection, init_db


def test_database_opens():
    # 1. Create the database file.
    init_db()

    # 2. The file should now exist on disk.
    assert DB_PATH.exists(), f"Database file was not created at {DB_PATH}"

    # 3. We should be able to open it and run a query.
    connection = get_connection()
    try:
        result = connection.execute("SELECT 1 AS ok;").fetchone()
        assert result["ok"] == 1
    finally:
        connection.close()


if __name__ == "__main__":
    test_database_opens()
    print("PASSED: database was created and opened successfully.")