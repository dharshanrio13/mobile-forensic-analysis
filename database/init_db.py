"""
Database initialisation.

`init_db()` is the one function the application calls at startup.
Right now it only makes sure the database file exists and can be opened.

No application tables are created here yet. When the team is ready to add
tables, this is the file where those CREATE TABLE statements will go.
"""

from .connection import DB_PATH, get_connection


def init_db() -> None:
    """
    Prepare the database so the rest of the application can use it.

    Steps:
      1. Open a connection. SQLite creates database/forensic.db if missing.
      2. Run a harmless query to confirm the file really works.
      3. Commit and close.

    Safe to call every time the app starts - it does nothing destructive.
    """
    connection = get_connection()
    try:
        # A tiny query that always succeeds on a healthy database.
        connection.execute("SELECT 1;")
        connection.commit()
        print(f"[database] Ready at: {DB_PATH}")
    finally:
        # Always close, even if something above raised an error.
        connection.close()


# Lets you run this file directly to create the database:
#     python -m database.init_db
if __name__ == "__main__":
    init_db()