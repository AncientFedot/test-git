from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from bonifaciy.api_server import run_api_server
from bonifaciy.auth import generate_signing_key, hash_password, revoke_sessions
from bonifaciy.backup import BackupService
from bonifaciy.config import build_settings
from bonifaciy.db import managed_connection
from bonifaciy.governance import migration_preflight
from bonifaciy.importer import ImportService
from bonifaciy.mail import MailService
from bonifaciy.mail_daemon import MailDaemon
from bonifaciy.mail_transport import IMAPSyncService, SMTPTransport
from bonifaciy.mail_worker import MailWorker, MockMailTransport
from bonifaciy.migrations import MIGRATIONS, run_migrations
from bonifaciy.ops import log_operation
from bonifaciy.rbac import require_permission
from bonifaciy.release_gate import run_release_gate
from bonifaciy.security import SecurityConfigurationError, build_secret_cipher
from bonifaciy.storage import FileStorageService


LOG = logging.getLogger("bonifaciy")


def setup_logging(log_file: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file, encoding="utf-8")],
        force=True,
    )


@contextmanager
def app_context() -> tuple:
    settings = build_settings()
    setup_logging(settings.logs_dir / "bonifaciy.log")
    with managed_connection(settings.db_path) as conn:
        run_migrations(conn)
        yield settings, conn


