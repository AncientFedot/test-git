# Troubleshooting

## API returns 401
- Obtain token via `POST /auth/login` with valid login/password.
- Send `Authorization: Bearer <token>` header.
- Ensure `BONIFACIY_API_SIGNING_KEY` is configured and stable across restarts.

## API returns 403
- Check user role and RBAC grants.
- For `/projects`, non-admin user must be owner or present in `project_members`.

## Files seem missing after update
- Ensure `BONIFACIY_DATA_DIR` points to same absolute location.
- Run `python main.py health`.
- Run `python main.py reconcile --role administrator`.

## Import shows no rows
- Check import status:
  - `success`
  - `empty`
  - `needs_review` (OCR dependencies missing or scan quality issue)
  - `failed`
- Run `python main.py ocr-runtime-check`.

## Outbox messages are not being sent
- Queue with `python main.py mail-queue ...`.
- Process queue:
  - one-shot: `python main.py mail-worker-once --batch-size 20`
  - daemon: `python main.py mail-worker-daemon --batch-size 20 --interval 15`
- Inspect queue state with `python main.py mail-outbox --account-id <id>`.

## IMAP sync does not import messages
- Validate IMAP host format (`ssl://...` or plain with STARTTLS).
- Run `python main.py mail-sync-once --account-id <id> --limit 20`.
- Check dedup by `(account_id, external_uid)`.

## Migration rollout check
- Run `python main.py migrations-preflight`.
- Run `python main.py release-gate --backup-max-age-hours 24`.
- Follow `RELEASE_GATE_CHECKLIST.md` before cutover.

## HTTPS/TLS
- Do not expose `api-server` directly to internet.
- Use reverse proxy for TLS termination, rate-limit, timeouts and logs.

## Restore failed
- Restore keeps active data snapshot and performs rollback automatically.
- Read logs in `<data-dir>/logs/bonifaciy.log` and `operation_logs` table.
