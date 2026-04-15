# Architecture and Data Paths

## Layers
- `config.py`: stable absolute paths and environment-driven settings.
- `db.py` + `migrations.py`: schema lifecycle and transactional guarantees.
- `governance.py` + `release_gate.py`: migration and release preflight checks.
- `auth.py`: password hashing, token issuing, API session validation.
- `rbac.py`: permission matrix checks.
- `storage.py`: staged file write/publish/rollback and file reconciliation.
- `backup.py`: manifest-based backup and staging restore with upload file checksums.
- `importer.py`: parser diagnostics and OCR fallback attempt.
- `mail.py` + `mail_transport.py` + `mail_worker.py` + `mail_daemon.py`:
  account isolation, queue lifecycle, SMTP send, IMAP sync, daemon scheduler.
- `security.py`: pluggable secret encryption backends with production policy enforcement.
- `ops.py`: operation log writes with correlation id.
- `api_server.py`: HTTP API with bearer auth + RBAC/object-scope checks.
- `main.py`: operator-facing CLI with unified error handling.

## Persistent paths
All live under `BONIFACIY_DATA_DIR`:
- `db/bonifaciy.sqlite3`
- `uploads/`
- `logs/`
- `backups/`
- `quarantine/`
- `tmp/`

No operational data is stored in the release folder.

## Safety principles
1. Files are staged then published and registered in DB atomically.
2. Restore is verified in staging before replacing active data.
3. Backup manifest includes file-level checksums for uploads.
4. Mail outbox has dedup/reservation/retry/fail lifecycle.
5. API requires login/token sessions (no anonymous data access).
6. Critical operations include correlation ids and operation logs.
7. Production secrets use fernet backend with explicit key provisioning.
