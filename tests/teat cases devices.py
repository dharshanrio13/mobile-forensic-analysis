"""
Small test: create the tables, insert one case and one device, then
retrieve the device belonging to that case.

Run from the project root (mobile-forensic-analysis/):

    python tests/test_cases_devices.py

or:

    pytest tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import DATABASE_PATH, get_connection, init_db


def test_insert_case_and_device():
    # Start from a clean file so this test is predictable to re-run.
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    init_db()  # creates forensic.db and the cases/devices tables

    connection = get_connection()
    try:
        # Insert one case.
        cursor = connection.execute(
            """
            INSERT INTO cases (case_number, case_name, description, status)
            VALUES (?, ?, ?, ?);
            """,
            ("CASE-2026-001", "Sample Investigation", "Test case", "open"),
        )
        case_id = cursor.lastrowid

        # Insert one device belonging to that case.
        connection.execute(
            """
            INSERT INTO devices (
                case_id, device_name, manufacturer, model,
                operating_system, os_version, device_identifier
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (case_id, "Suspect Phone", "Samsung", "Galaxy S21",
             "Android", "13", "IMEI-123456789"),
        )
        connection.commit()

        # Retrieve the device(s) belonging to that case.
        devices = connection.execute(
            "SELECT * FROM devices WHERE case_id = ?;",
            (case_id,),
        ).fetchall()

        assert len(devices) == 1
        assert devices[0]["device_name"] == "Suspect Phone"
        assert devices[0]["case_id"] == case_id

        print(f"Case '{devices[0]['device_name']}' is linked to case_id={case_id}")
    finally:
        connection.close()


if __name__ == "__main__":
    test_insert_case_and_device()
    print("PASS - case and device inserted and linked correctly.")