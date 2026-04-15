#!/usr/bin/env bash
set -euo pipefail

API_HOST="${BONIFACIY_API_HOST:-127.0.0.1}"
API_PORT="${BONIFACIY_API_PORT:-8080}"
CHECK_SYSTEMD="${BONIFACIY_CHECK_SYSTEMD:-0}"
WORKER_SERVICE="${BONIFACIY_MAIL_WORKER_SERVICE:-bonifaciy-mail-worker}"
TLS_HOST="${BONIFACIY_TLS_HOST:-}"
REQUIRE_OCR="${BONIFACIY_REQUIRE_OCR:-1}"

check_json_field() {
  local cmd="$1"
  local expr="$2"
  local message="$3"

  local output
  output=$(eval "$cmd")
  CHECK_OUTPUT="$output" python -c "import json, os; data=json.loads(os.environ['CHECK_OUTPUT']); assert (${expr}), f'[FAIL] ${message}: {data}'; print('[OK] ${message}')"
}

check_api_bind_localhost_only() {
  local listeners=""
  if command -v ss >/dev/null 2>&1; then
    listeners=$(ss -ltnH | awk '{print $4}')
  elif command -v netstat >/dev/null 2>&1; then
    listeners=$(netstat -ltn 2>/dev/null | awk 'NR>2 {print $4}')
  else
    echo "[WARN] neither ss nor netstat found; skipping API bind check"
    return 0
  fi

  local local_hit
  local public_hit
  local_hit=$(printf '%s
' "$listeners" | grep -E "(^|:)${API_PORT}$" | grep -E "^${API_HOST}:${API_PORT}$|^127\.0\.0\.1:${API_PORT}$|^localhost:${API_PORT}$|^::1:${API_PORT}$|^\[::1\]:${API_PORT}$" || true)
  public_hit=$(printf '%s
' "$listeners" | grep -E "^0\.0\.0\.0:${API_PORT}$|^\[::\]:${API_PORT}$|^:::${API_PORT}$" || true)

  if [[ -z "$local_hit" ]]; then
    echo "[FAIL] API is not listening on ${API_HOST}:${API_PORT}"
    return 1
  fi
  if [[ -n "$public_hit" ]]; then
    echo "[FAIL] API is publicly bound on ${public_hit}; must be localhost-only"
    return 1
  fi
  echo "[OK] API bind is localhost-only (${API_HOST}:${API_PORT})"
}

check_tls_certificate() {
  if [[ -z "$TLS_HOST" ]]; then
    echo "[WARN] BONIFACIY_TLS_HOST is not set; skipping TLS certificate validation"
    return 0
  fi

  local cert_info
  cert_info=$(echo | openssl s_client -servername "$TLS_HOST" -connect "$TLS_HOST:443" 2>/dev/null | openssl x509 -noout -dates -subject) || {
    echo "[FAIL] unable to read TLS certificate from ${TLS_HOST}:443"
    return 1
  }
  echo "[OK] TLS certificate reachable for ${TLS_HOST}"
  echo "$cert_info"
}

check_mail_worker_health() {
  if [[ "$CHECK_SYSTEMD" != "1" ]]; then
    echo "[WARN] BONIFACIY_CHECK_SYSTEMD!=1; skipping systemd worker health check"
    return 0
  fi

  systemctl is-active --quiet "$WORKER_SERVICE" || {
    echo "[FAIL] systemd service '${WORKER_SERVICE}' is not active"
    return 1
  }
  echo "[OK] systemd service '${WORKER_SERVICE}' is active"
}

restore_drill_from_latest_backup() {
  local latest
  latest=$(ls -1t "${BONIFACIY_DATA_DIR}/backups"/*.tar.gz 2>/dev/null | head -n1 || true)
  if [[ -z "$latest" ]]; then
    echo "[FAIL] no backup archive found for restore drill"
    return 1
  fi
  echo "[INFO] restore drill from ${latest}"
  python main.py restore "$latest" --role administrator >/tmp/bonifaciy_restore_result.json
  python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/bonifaciy_restore_result.json').read_text(encoding='utf-8'))
if payload.get('status') != 'restored':
    raise SystemExit(f"[FAIL] restore drill: {payload}")
print('[OK] restore drill status=restored')
PY
}

echo "[INFO] checking migrations preflight"
check_json_field "python main.py migrations-preflight" "data.get('status') == 'ok' and data.get('compatible') is True" "migrations-preflight compatible=true"

echo "[INFO] checking security backend policy"
check_json_field "python main.py security-check --role administrator" "data.get('status') == 'ok'" "security-check status=ok"

echo "[INFO] checking OCR runtime"
if [[ "$REQUIRE_OCR" == "1" ]]; then
  check_json_field "python main.py ocr-runtime-check" "data.get('status') == 'ok' and all(v == 'ok' for v in data.get('dependencies', {}).values())" "ocr-runtime-check dependencies=ok"
else
  echo "[WARN] BONIFACIY_REQUIRE_OCR!=1; skipping OCR dependency gate"
fi

echo "[INFO] creating fresh backup"
python main.py backup --role administrator >/tmp/bonifaciy_backup_result.json
python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/bonifaciy_backup_result.json').read_text(encoding='utf-8'))
if payload.get('status') != 'ok':
    raise SystemExit(f"[FAIL] backup: {payload}")
print('[OK] backup status=ok')
PY

echo "[INFO] checking release gate"
check_json_field "python main.py release-gate --backup-max-age-hours 24" "data.get('status') == 'ok' and data.get('ok') is True" "release-gate ok=true"

echo "[INFO] running restore drill"
restore_drill_from_latest_backup

echo "[INFO] checking API bind mode"
check_api_bind_localhost_only

echo "[INFO] checking TLS certificate"
check_tls_certificate

echo "[INFO] checking mail worker health"
check_mail_worker_health

echo "[DONE] production readiness checks passed"
