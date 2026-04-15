from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _m001_init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            owner_user_id INTEGER,
            archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL,
            original_name TEXT NOT NULL,
            storage_path TEXT NOT NULL,
            file_sha256 TEXT NOT NULL,
            visibility_scope TEXT NOT NULL,
            linked_entity_type TEXT,
            linked_entity_id TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            replaced_by INTEGER,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(created_by) REFERENCES users(id),
            FOREIGN KEY(replaced_by) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS document_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archive_path TEXT NOT NULL,
            manifest_path TEXT NOT NULL,
            checksum TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS import_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            source_filename TEXT NOT NULL,
            source_type TEXT NOT NULL,
            parser TEXT NOT NULL,
            ocr_engine TEXT,
            ocr_pages INTEGER,
            extracted_chars INTEGER NOT NULL,
            status TEXT NOT NULL,
            diagnostic TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS mail_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            imap_host TEXT NOT NULL,
            smtp_host TEXT NOT NULL,
            encrypted_secret TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS mail_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            external_uid TEXT NOT NULL,
            thread_id TEXT,
            direction TEXT NOT NULL,
            subject TEXT NOT NULL,
            body_preview TEXT NOT NULL,
            linked_entity_type TEXT,
            linked_entity_id TEXT,
            sync_state TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, external_uid),
            FOREIGN KEY(account_id) REFERENCES mail_accounts(id)
        );
        """
    )


def _m002_ops_and_outbox(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS mail_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            state TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            dedup_key TEXT,
            next_attempt_at TEXT,
            locked_at TEXT,
            sent_at TEXT,
            provider_message_id TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id) REFERENCES mail_accounts(id)
        );

        CREATE INDEX IF NOT EXISTS idx_mail_outbox_state_next_attempt
            ON mail_outbox(state, next_attempt_at);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_mail_outbox_dedup_active
            ON mail_outbox(dedup_key)
            WHERE state IN ('queued', 'retry', 'processing');
        """
    )


def _m003_outbox_upgrade(conn: sqlite3.Connection) -> None:
    alterations = [
        "ALTER TABLE mail_outbox ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 5",
        "ALTER TABLE mail_outbox ADD COLUMN dedup_key TEXT",
        "ALTER TABLE mail_outbox ADD COLUMN next_attempt_at TEXT",
        "ALTER TABLE mail_outbox ADD COLUMN locked_at TEXT",
        "ALTER TABLE mail_outbox ADD COLUMN sent_at TEXT",
        "ALTER TABLE mail_outbox ADD COLUMN provider_message_id TEXT",
    ]
    for statement in alterations:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_mail_outbox_state_next_attempt
            ON mail_outbox(state, next_attempt_at);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_mail_outbox_dedup_active
            ON mail_outbox(dedup_key)
            WHERE state IN ('queued', 'retry', 'processing');
        """
    )




def _m004_rbac(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER NOT NULL,
            permission_id INTEGER NOT NULL,
            PRIMARY KEY(role_id, permission_id),
            FOREIGN KEY(role_id) REFERENCES roles(id),
            FOREIGN KEY(permission_id) REFERENCES permissions(id)
        );
        """
    )

    roles = ["administrator", "manager", "mto", "accounting", "observer"]
    perms = [
        "projects.read", "projects.write",
        "documents.read", "documents.write",
        "mail.read", "mail.write",
        "backup.run", "restore.run",
        "imports.run", "security.check",
    ]

    for role in roles:
        conn.execute("INSERT OR IGNORE INTO roles(code) VALUES(?)", (role,))
    for perm in perms:
        conn.execute("INSERT OR IGNORE INTO permissions(code) VALUES(?)", (perm,))

    mapping = {
        "administrator": perms,
        "manager": ["projects.read", "projects.write", "documents.read", "documents.write", "mail.read", "mail.write", "imports.run"],
        "mto": ["projects.read", "documents.read", "documents.write", "mail.read", "mail.write", "imports.run"],
        "accounting": ["projects.read", "documents.read", "mail.read", "backup.run"],
        "observer": ["projects.read", "documents.read"],
    }

    for role_code, role_perms in mapping.items():
        role_id = conn.execute("SELECT id FROM roles WHERE code = ?", (role_code,)).fetchone()[0]
        for perm in role_perms:
            perm_id = conn.execute("SELECT id FROM permissions WHERE code = ?", (perm,)).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions(role_id, permission_id) VALUES(?, ?)",
                (role_id, perm_id),
            )




def _m005_api_sessions_acl_and_mail_attachments(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS api_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            is_revoked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS project_members (
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role_in_project TEXT NOT NULL DEFAULT 'member',
            PRIMARY KEY(project_id, user_id),
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS mail_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(message_id) REFERENCES mail_messages(id)
        );
        """
    )


MIGRATIONS = [
    Migration(1, "init_core_schema", _m001_init),
    Migration(2, "add_operation_logs_and_mail_outbox", _m002_ops_and_outbox),
    Migration(3, "upgrade_mail_outbox_reliability", _m003_outbox_upgrade),
    Migration(4, "add_rbac_tables", _m004_rbac),
    Migration(5, "add_api_sessions_acl_and_mail_attachments", _m005_api_sessions_acl_and_mail_attachments),
]


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    }

    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        migration.apply(conn)
        conn.execute(
            "INSERT INTO schema_migrations(version, name) VALUES(?, ?)",
            (migration.version, migration.name),
        )

    conn.commit()
