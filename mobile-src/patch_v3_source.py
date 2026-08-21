from pathlib import Path
import re

path = Path('app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java')
text = path.read_text(encoding='utf-8')

checks = []

def replace_once(old: str, new: str, name: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{name}: expected 1 occurrence, found {count}')
    text = text.replace(old, new, 1)
    checks.append(name)

replace_once(
    's.setUserAgentString(s.getUserAgentString() + " BonifaciyChatAndroid/2.0");',
    's.setUserAgentString(s.getUserAgentString() + " BonifaciyChatAndroid/3.0");',
    'user-agent',
)

replace_once(
    '        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);\n    }',
    '''        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);\n        web.postDelayed(this::openPendingPushChatIfAny, 700L);\n    }''',
    'pending-push-on-create',
)

anchor = '''    private int dp(int v) {\n'''
insert = '''    private void openPendingPushChatIfAny() {\n        try {\n            String pending = getSharedPreferences("boni", MODE_PRIVATE)\n                    .getString("pending_push_chat_url", "");\n            if (pending == null || pending.isBlank() || base == null) return;\n\n            Uri uri;\n            if (pending.startsWith("/chat")) {\n                uri = Uri.parse(base + pending);\n            } else {\n                uri = Uri.parse(pending);\n                if (!isTrustedPortalUri(uri)) return;\n                Uri baseUri = Uri.parse(base);\n                if (baseUri.getHost() == null || uri.getHost() == null\n                        || !baseUri.getHost().equalsIgnoreCase(uri.getHost())) return;\n            }\n            String path = uri.getPath();\n            if (path == null || !path.startsWith("/chat")) return;\n\n            getSharedPreferences("boni", MODE_PRIVATE).edit()\n                    .remove("pending_push_chat_url")\n                    .remove("pending_push_chat_id")\n                    .apply();\n            web.loadUrl(uri.toString());\n        } catch (Exception ignored) {\n        }\n    }\n\n'''
replace_once(anchor, insert + anchor, 'pending-push-method')

replace_once(
    '''            public void onPageFinished(WebView v, String url) {\n                injectMobile();\n            }''',
    '''            public void onPageFinished(WebView v, String url) {\n                injectMobile();\n                PushRegistrar.scheduleRegistration(MainActivity.this, 250L, 2000L);\n            }''',
    'register-after-page-load',
)

pattern = re.compile(
    r'    private void showMessageNotification\(String author\) \{.*?\n    \}\n\n    private void injectMobile\(\) \{',
    re.S,
)
replacement = '''    private void showMessageNotification(String author, String chatTitle, String preview, String messageId) {\n        if (appInForeground) return;\n        String companyKey = "НПО БОРЕЙ".equals(companyName) ? "borey" : "rk";\n        String chatId = "local:" + (chatTitle == null ? "chat" : chatTitle);\n        NotificationHelper.showMessage(\n                this,\n                companyKey,\n                companyName,\n                chatId,\n                chatTitle,\n                author,\n                preview,\n                "",\n                messageId,\n                base == null ? "/chat" : base + "/chat",\n                1);\n    }\n\n    private void injectMobile() {'''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f'rich-local-notification-method: expected 1 replacement, found {count}')
checks.append('rich-local-notification-method')

replace_once(
    "var author=an?(an.textContent||'').trim():'';bridge.notifyNewMessage(author,id)",
    "var author=an?(an.textContent||'').trim():'';var body=x.querySelector('.chat-message-body');var preview=body?(body.textContent||'').replace(/\\s+/g,' ').trim():'';var head=document.querySelector('.chat-reset-header .brand-title');var chatTitle=head?(head.textContent||'').replace(/^(Рабочий чат:|Проектный чат:|Личная переписка:)\\s*/,'').trim():'Чат';bridge.notifyNewMessage(author,chatTitle,preview,id)",
    'rich-local-notification-js',
)

replace_once(
    '''        public void notifyNewMessage(String author, String messageId) {\n            if (!appInForeground) runOnUiThread(() -> showMessageNotification(author));\n        }''',
    '''        public void notifyNewMessage(String author, String chatTitle, String preview, String messageId) {\n            // With FCM configured the server push is authoritative. This local\n            // WebView fallback is used only when Firebase is unavailable,\n            // preventing duplicate notifications while the app is backgrounded.\n            if (!appInForeground && !BonifaciyApp.isFirebaseConfigured()) {\n                runOnUiThread(() -> showMessageNotification(author, chatTitle, preview, messageId));\n            }\n        }''',
    'rich-local-notification-bridge',
)

path.write_text(text, encoding='utf-8')
print('V3 source patch OK:', ', '.join(checks))
