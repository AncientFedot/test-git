from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class ReleaseGateReport:
    ok: bool
    backup_recent: bool
    preflight_compatible: bool
    pending_migrations: int
    message: str


def run_release_gate(conn: sqlite3.Connection, pending_migrations: int, preflight_compatible: bool, backup_max_age_hours: int = 24) -> ReleaseGateReport:
    row = conn.execute("SELECT MAX(created_at) FROM backups").fetchone()
    latest_backup = row[0]

    backup_recent = False
    if latest_backup:
        try:
            dt = datetime.fromisoformat(str(latest_backup).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            backup_recent = (now - dt.astimezone(timezone.utc)) <= timedelta(hours=backup_max_age_hours)
        except Exception:
            backup_recent = False

    ok = backup_recent and preflight_compatible
    if not backup_recent:
        message = "Backup is missing or older than policy threshold"
    elif not preflight_compatible:
        message = "Migration preflight incompatible"
    elif pending_migrations > 0:
        message = f"Pending migrations detected: {pending_migrations}"
    else:
        message = "Release gate passed"

    return ReleaseGateReport(
        ok=ok,
        backup_recent=backup_recent,
        preflight_compatible=preflight_compatible,
        pending_migrations=pending_migrations,
        message=message,
    )
