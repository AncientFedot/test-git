from __future__ import annotations

import sqlite3


def has_permission(conn: sqlite3.Connection, role: str, permission: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE r.code = ? AND p.code = ?
        LIMIT 1
        """,
        (role, permission),
    ).fetchone()
    return row is not None


def require_permission(conn: sqlite3.Connection, role: str, permission: str) -> None:
    if not has_permission(conn, role, permission):
        raise PermissionError(f"Role '{role}' does not have permission '{permission}'")
