#!/usr/bin/env bash
set -euo pipefail

TARGET_USER_ID="${1:-}"

echo "[INFO] generate new API signing key candidate"
python main.py generate-signing-key

echo "[INFO] revoke API sessions"
if [[ -n "$TARGET_USER_ID" ]]; then
  python main.py revoke-sessions --user-id "$TARGET_USER_ID"
else
  python main.py revoke-sessions
fi

echo "[DONE] session revocation completed; update secret manager with new key and redeploy"
