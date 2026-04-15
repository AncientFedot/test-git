from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from bonifaciy.api_server import create_app
from bonifaciy.auth import hash_password
from bonifaciy.backup import BackupService
from bonifaciy.config import build_settings
from bonifaciy.db import connect
from bonifaciy.governance import migration_preflight
from bonifaciy.importer import ImportService
from bonifaciy.mail import MailService
from bonifaciy.mail_daemon import MailDaemon
from bonifaciy.mail_worker import MailWorker, MockMailTransport
from bonifaciy.migrations import MIGRATIONS, run_migrations
from bonifaciy.rbac import has_permission
from bonifaciy.release_gate import run_release_gate
from bonifaciy.security import SecurityConfigurationError, build_secret_cipher
from bonifaciy.storage import FileStorageService


def call_wsgi(app, path: str, method: str = "GET", body: dict | None = None, token: str | None = None):
    payload = json.dumps(body or {}).encode("utf-8")
    environ = {
        "PATH_INFO": path,
        "REQUEST_METHOD": method,
        "CONTENT_LENGTH": str(len(payload)),
        "wsgi.input": io.BytesIO(payload),
    }
    if token:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    status_holder = {}

    def start_response(status, headers):
        status_holder["status"] = status

    result = b"".join(app(environ, start_response))
    try:
        parsed = json.loads(result.decode("utf-8"))
    except Exception:
        parsed = result.decode("utf-8")
    return status_holder["status"], parsed


class BonifaciyCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BONIFACIY_DATA_DIR"] = self.tmp.name
        os.environ["BONIFACIY_SECRET_KEY"] = "unit-test-key"
        os.environ["BONIFACIY_SECRET_BACKEND"] = "insecure-xor"
        os.environ["BONIFACIY_ALLOW_INSECURE_SECRETS"] = "1"
        os.environ["BONIFACIY_ENV"] = "test"
        os.environ["BONIFACIY_API_SIGNING_KEY"] = "api-sign-key"
        self.settings = build_settings()
        self.conn = connect(self.settings.db_path)
        run_migrations(self.conn)
        self.conn.execute(
            "INSERT OR REPLACE INTO users(id, login, role, password_hash, is_active) VALUES(1, 'admin', 'administrator', ?, 1)",
            (hash_password("admin-pass"),),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO users(id, login, role, password_hash, is_active) VALUES(2, 'mto1', 'mto', ?, 1)",
            (hash_password("mto-pass"),),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO projects(id, name, status, owner_user_id, archived) VALUES(1, 'p', 'active', 1, 0)"
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO project_members(project_id, user_id, role_in_project) VALUES(1, 2, 'member')"
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()
        for key in [
            "BONIFACIY_DATA_DIR",
            "BONIFACIY_SECRET_KEY",
            "BONIFACIY_SECRET_BACKEND",
            "BONIFACIY_ALLOW_INSECURE_SECRETS",
            "BONIFACIY_ENV",
            "BONIFACIY_API_SIGNING_KEY",
        ]:
            os.environ.pop(key, None)

    def test_storage_and_reconcile(self) -> None:
        storage = FileStorageService(self.settings.uploads_dir, self.settings.temp_dir)
        doc_id = storage.save_document(
            self.conn,
            project_id=1,
            category="invoice",
            status="attached",
            original_name="bill.txt",
            content=b"invoice 1",
            visibility_scope="project",
            correlation_id="corr1",
            created_by=1,
        )
        self.assertGreater(doc_id, 0)
        result = storage.reconcile(self.conn)
        self.assertEqual(result["missing_on_disk"], [])
        self.assertEqual(result["orphaned_files"], [])

    def test_backup_manifest_and_restore(self) -> None:
        storage = FileStorageService(self.settings.uploads_dir, self.settings.temp_dir)
        storage.save_document(
            self.conn,
            project_id=1,
            category="specification",
            status="attached",
            original_name="spec.txt",
            content=b"spec",
            visibility_scope="project",
            correlation_id="c",
            created_by=1,
        )
        backup = BackupService(self.settings.data_dir, self.settings.db_path, self.settings.uploads_dir, self.settings.backups_dir)
        res = backup.create_backup(self.conn)
        manifest = json.loads(res.manifest_path.read_text(encoding="utf-8"))
        self.assertIn("uploads_files", manifest)

        report = run_release_gate(self.conn, pending_migrations=0, preflight_compatible=True, backup_max_age_hours=24)
        self.assertTrue(report.ok)

    def test_import_diagnostics(self) -> None:
        path = Path(self.tmp.name) / "sample.txt"
        path.write_text("hello", encoding="utf-8")
        importer = ImportService(self.conn)
        result = importer.import_file(path)
        self.assertEqual(result.status, "success")

    def test_mail_outbox_and_worker_daemon(self) -> None:
        cipher = build_secret_cipher()
        mail = MailService(self.conn, cipher)
        account_id = mail.upsert_account(1, "a@example.com", "imap.example.com", "smtp.example.com", "secret")
        msg = mail.queue_outgoing_message(
            account_id=account_id,
            recipient="b@example.com",
            subject="RFQ",
            body="Need quote",
        )
        worker = MailWorker(mail, MockMailTransport(fail_first_n=1))
        daemon = MailDaemon(worker)

        first = daemon.run(interval_seconds=0, iterations=1, batch_size=10)
        self.assertEqual(first.retried, 1)

        self.conn.execute("UPDATE mail_outbox SET next_attempt_at = CURRENT_TIMESTAMP WHERE id = ?", (msg,))
        self.conn.commit()
        second = daemon.run(interval_seconds=0, iterations=1, batch_size=10)
        self.assertEqual(second.sent, 1)

    def test_rbac_and_preflight(self) -> None:
        self.assertTrue(has_permission(self.conn, "administrator", "backup.run"))
        self.assertFalse(has_permission(self.conn, "observer", "backup.run"))

        pf = migration_preflight(self.conn, latest_version=len(MIGRATIONS))
        self.assertTrue(pf.compatible)
        self.assertEqual(pf.pending, 0)

    def test_api_auth_and_acl(self) -> None:
        app = create_app(self.settings.db_path)
        status, payload = call_wsgi(app, "/projects", "GET")
        self.assertTrue(status.startswith("401"))

        status, payload = call_wsgi(app, "/auth/login", "POST", {"login": "mto1", "password": "mto-pass"})
        self.assertTrue(status.startswith("200"))
        token = payload["token"]

        status, payload = call_wsgi(app, "/projects", "GET", token=token)
        self.assertTrue(status.startswith("200"))
        self.assertTrue(any(p["id"] == 1 for p in payload))

    def test_secret_cipher_requires_key(self) -> None:
        os.environ.pop("BONIFACIY_SECRET_KEY", None)
        with self.assertRaises(SecurityConfigurationError):
            build_secret_cipher()

    def test_insecure_backend_forbidden_in_production(self) -> None:
        os.environ["BONIFACIY_ENV"] = "production"
        with self.assertRaises(SecurityConfigurationError):
            build_secret_cipher()


if __name__ == "__main__":
    unittest.main()
