from __future__ import annotations

from dataclasses import dataclass

from .mail import MailService, OutboxMessage


class MailTransport:
    def send(self, message: OutboxMessage) -> str:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class MockMailTransport(MailTransport):
    fail_first_n: int = 0

    def __post_init__(self) -> None:
        self._count = 0

    def send(self, message: OutboxMessage) -> str:
        self._count += 1
        if self._count <= self.fail_first_n:
            raise RuntimeError("Simulated SMTP failure")
        return f"mock-{message.id}-{self._count}"


@dataclass
class MailWorkerResult:
    processed: int
    sent: int
    retried: int
    failed: int


class MailWorker:
    def __init__(self, service: MailService, transport: MailTransport):
        self.service = service
        self.transport = transport

    def run_once(self, *, batch_size: int = 20) -> MailWorkerResult:
        queue = self.service.reserve_outbox_batch(limit=batch_size)
        processed = sent = retried = failed = 0

        for message in queue:
            processed += 1
            try:
                provider_id = self.transport.send(message)
            except Exception as exc:
                self.service.mark_outbox_attempt(message.id, success=False, error=str(exc))
                row = self.service.conn.execute("SELECT state FROM mail_outbox WHERE id = ?", (message.id,)).fetchone()
                if row and row["state"] == "failed":
                    failed += 1
                else:
                    retried += 1
            else:
                self.service.mark_outbox_sent(message.id, provider_message_id=provider_id)
                sent += 1

        return MailWorkerResult(processed=processed, sent=sent, retried=retried, failed=failed)
