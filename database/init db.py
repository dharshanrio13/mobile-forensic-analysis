"""
Database initialization for the Mobile Device Forensic Analysis System.

init_db() is the single function the rest of the team calls at application
startup. Right now it only makes sure the database file exists and can be
opened. Table creation will be added here later.
"""

from .connection import DATABASE_PATH, get_connection
from .schema import create_all_tables


def init_db() -> None:
    """
    Prepare the database so the application can start.

    Opening a connection creates forensic.db on disk if it is not there
    yet. Then every known table is created if missing. Running this more
    than once is safe.
    """
    connection = get_connection()
    try:
        create_all_tables(connection)
    finally:
        connection.close()

    print(f"[database] Ready at: {DATABASE_PATH}")


if __name__ == "__main__":
    # Lets you run:  python -m database.init_db
    init_db()