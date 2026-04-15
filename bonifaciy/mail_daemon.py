from __future__ import annotations

import time
from dataclasses import dataclass

from .mail_worker import MailWorkerResult


@dataclass
class DaemonStats:
    iterations: int = 0
    processed: int = 0
    sent: int = 0
    retried: int = 0
    failed: int = 0


class MailDaemon:
    def __init__(self, worker):
        self.worker = worker

    def run(self, *, interval_seconds: int = 15, iterations: int | None = None, batch_size: int = 20) -> DaemonStats:
        stats = DaemonStats()
        while True:
            result: MailWorkerResult = self.worker.run_once(batch_size=batch_size)
            stats.iterations += 1
            stats.processed += result.processed
            stats.sent += result.sent
            stats.retried += result.retried
            stats.failed += result.failed

            if iterations is not None and stats.iterations >= iterations:
                return stats
            time.sleep(interval_seconds)
