# Bonifaciy (production operations core)

Bonifaciy is a hardened operational core for MTO CRM/ERP workflows with persistent storage, controlled migrations, safe document storage, backup/restore safety, diagnostics, RBAC checks, mail processing queues, API auth, and baseline web/API endpoints.

## What is implemented

- Stable persistent **data directory** independent from release folder.
- Managed SQLite migrations + migration preflight compatibility checks.
- Atomic staged file upload and safe file replacement.
- Backup/restore with staging validation and file-level upload checksums in manifest.
- Import diagnostics with parser status and OCR fallback attempt for scanned PDFs.
- Mail subsystem:
  - isolated user mail accounts,
  - encrypted secret at rest via pluggable backend,
  - synced-message dedup,
  - outbox queue with reservation/retry/backoff/failed,
  - SMTP transport and IMAP sync service,
  - attachment metadata capture and thread references.
- Worker daemon mode (`mail-worker-daemon`) and one-shot mode.
- RBAC tables + object-level scope via project membership in API project listing.
- API auth via `/auth/login` bearer token sessions (`api_sessions`).
- Minimal HTTP API server (`/health`, `/projects`, `/mail/outbox`) + simple `/ui` page.

## Quick start

```bash
export BONIFACIY_DATA_DIR=/srv/bonifaciy-data
export BONIFACIY_SECRET_KEY='change-me-very-long-random-key'
export BONIFACIY_API_SIGNING_KEY='change-me-too'
python main.py init-data --admin-password-hash 'CHANGE_ME'
python main.py health
```

## Security/Secrets bootstrap

1. Install secure backend dependency:
   ```bash
   pip install cryptography
   ```
2. Generate Fernet key and set env:
   ```bash
   python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
   ```
3. Validate secret configuration:
   ```bash
   python main.py security-check --role administrator
   ```

## Main commands

```bash
python main.py init-data --admin-password-hash 'CHANGE_ME'
python main.py migrations-preflight
python main.py release-gate --backup-max-age-hours 24
python main.py ocr-runtime-check
python main.py security-check --role administrator
python main.py backup --role administrator
python main.py import ./spec.xlsx --role mto
python main.py mail-account --user-id 1 --email user@example.com --imap ssl://imap.example.com --smtp starttls://smtp.example.com --secret app-password --role mto
python main.py mail-sync-once --account-id 1 --limit 20 --role mto
python main.py mail-queue --account-id 1 --to vendor@example.com --subject RFQ --body 'Please send quote' --role mto
python main.py mail-worker-once --batch-size 20 --role mto
python main.py mail-worker-daemon --batch-size 20 --interval 15 --iterations 100 --role mto
python main.py api-server --host 127.0.0.1 --port 8080
```

## Production runbook assets

- env template: `ops/prod.env.example`
- Nginx reverse-proxy template: `ops/nginx/bonifaciy.conf`
- Linux services: `ops/systemd/bonifaciy-api.service`, `ops/systemd/bonifaciy-mail-worker.service`
- Windows/NSSM service setup: `ops/windows/nssm-setup.txt`
- automated readiness checks: `scripts/prod_readiness_check.sh`
- security incident helper: `scripts/security_incident_rotate.sh`

## Operational docs
- `DEPLOYMENT.md`
- `BACKUP_RESTORE.md`
- `UPGRADE.md`
- `TROUBLESHOOTING.md`
- `SECRETS_POLICY.md`
- `RELEASE_GATE_CHECKLIST.md`

## Testing

```bash
python -m unittest discover -s tests -v
```
