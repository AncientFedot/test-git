from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class MigrationPreflight:
    current_version: int
    latest_version: int
    pending: int
    compatible: bool
    message: str


def migration_preflight(conn: sqlite3.Connection, latest_version: int) -> MigrationPreflight:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    current = int(row[0])
    pending = max(0, latest_version - current)
    compatible = current <= latest_version
    message = "ok" if compatible else "db schema is newer than app"
    return MigrationPreflight(
        current_version=current,
        latest_version=latest_version,
        pending=pending,
        compatible=compatible,
        message=message,
    )
