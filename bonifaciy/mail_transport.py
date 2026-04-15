from __future__ import annotations

import email
import imaplib
import smtplib
from email.message import EmailMessage
from typing import Iterable

from .mail import MailService, OutboxMessage


class SMTPTransport:
    def __init__(self, mail_service: MailService):
        self.mail_service = mail_service

    def send(self, message: OutboxMessage) -> str:
        account = self.mail_service.conn.execute(
            "SELECT * FROM mail_accounts WHERE id = ?",
            (message.account_id,),
        ).fetchone()
        if account is None:
            raise ValueError(f"Mail account {message.account_id} not found")

        secret = self.mail_service.cipher.decrypt(account["encrypted_secret"])
        sender = account["email"]

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = message.recipient
        msg["Subject"] = message.subject
        msg.set_content(message.body)

        host = account["smtp_host"]
        if host.startswith("ssl://"):
            smtp_host = host.replace("ssl://", "", 1)
            with smtplib.SMTP_SSL(smtp_host, 465, timeout=20) as client:
                client.login(sender, secret)
                client.send_message(msg)
        else:
            smtp_host = host.replace("starttls://", "", 1)
            with smtplib.SMTP(smtp_host, 587, timeout=20) as client:
                client.starttls()
                client.login(sender, secret)
                client.send_message(msg)

        return msg.get("Message-ID", "") or f"smtp-{message.id}"


class IMAPSyncService:
    def __init__(self, mail_service: MailService):
        self.mail_service = mail_service

    def sync_account(self, account_id: int, limit: int = 20) -> dict[str, int]:
        account = self.mail_service.conn.execute(
            "SELECT * FROM mail_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if account is None:
            raise ValueError(f"Mail account {account_id} not found")

        secret = self.mail_service.cipher.decrypt(account["encrypted_secret"])
        email_addr = account["email"]
        host = account["imap_host"]

        if host.startswith("ssl://"):
            imap_host = host.replace("ssl://", "", 1)
            client = imaplib.IMAP4_SSL(imap_host)
        else:
            client = imaplib.IMAP4(host)
            client.starttls()

        inserted = skipped = 0
        try:
            client.login(email_addr, secret)
            client.select("INBOX")
            status, data = client.search(None, "ALL")
            if status != "OK":
                return {"inserted": 0, "skipped": 0}

            ids = data[0].split()[-limit:]
            for msg_id in ids:
                fetch_status, payload = client.fetch(msg_id, "(RFC822)")
                if fetch_status != "OK" or not payload or not payload[0]:
                    skipped += 1
                    continue

                raw = payload[0][1]
                parsed = email.message_from_bytes(raw)
                subject = parsed.get("Subject", "(no subject)")
                thread = parsed.get("In-Reply-To") or parsed.get("References") or parsed.get("Message-ID")
                body_preview = self._extract_preview(parsed)
                ext_uid = msg_id.decode("utf-8", errors="ignore")
                was_inserted = self.mail_service.save_synced_message(
                    account_id=account_id,
                    external_uid=ext_uid,
                    thread_id=thread,
                    direction="incoming",
                    subject=subject,
                    body_preview=body_preview,
                )
                message_id = self.mail_service.get_message_id(account_id, ext_uid)
                if message_id is not None:
                    for part in parsed.walk():
                        if part.get_content_disposition() == "attachment":
                            payload = part.get_payload(decode=True) or b""
                            self.mail_service.save_attachment_meta(
                                message_id=message_id,
                                filename=part.get_filename() or "attachment.bin",
                                content_type=part.get_content_type(),
                                size_bytes=len(payload),
                            )
                if was_inserted:
                    inserted += 1
                else:
                    skipped += 1
        finally:
            try:
                client.logout()
            except Exception:
                pass

        return {"inserted": inserted, "skipped": skipped}

    @staticmethod
    def _extract_preview(parsed_message: email.message.Message) -> str:
        if parsed_message.is_multipart():
            for part in parsed_message.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode(errors="ignore")[:500]
            return ""
        payload = parsed_message.get_payload(decode=True) or b""
        return payload.decode(errors="ignore")[:500]
