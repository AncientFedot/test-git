# Changelog

## 2026-04-15 (Readiness gate hardening)
- Extended `scripts/prod_readiness_check.sh` with restore drill, API localhost-bind check, optional TLS certificate check, and optional systemd worker health check.
- Added `scripts/security_incident_rotate.sh` helper for signing-key rotation workflow and session revocation.
- Updated deployment and release checklist docs with one-command gate usage and required environment flags.

## 2026-04-15 (Production go-live runbook assets)
- Added production environment template: `ops/prod.env.example`.
- Added reverse-proxy reference config: `ops/nginx/bonifaciy.conf`.
- Added Linux systemd units: `ops/systemd/bonifaciy-api.service`, `ops/systemd/bonifaciy-mail-worker.service`.
- Added Windows NSSM setup guide: `ops/windows/nssm-setup.txt`.
- Added automated readiness script: `scripts/prod_readiness_check.sh`.
- Updated deployment, release gate, secrets, upgrade, and README docs with explicit cutover/rollback and key rotation/session revocation flow.

## 2026-04-15 (Auth/API/TLS readiness + governance)
- Added API auth subsystem (`auth.py`): password hashing, token issuance, session validation.
- Added `api_sessions`, `project_members`, and `mail_attachments` tables (migration v5).
- Upgraded API server to require bearer auth (except `/health`, `/auth/login`, `/ui`).
- Added object-level scope for project listing (owner/member visibility for non-admin users).
- Extended IMAP sync to capture attachment metadata and better thread reference mapping.
- Added release governance gate (`release_gate.py`) and CLI command `release-gate`.
- Added OCR runtime dependency check command `ocr-runtime-check`.
- Added operational docs: `SECRETS_POLICY.md`, `RELEASE_GATE_CHECKLIST.md` and deployment updates.

## 2026-04-15 (Production readiness foundation expansion)
- Added real mail transport layer (SMTP send + IMAP sync).
- Added mail daemon scheduler and CLI daemon command.
- Upgraded backup manifest with file-level upload checksums.
- Added RBAC core tables and CLI permission checks.
- Added migration governance preflight and API baseline.
- Extended tests for daemon/outbox lifecycle, backup manifest checks, RBAC, migration preflight.

## 2026-04-15 (Mail worker/outbox phase 2)
- Added `mail_worker.py` with single-run worker cycle and pluggable transport interface.
- Upgraded outbox reliability with reservation (`processing`), retry scheduling (`next_attempt_at`), max attempts and terminal `failed` state.
- Added active dedup key for queued/retry/processing messages.
- Added CLI commands: `mail-worker-once` and `mail-outbox`.
- Added migration v3 to upgrade existing outbox schemas safely.

## 2026-04-15 (Security/Secrets phase 1)
- Replaced single hardcoded secret path with pluggable secret backend strategy (`fernet` / `insecure-xor`).
- Enforced production policy: insecure backend forbidden outside development/test/local profiles.
- Added `security-check` CLI command for preflight validation of secret configuration.