def _success(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _execute(operation: str, handler: Callable[[argparse.Namespace, str], dict], args: argparse.Namespace) -> int:
    correlation_id = uuid.uuid4().hex
    try:
        result = handler(args, correlation_id)
        result["correlation_id"] = correlation_id
        return _success(result)
    except (SecurityConfigurationError, PermissionError) as exc:
        LOG.error("%s failed (%s): %s", operation, correlation_id, exc)
        print(json.dumps({"status": "error", "operation": operation, "correlation_id": correlation_id, "message": str(exc)}))
        return 2
    except Exception as exc:
        LOG.exception("%s failed (%s)", operation, correlation_id)
        print(json.dumps({"status": "error", "operation": operation, "correlation_id": correlation_id, "message": str(exc)}))
        return 1


def _authorize(conn, role: str, permission: str) -> None:
    require_permission(conn, role, permission)


def cmd_init_data(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        conn.execute(
            "INSERT OR IGNORE INTO users(id, login, role, password_hash, is_active) VALUES(1, ?, 'administrator', ?, 1)",
            (args.admin_login, hash_password(args.admin_password_hash)),
        )
        conn.execute(
            "INSERT OR IGNORE INTO projects(id, name, status, owner_user_id, archived) VALUES(1, ?, 'active', 1, 0)",
            (args.demo_project_name,),
        )
        conn.commit()
        log_operation(conn, correlation_id, "init-data", "INFO", "seed data ensured")
        return {"status": "ok", "message": "seed data ensured"}


def cmd_health(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (settings, conn):
        log_operation(conn, correlation_id, "health", "INFO", "health check executed")
        LOG.info(
            "paths data_dir=%s db=%s uploads=%s logs=%s backups=%s",
            settings.data_dir,
            settings.db_path,
            settings.uploads_dir,
            settings.logs_dir,
            settings.backups_dir,
        )
        return {
            "status": "ok",
            "data_dir": str(settings.data_dir),
            "db": str(settings.db_path),
            "uploads": str(settings.uploads_dir),
            "logs": str(settings.logs_dir),
            "backups": str(settings.backups_dir),
        }


def cmd_upload(args: argparse.Namespace, correlation_id: str) -> dict:
    path = Path(args.file)
    with app_context() as (settings, conn):
        _authorize(conn, args.role, "documents.write")
        storage = FileStorageService(settings.uploads_dir, settings.temp_dir)
        doc_id = storage.save_document(
            conn,
            project_id=args.project_id,
            category=args.category,
            status=args.status,
            original_name=path.name,
            content=path.read_bytes(),
            visibility_scope=args.visibility,
            correlation_id=correlation_id,
            created_by=args.user_id,
        )
        log_operation(conn, correlation_id, "upload", "INFO", f"document_id={doc_id}")
        return {"status": "ok", "document_id": doc_id}


def cmd_reconcile(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (settings, conn):
        _authorize(conn, args.role, "documents.read")
        storage = FileStorageService(settings.uploads_dir, settings.temp_dir)
        result = storage.reconcile(conn)
        if args.cleanup and result["orphaned_files"]:
            removed = storage.clear_orphans(result["orphaned_files"])
            result["orphaned_files_removed"] = removed
        log_operation(conn, correlation_id, "reconcile", "INFO", json.dumps(result, ensure_ascii=False))
        return {"status": "ok", **result}


def cmd_backup(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (settings, conn):
        _authorize(conn, args.role, "backup.run")
        service = BackupService(settings.data_dir, settings.db_path, settings.uploads_dir, settings.backups_dir)
        res = service.create_backup(conn)
        log_operation(conn, correlation_id, "backup", "INFO", f"archive={res.archive_path}")
        return {"status": "ok", "archive": str(res.archive_path), "manifest": str(res.manifest_path), "checksum": res.checksum}


def cmd_restore(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (settings, conn):
        _authorize(conn, args.role, "restore.run")
        service = BackupService(settings.data_dir, settings.db_path, settings.uploads_dir, settings.backups_dir)
        service.restore(Path(args.archive))
        log_operation(conn, correlation_id, "restore", "INFO", f"archive={args.archive}")
        return {"status": "restored", "archive": args.archive}


def cmd_import(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "imports.run")
        importer = ImportService(conn)
        diag = importer.import_file(Path(args.file))
        log_operation(conn, correlation_id, "import", "INFO", f"status={diag.status}; parser={diag.parser}")
        return {"status": "ok", "import": diag.__dict__}


def cmd_security_check(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "security.check")
        build_secret_cipher()
        log_operation(conn, correlation_id, "security-check", "INFO", "secret backend configuration valid")
        return {"status": "ok", "message": "Secret backend configuration is valid"}


def cmd_mail_account(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "mail.write")
        cipher = build_secret_cipher()
        mail = MailService(conn, cipher)
        account = mail.upsert_account(
            user_id=args.user_id,
            email=args.email,
            imap_host=args.imap,
            smtp_host=args.smtp,
            secret=args.secret,
        )
        log_operation(conn, correlation_id, "mail-account", "INFO", f"account_id={account}")
        return {"status": "ok", "account_id": account}


def cmd_mail_sync_demo(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "mail.read")
        cipher = build_secret_cipher()
        mail = MailService(conn, cipher)
        inserted = mail.save_synced_message(
            account_id=args.account_id,
            external_uid=args.uid,
            thread_id=args.thread,
            direction=args.direction,
            subject=args.subject,
            body_preview=args.preview,
        )
        log_operation(conn, correlation_id, "mail-sync-demo", "INFO", f"account_id={args.account_id}; inserted={inserted}")
        return {"status": "ok", "inserted": inserted}


def cmd_mail_sync_once(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "mail.read")
        cipher = build_secret_cipher()
        mail = MailService(conn, cipher)
        sync = IMAPSyncService(mail)
        result = sync.sync_account(account_id=args.account_id, limit=args.limit)
        log_operation(conn, correlation_id, "mail-sync-once", "INFO", json.dumps(result))
        return {"status": "ok", **result}


def cmd_mail_queue(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "mail.write")
        cipher = build_secret_cipher()
        mail = MailService(conn, cipher)
        message_id = mail.queue_outgoing_message(
            account_id=args.account_id,
            recipient=args.to,
            subject=args.subject,
            body=args.body,
        )
        log_operation(conn, correlation_id, "mail-queue", "INFO", f"message_id={message_id}")
        return {"status": "ok", "message_id": message_id}


def cmd_mail_outbox(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "mail.read")
        cipher = build_secret_cipher()
        mail = MailService(conn, cipher)
        rows = mail.list_outbox(account_id=args.account_id)
        items = [dict(row) for row in rows]
        log_operation(conn, correlation_id, "mail-outbox", "INFO", f"rows={len(items)}")
        return {"status": "ok", "items": items}


def _build_worker(conn, fail_first_n: int, mock: bool):
    cipher = build_secret_cipher()
    mail = MailService(conn, cipher)
    transport = MockMailTransport(fail_first_n=fail_first_n) if mock else SMTPTransport(mail)
    return MailWorker(mail, transport)


def cmd_mail_worker_once(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "mail.write")
        worker = _build_worker(conn, args.fail_first_n, args.mock)
        result = worker.run_once(batch_size=args.batch_size)
        payload = {
            "processed": result.processed,
            "sent": result.sent,
            "retried": result.retried,
            "failed": result.failed,
        }
        log_operation(conn, correlation_id, "mail-worker-once", "INFO", json.dumps(payload))
        return {"status": "ok", **payload}


def cmd_mail_worker_daemon(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        _authorize(conn, args.role, "mail.write")
        worker = _build_worker(conn, args.fail_first_n, args.mock)
        daemon = MailDaemon(worker)
        stats = daemon.run(
            interval_seconds=args.interval,
            iterations=args.iterations,
            batch_size=args.batch_size,
        )
        payload = stats.__dict__
        log_operation(conn, correlation_id, "mail-worker-daemon", "INFO", json.dumps(payload))
        return {"status": "ok", **payload}


def cmd_migrations_preflight(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        check = migration_preflight(conn, latest_version=len(MIGRATIONS))
        payload = check.__dict__
        log_operation(conn, correlation_id, "migrations-preflight", "INFO", json.dumps(payload))
        return {"status": "ok", **payload}


def cmd_api_server(args: argparse.Namespace, correlation_id: str) -> dict:
    settings = build_settings()
    setup_logging(settings.logs_dir / "bonifaciy.log")
    LOG.info("Starting API server on %s:%s", args.host, args.port)
    run_api_server(settings.db_path, host=args.host, port=args.port)
    return {"status": "stopped"}


def _add_role_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--role", default="administrator")




def cmd_ocr_runtime_check(args: argparse.Namespace, correlation_id: str) -> dict:
    deps = {}
    for module in ("pdf2image", "pytesseract", "pypdf", "openpyxl", "docx"):
        try:
            __import__(module)
            deps[module] = "ok"
        except Exception as exc:
            deps[module] = f"missing: {exc}"
    return {"status": "ok", "dependencies": deps}


def cmd_release_gate(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        pre = migration_preflight(conn, latest_version=len(MIGRATIONS))
        report = run_release_gate(
            conn,
            pending_migrations=pre.pending,
            preflight_compatible=pre.compatible,
            backup_max_age_hours=args.backup_max_age_hours,
        )
        log_operation(conn, correlation_id, "release-gate", "INFO", json.dumps(report.__dict__))
        return {"status": "ok", **report.__dict__}



def cmd_revoke_sessions(args: argparse.Namespace, correlation_id: str) -> dict:
    with app_context() as (_settings, conn):
        count = revoke_sessions(conn, user_id=args.user_id)
        log_operation(conn, correlation_id, "revoke-sessions", "INFO", f"revoked={count}")
        return {"status": "ok", "revoked": count}


def cmd_generate_signing_key(args: argparse.Namespace, correlation_id: str) -> dict:
    return {"status": "ok", "signing_key": generate_signing_key()}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bonifaciy operations CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-data")
    p.add_argument("--admin-login", default="admin")
    p.add_argument("--admin-password-hash", default="dev-only-change-me")
    p.add_argument("--demo-project-name", default="Demo Project")
    p.set_defaults(operation="init-data", handler=cmd_init_data)

    p = sub.add_parser("health")
    p.set_defaults(operation="health", handler=cmd_health)

    p = sub.add_parser("upload")
    p.add_argument("file")
    p.add_argument("--project-id", type=int, default=1)
    p.add_argument("--category", default="specification")
    p.add_argument("--status", default="attached")
    p.add_argument("--visibility", default="project")
    p.add_argument("--user-id", type=int, default=1)
    _add_role_arg(p)
    p.set_defaults(operation="upload", handler=cmd_upload)

    p = sub.add_parser("reconcile")
    p.add_argument("--cleanup", action="store_true", help="Remove orphaned files found on disk")
    _add_role_arg(p)
    p.set_defaults(operation="reconcile", handler=cmd_reconcile)

    p = sub.add_parser("backup")
    _add_role_arg(p)
    p.set_defaults(operation="backup", handler=cmd_backup)

    p = sub.add_parser("restore")
    p.add_argument("archive")
    _add_role_arg(p)
    p.set_defaults(operation="restore", handler=cmd_restore)

    p = sub.add_parser("import")
    p.add_argument("file")
    _add_role_arg(p)
    p.set_defaults(operation="import", handler=cmd_import)

    p = sub.add_parser("security-check")
    _add_role_arg(p)
    p.set_defaults(operation="security-check", handler=cmd_security_check)

    p = sub.add_parser("mail-account")
    p.add_argument("--user-id", type=int, default=1)
    p.add_argument("--email", required=True)
    p.add_argument("--imap", required=True)
    p.add_argument("--smtp", required=True)
    p.add_argument("--secret", required=True)
    _add_role_arg(p)
    p.set_defaults(operation="mail-account", handler=cmd_mail_account)

    p = sub.add_parser("mail-sync-demo")
    p.add_argument("--account-id", required=True, type=int)
    p.add_argument("--uid", required=True)
    p.add_argument("--thread", default=None)
    p.add_argument("--direction", default="incoming")
    p.add_argument("--subject", default="Demo")
    p.add_argument("--preview", default="Preview")
    _add_role_arg(p)
    p.set_defaults(operation="mail-sync-demo", handler=cmd_mail_sync_demo)

    p = sub.add_parser("mail-sync-once")
    p.add_argument("--account-id", required=True, type=int)
    p.add_argument("--limit", type=int, default=20)
    _add_role_arg(p)
    p.set_defaults(operation="mail-sync-once", handler=cmd_mail_sync_once)

    p = sub.add_parser("mail-outbox")
    p.add_argument("--account-id", required=False, type=int)
    _add_role_arg(p)
    p.set_defaults(operation="mail-outbox", handler=cmd_mail_outbox)

    p = sub.add_parser("mail-worker-once")
    p.add_argument("--batch-size", type=int, default=20)
    p.add_argument("--mock", action="store_true", help="Use mock transport instead of SMTP")
    p.add_argument("--fail-first-n", type=int, default=0, help="Debug option for simulated SMTP failures")
    _add_role_arg(p)
    p.set_defaults(operation="mail-worker-once", handler=cmd_mail_worker_once)

    p = sub.add_parser("mail-worker-daemon")
    p.add_argument("--batch-size", type=int, default=20)
    p.add_argument("--interval", type=int, default=15)
    p.add_argument("--iterations", type=int, default=None)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--fail-first-n", type=int, default=0)
    _add_role_arg(p)
    p.set_defaults(operation="mail-worker-daemon", handler=cmd_mail_worker_daemon)

    p = sub.add_parser("mail-queue")
    p.add_argument("--account-id", required=True, type=int)
    p.add_argument("--to", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--body", required=True)
    _add_role_arg(p)
    p.set_defaults(operation="mail-queue", handler=cmd_mail_queue)

    p = sub.add_parser("migrations-preflight")
    p.set_defaults(operation="migrations-preflight", handler=cmd_migrations_preflight)

    p = sub.add_parser("ocr-runtime-check")
    p.set_defaults(operation="ocr-runtime-check", handler=cmd_ocr_runtime_check)

    p = sub.add_parser("release-gate")
    p.add_argument("--backup-max-age-hours", type=int, default=24)
    p.set_defaults(operation="release-gate", handler=cmd_release_gate)

    p = sub.add_parser("revoke-sessions")
    p.add_argument("--user-id", type=int, default=None)
    p.set_defaults(operation="revoke-sessions", handler=cmd_revoke_sessions)

    p = sub.add_parser("generate-signing-key")
    p.set_defaults(operation="generate-signing-key", handler=cmd_generate_signing_key)

    p = sub.add_parser("api-server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", default=8080, type=int)
    p.set_defaults(operation="api-server", handler=cmd_api_server)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(_execute(args.operation, args.handler, args))
