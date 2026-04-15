# Deployment Guide

## 1) Prerequisites
- Python 3.11+
- Persistent storage path outside release directory (`BONIFACIY_DATA_DIR`)
- Secure secrets config (`BONIFACIY_SECRET_BACKEND=fernet`, `BONIFACIY_SECRET_KEY`)
- Dedicated API signing key (`BONIFACIY_API_SIGNING_KEY`, must differ from secret key)
- Reverse proxy with valid TLS cert (Nginx/IIS/Caddy)

Use production env template:
- Linux/systemd: `ops/prod.env.example` -> `/etc/bonifaciy/bonifaciy.env`
- Windows/NSSM: `ops/windows/nssm-setup.txt`

## 2) First bootstrap
```bash
cp ops/prod.env.example /etc/bonifaciy/bonifaciy.env
# edit values and set real keys
python main.py init-data --admin-login admin --admin-password-hash 'CHANGE_ME'
python main.py migrations-preflight
python main.py security-check --role administrator
python main.py release-gate --backup-max-age-hours 24
```

## 3) API runtime behind reverse proxy (required)
Run API only on localhost:
```bash
python main.py api-server --host 127.0.0.1 --port 8080
```

Do NOT expose `api-server` directly to internet.

Use reverse proxy with:
- TLS termination (HTTPS only)
- request limits/rate-limit
- timeout/retry policy
- security headers
- WAF/logging

Reference Nginx config:
- `ops/nginx/bonifaciy.conf`

## 4) Mail worker service mode
One-shot worker:
```bash
python main.py mail-worker-once --batch-size 20 --role mto
```
Daemon mode:
```bash
python main.py mail-worker-daemon --batch-size 20 --interval 15 --role mto
```

Deploy daemon as OS service:
- Linux: `ops/systemd/bonifaciy-mail-worker.service`
- Windows: NSSM steps in `ops/windows/nssm-setup.txt`

API service unit (Linux):
- `ops/systemd/bonifaciy-api.service`

## 5) OCR runtime
Install runtime dependencies on host:
- python packages: `pdf2image`, `pytesseract`, `pypdf`, `openpyxl`, `python-docx`
- binaries: `tesseract-ocr`, `poppler`

Check runtime:
```bash
python main.py ocr-runtime-check
```

## 6) Pre-cutover readiness
Recommended all-in-one script:
```bash
# Requires API process running on 127.0.0.1:8080
BONIFACIY_TLS_HOST=api.example.com BONIFACIY_CHECK_SYSTEMD=1 ./scripts/prod_readiness_check.sh
```

Script gates include:
- migration/security/OCR checks
- fresh backup + automatic restore drill
- release-gate ok=true
- API localhost-only bind validation
- TLS certificate reachability (if `BONIFACIY_TLS_HOST` is set)
- mail worker service health (if `BONIFACIY_CHECK_SYSTEMD=1`)

Manual sequence:
```bash
python main.py migrations-preflight
python main.py security-check --role administrator
python main.py ocr-runtime-check
python main.py backup --role administrator
python main.py release-gate --backup-max-age-hours 24
```

## 7) Cutover / rollback
- Follow `RELEASE_GATE_CHECKLIST.md`.
- Keep `BONIFACIY_DATA_DIR` unchanged across releases.
- Rollback steps are documented in `UPGRADE.md`.
