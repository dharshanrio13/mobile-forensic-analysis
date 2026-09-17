"""
Table definitions for the Mobile Device Forensic Analysis System.

Only two tables exist so far: cases and devices.
No evidence / events / communication / location / application / system-log
tables yet — those come later.
"""

# A case is the top-level forensic investigation record.
CREATE_CASES_TABLE = """
CREATE TABLE IF NOT EXISTS cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT    NOT NULL UNIQUE,
    case_name   TEXT    NOT NULL,
    description TEXT,
    status      TEXT    NOT NULL DEFAULT 'open',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# A device is a phone/tablet/etc. seized as part of a case.
# Every device must belong to exactly one case (device_id -> cases.id).
CREATE_DEVICES_TABLE = """
CREATE TABLE IF NOT EXISTS devices (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id           INTEGER NOT NULL,
    device_name       TEXT    NOT NULL,
    manufacturer      TEXT,
    model             TEXT,
    operating_system  TEXT,
    os_version        TEXT,
    device_identifier TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES cases (id)
);
"""

# Run in this order: devices references cases, so cases must exist first.
ALL_TABLES = [
    CREATE_CASES_TABLE,
    CREATE_DEVICES_TABLE,
]


def create_all_tables(connection) -> None:
    """
    Create every known table if it does not already exist.

    Safe to call repeatedly — CREATE TABLE IF NOT EXISTS is a no-op
    once the table is there.
    """
    for statement in ALL_TABLES:
        connection.execute(statement)
    connection.commit()