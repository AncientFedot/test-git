# Release Gate Checklist

## Pre-cutover
- [ ] `python main.py migrations-preflight` returns `compatible=true`.
- [ ] `python main.py security-check --role administrator` returns `status=ok`.
- [ ] `python main.py ocr-runtime-check` returns all required dependencies as `ok`.
- [ ] fresh backup exists (`python main.py backup --role administrator`).
- [ ] restore drill from latest backup verified successfully.
- [ ] `python main.py release-gate --backup-max-age-hours 24` returns `ok=true`.
- [ ] reverse proxy TLS certificate is valid and not expiring.
- [ ] API bound to localhost only (`127.0.0.1:8080`) and NOT `0.0.0.0:8080`.
- [ ] mail worker service is healthy (`systemctl status bonifaciy-mail-worker` or NSSM equivalent).

## One-command gate (recommended)
```bash
BONIFACIY_TLS_HOST=api.example.com BONIFACIY_CHECK_SYSTEMD=1 ./scripts/prod_readiness_check.sh
```
Notes:
- `BONIFACIY_TLS_HOST` validates TLS cert via `openssl s_client`.
- `BONIFACIY_CHECK_SYSTEMD=1` enforces worker health via `systemctl is-active`.
- OCR check is mandatory by default (`BONIFACIY_REQUIRE_OCR=1`).

## Cutover
- [ ] stop old release workers
- [ ] start new API and mail daemon
- [ ] run smoke checks:
  - [ ] `/health`
  - [ ] `/auth/login`
  - [ ] `/projects` with valid token
  - [ ] enqueue one mail (`mail-queue`) and deliver (`mail-worker-once`)

## Post-cutover
- [ ] check operation logs for errors
- [ ] check outbox retry/failed rates
- [ ] check API 401/403 anomaly rate
- [ ] confirm no data-dir path drift
- [ ] keep rollback window and previous release artifacts until stabilisation period ends
