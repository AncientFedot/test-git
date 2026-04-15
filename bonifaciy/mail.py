from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .security import CipherProtocol


@dataclass
class MailAccount:
    id: int
    user_id: int
    email: str


@dataclass
class OutboxMessage:
    id: int
    account_id: int
    recipient: str
    subject: str
    body: str
    attempts: int
    max_attempts: int


class MailService:
    def __init__(self, conn: sqlite3.Connection, cipher: CipherProtocol):
        self.conn = conn
        self.cipher = cipher

    def upsert_account(self, user_id: int, email: str, imap_host: str, smtp_host: str, secret: str) -> int:
        encrypted_secret = self.cipher.encrypt(secret)
        existing = self.conn.execute(
            "SELECT id FROM mail_accounts WHERE user_id = ? AND email = ?",
            (user_id, email),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE mail_accounts SET imap_host = ?, smtp_host = ?, encrypted_secret = ? WHERE id = ?",
                (imap_host, smtp_host, encrypted_secret, existing["id"]),
            )
            self.conn.commit()
            return int(existing["id"])

        cur = self.conn.execute(
            """
            INSERT INTO mail_accounts(user_id, email, imap_host, smtp_host, encrypted_secret)
            VALUES(?, ?, ?, ?, ?)
            """,
            (user_id, email, imap_host, smtp_host, encrypted_secret),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    @staticmethod
    def _dedup_key(account_id: int, recipient: str, subject: str, body: str) -> str:
        h = hashlib.sha256()
        h.update(f"{account_id}|{recipient}|{subject}|{body}".encode("utf-8"))
        return h.hexdigest()

    def queue_outgoing_message(
        self,
        *,
        account_id: int,
        recipient: str,
        subject: str,
        body: str,
        max_attempts: int = 5,
    ) -> int:
        dedup_key = self._dedup_key(account_id, recipient, subject, body)
        existing = self.conn.execute(
            """
            SELECT id FROM mail_outbox
            WHERE dedup_key = ? AND state IN ('queued', 'retry', 'processing')
            ORDER BY id DESC LIMIT 1
            """,
            (dedup_key,),
        ).fetchone()
        if existing:
            return int(existing["id"])

        cur = self.conn.execute(
            """
            INSERT INTO mail_outbox(
                account_id, recipient, subject, body, state, attempts,
                max_attempts, dedup_key, next_attempt_at
            )
            VALUES(?, ?, ?, ?, 'queued', 0, ?, ?, CURRENT_TIMESTAMP)
            """,
            (account_id, recipient, subject, body, max_attempts, dedup_key),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def reserve_outbox_batch(self, *, limit: int = 20) -> list[OutboxMessage]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM mail_outbox
            WHERE state IN ('queued', 'retry')
              AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP)
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        reserved: list[OutboxMessage] = []
        lock_ts = datetime.now(timezone.utc).isoformat()

        for row in rows:
            updated = self.conn.execute(
                """
                UPDATE mail_outbox
                SET state = 'processing', locked_at = ?
                WHERE id = ? AND state IN ('queued', 'retry')
                """,
                (lock_ts, row["id"]),
            )
            if updated.rowcount:
                reserved.append(
                    OutboxMessage(
                        id=int(row["id"]),
                        account_id=int(row["account_id"]),
                        recipient=row["recipient"],
                        subject=row["subject"],
                        body=row["body"],
                        attempts=int(row["attempts"]),
                        max_attempts=int(row["max_attempts"]),
                    )
                )

        self.conn.commit()
        return reserved

    def mark_outbox_sent(self, message_id: int, provider_message_id: str | None = None) -> None:
        self.conn.execute(
            """
            UPDATE mail_outbox
            SET state = 'sent', sent_at = CURRENT_TIMESTAMP,
                provider_message_id = ?, last_error = NULL, locked_at = NULL
            WHERE id = ?
            """,
            (provider_message_id, message_id),
        )
        self.conn.commit()

    def mark_outbox_attempt(self, message_id: int, success: bool, error: str | None = None) -> None:
        row = self.conn.execute(
            "SELECT attempts, max_attempts FROM mail_outbox WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Outgoing message {message_id} not found")

        attempts = int(row["attempts"]) + 1
        max_attempts = int(row["max_attempts"])

        if success:
            self.mark_outbox_sent(message_id)
            return

        if attempts >= max_attempts:
            state = "failed"
            next_attempt_at = None
        else:
            state = "retry"
            wait_seconds = min(300, 2 ** attempts)
            next_attempt_at = (datetime.now(timezone.utc) + timedelta(seconds=wait_seconds)).isoformat()

        self.conn.execute(
            """
            UPDATE mail_outbox
            SET attempts = ?, state = ?, last_error = ?,
                next_attempt_at = ?, locked_at = NULL
            WHERE id = ?
            """,
            (attempts, state, error, next_attempt_at, message_id),
        )
        self.conn.commit()

    def save_synced_message(
        self,
        *,
        account_id: int,
        external_uid: str,
        thread_id: str | None,
        direction: str,
        subject: str,
        body_preview: str,
    ) -> bool:
        try:
            self.conn.execute(
                """
                INSERT INTO mail_messages(account_id, external_uid, thread_id, direction, subject, body_preview, sync_state)
                VALUES(?, ?, ?, ?, ?, ?, 'synced')
                """,
                (account_id, external_uid, thread_id, direction, subject, body_preview),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


    def get_message_id(self, account_id: int, external_uid: str) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM mail_messages WHERE account_id = ? AND external_uid = ?",
            (account_id, external_uid),
        ).fetchone()
        return int(row["id"]) if row else None

    def save_attachment_meta(self, *, message_id: int, filename: str, content_type: str | None, size_bytes: int | None) -> None:
        self.conn.execute(
            """
            INSERT INTO mail_attachments(message_id, filename, content_type, size_bytes)
            VALUES(?, ?, ?, ?)
            """,
            (message_id, filename, content_type, size_bytes),
        )
        self.conn.commit()

    def list_user_messages(self, user_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT mm.*
            FROM mail_messages mm
            JOIN mail_accounts ma ON ma.id = mm.account_id
            WHERE ma.user_id = ?
            ORDER BY mm.created_at DESC
            """,
            (user_id,),
        ).fetchall()

    def list_outbox(self, account_id: int | None = None) -> list[sqlite3.Row]:
        if account_id is None:
            return self.conn.execute(
                "SELECT * FROM mail_outbox ORDER BY id DESC"
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM mail_outbox WHERE account_id = ? ORDER BY id DESC",
            (account_id,),
        ).fetchall()
