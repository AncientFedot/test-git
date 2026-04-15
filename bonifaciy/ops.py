from __future__ import annotations

import sqlite3


def log_operation(conn: sqlite3.Connection, correlation_id: str, operation: str, level: str, message: str) -> None:
    conn.execute(
        """
        INSERT INTO operation_logs(correlation_id, operation, level, message)
        VALUES(?, ?, ?, ?)
        """,
        (correlation_id, operation, level, message),
    )
    conn.commit()
