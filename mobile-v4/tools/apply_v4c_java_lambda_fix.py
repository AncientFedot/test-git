from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java"

s = MAIN.read_text(encoding="utf-8")
old = "                String finalUsedPath = usedPath;\n                runOnUiThread(() -> {\n                    loading(false);\n                    openDownloadedFile(r, name);\n"
new = "                String finalUsedPath = usedPath;\n                V4Core.DownloadResult finalResult = r;\n                runOnUiThread(() -> {\n                    loading(false);\n                    openDownloadedFile(finalResult, name);\n"

count = s.count(old)
if count != 1:
    raise SystemExit(f"V4C Java lambda fix anchor: expected 1, found {count}")

MAIN.write_text(s.replace(old, new, 1), encoding="utf-8")
print("V4C_JAVA_LAMBDA_FIX=OK")
