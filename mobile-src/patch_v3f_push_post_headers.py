from pathlib import Path

p = Path('app/src/main/java/ru/leorix/bonifaciychat/PushRegistrar.java')
s = p.read_text(encoding='utf-8')

anchor = '            conn.setRequestProperty("X-Bonifaciy-Mobile-App", "android-v3");\n'
count = s.count(anchor)
if count != 2:
    raise SystemExit(f'Expected 2 mobile protocol header occurrences after V3E patch, found {count}')
s = s.replace(
    anchor,
    anchor +
    '            conn.setRequestProperty("Origin", base);\n' +
    '            conn.setRequestProperty("Referer", base + "/chat");\n'
)

old = '''            if (code < 200 || code >= 300) {\n                p.edit().putString("last_stage_" + company, "HTTP_ERROR").apply();\n                return;\n            }'''
new = '''            if (code < 200 || code >= 300) {\n                String errorBody = readBody(conn.getErrorStream());\n                String safeError = errorBody == null ? "" : errorBody.replaceAll("[\\r\\n\\t]+", " ").trim();\n                if (safeError.length() > 240) safeError = safeError.substring(0, 240);\n                if (safeError.isBlank()) safeError = "HTTP " + code;\n                p.edit()\n                        .putString("last_stage_" + company, "HTTP_ERROR")\n                        .putString("last_error_" + company, safeError)\n                        .apply();\n                return;\n            }'''
if s.count(old) != 1:
    raise SystemExit(f'Expected one register HTTP error block, found {s.count(old)}')
s = s.replace(old, new, 1)

s = s.replace('BonifaciyChatAndroid/3.4', 'BonifaciyChatAndroid/3.5')
s = s.replace('V3E native diagnostics', 'V3F native diagnostics')
s = s.replace('return "3.4-test";', 'return "3.5-test";')

p.write_text(s, encoding='utf-8')
print('V3F push POST headers fix OK: Origin/Referer added; HTTP error body diagnostics enabled')
