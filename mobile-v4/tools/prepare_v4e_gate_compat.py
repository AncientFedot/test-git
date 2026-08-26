from pathlib import Path

p = Path(__file__).resolve().with_name("apply_v4e_live_chat_sync_patch.py")
s = p.read_text(encoding="utf-8")
old = '    "no periodic sync loop": "postDelayed" not in MAIN.read_text(encoding="utf-8"),\n'
new = '''    "no periodic sync loop": all(\n        marker not in MAIN.read_text(encoding="utf-8")\n        for marker in ("syncHandler.postDelayed", "CHAT_SYNC_INTERVAL", "scheduleChatSyncPolling")\n    ),\n'''
if s.count(old) != 1:
    raise SystemExit(f"V4E gate compatibility anchor count={s.count(old)}, expected=1")
p.write_text(s.replace(old, new, 1), encoding="utf-8", newline="\n")
print("V4E_NO_POLLING_GATE_COMPAT=OK")
