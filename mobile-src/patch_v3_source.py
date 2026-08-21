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


def replace_n(old: str, new: str, expected: int, name: str) -> None:
    global text
    count = text.count(old)
    if count != expected:
        raise SystemExit(f'{name}: expected {expected} occurrences, found {count}')
    text = text.replace(old, new)
    checks.append(name)


replace_once(
    's.setUserAgentString(s.getUserAgentString() + " BonifaciyChatAndroid/2.0");',
    's.setUserAgentString(s.getUserAgentString() + " BonifaciyChatAndroid/3.1");',
    'user-agent',
)
replace_once('b.setTextSize(21);', 'b.setTextSize(18);', 'native-bar-button-font')
replace_once('root.addView(bar, new LinearLayout.LayoutParams(-1, dp(56)));',
             'root.addView(bar, new LinearLayout.LayoutParams(-1, dp(48)));',
             'native-bar-height')
replace_n('new LinearLayout.LayoutParams(dp(48), dp(48))',
          'new LinearLayout.LayoutParams(dp(42), dp(42))', 3,
          'native-bar-button-size')
replace_once('company.setTextSize(15);', 'company.setTextSize(14);', 'company-font')
replace_once('s.setUseWideViewPort(false);', 's.setUseWideViewPort(true);', 'wide-viewport')
replace_once('s.setTextZoom(100);', 's.setTextZoom(90);', 'web-text-zoom')
replace_once(
    '''        dialogs.setOnClickListener(v -> web.evaluateJavascript(
                "window.__boniToggleDialogs&&window.__boniToggleDialogs()", null));''',
    '''        dialogs.setOnClickListener(v -> web.evaluateJavascript(
                "(function(){if(document.body){document.body.classList.toggle('dialogs');return true}return false})()", null));''',
    'drawer-button-direct-toggle',
)
replace_once(
    '        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);\n    }',
    '''        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);
        web.postDelayed(this::openPendingPushChatIfAny, 700L);
    }''',
    'pending-push-on-create',
)

anchor = '''    private int dp(int v) {
'''
insert = '''    private void openPendingPushChatIfAny() {
        try {
            String pending = getSharedPreferences("boni", MODE_PRIVATE)
                    .getString("pending_push_chat_url", "");
            if (pending == null || pending.isBlank() || base == null) return;

            Uri uri;
            if (pending.startsWith("/chat")) {
                uri = Uri.parse(base + pending);
            } else {
                uri = Uri.parse(pending);
                if (!isTrustedPortalUri(uri)) return;
                Uri baseUri = Uri.parse(base);
                if (baseUri.getHost() == null || uri.getHost() == null
                        || !baseUri.getHost().equalsIgnoreCase(uri.getHost())) return;
            }
            String path = uri.getPath();
            if (path == null || !path.startsWith("/chat")) return;

            getSharedPreferences("boni", MODE_PRIVATE).edit()
                    .remove("pending_push_chat_url")
                    .remove("pending_push_chat_id")
                    .apply();
            web.loadUrl(uri.toString());
        } catch (Exception ignored) {
        }
    }

'''
replace_once(anchor, insert + anchor, 'pending-push-method')

replace_once(
    '''            public void onPageFinished(WebView v, String url) {
                injectMobile();
            }''',
    '''            public void onPageFinished(WebView v, String url) {
                injectMobile();
                PushRegistrar.scheduleRegistration(MainActivity.this, 250L, 2000L, 7000L);
            }''',
    'register-after-page-load',
)

pattern = re.compile(
    r'    private void showMessageNotification\(String author\) \{.*?\n    \}\n\n    private void injectMobile\(\) \{',
    re.S,
)
replacement = '''    private void showMessageNotification(String author, String chatTitle, String preview, String messageId) {
        if (appInForeground) return;
        String companyKey = "НПО БОРЕЙ".equals(companyName) ? "borey" : "rk";
        String chatId = "local:" + (chatTitle == null ? "chat" : chatTitle);
        NotificationHelper.showMessage(
                this,
                companyKey,
                companyName,
                chatId,
                chatTitle,
                author,
                preview,
                "",
                messageId,
                base == null ? "/chat" : base + "/chat",
                1);
    }

    private void injectMobile() {'''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f'rich-local-notification-method: expected 1 replacement, found {count}')
checks.append('rich-local-notification-method')

# Add compact V3B overrides after the older mobile rules. Later CSS wins.
css_anchor = '''

        String js = "document.body.classList.add('boniapp');" +
'''
css_override = '''
        css += "html,body{-webkit-text-size-adjust:90%!important}" +
                "body.boniapp .chat-reset-main{height:100dvh!important;padding:0 4px 4px!important;gap:5px!important}" +
                "body.boniapp .chat-reset-header{min-height:34px!important;padding:3px!important}body.boniapp .chat-reset-header .brand-title{font-size:13px!important;line-height:1.2!important}" +
                "body.boniapp #chat-box{padding:4px 1px 8px!important}" +
                "body.boniapp .chat-message{max-width:94%!important;font-size:13px!important;line-height:1.28!important;padding:7px 8px!important;border-radius:13px!important}" +
                "body.boniapp .chat-reset-composer{padding:5px!important;border-radius:13px!important}" +
                "body.boniapp #chat-message{min-height:40px!important;max-height:96px!important;font-size:14px!important;padding:8px!important;border-radius:11px!important}" +
                "body.boniapp .chat-reset-toolbar{display:block!important}" +
                "body.boniapp .chat-draft-meta-v187{margin-bottom:4px!important}" +
                "body.boniapp .chat-reset-actions{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:4px!important;width:100%!important}" +
                "body.boniapp .chat-reset-actions button,body.boniapp .chat-reset-actions .file-btn,body.boniapp .chat-send-btn{min-width:0!important;width:100%!important;min-height:38px!important;height:auto!important;padding:4px 2px!important;font-size:11.5px!important;line-height:1.1!important;border-radius:10px!important;white-space:normal!important;box-sizing:border-box!important}" +
                "body.boniapp .chat-reset-sidebar{width:min(84vw,340px)!important;padding:8px!important}" +
                "body.boniapp .chat-reset-dialog-item{min-height:46px!important;font-size:13px!important}" +
                "body.boniapp .chat-dialog-search-v176a input{min-height:40px!important;font-size:14px!important}";

        String js = "document.body.classList.add('boniapp');" +
'''
replace_once(css_anchor, '\n' + css_override, 'compact-mobile-css')

replace_once(
    "var author=an?(an.textContent||'').trim():'';bridge.notifyNewMessage(author,id)",
    "var author=an?(an.textContent||'').trim():'';var body=x.querySelector('.chat-message-body');var preview=body?(body.textContent||'').replace(/\\s+/g,' ').trim():'';var head=document.querySelector('.chat-reset-header .brand-title');var chatTitle=head?(head.textContent||'').replace(/^(Рабочий чат:|Проектный чат:|Личная переписка:)\\s*/,'').trim():'Чат';bridge.notifyNewMessage(author,chatTitle,preview,id)",
    'rich-local-notification-js',
)

replace_once(
    'new String[]{"Сменить компанию", "Открыть портал", "Настройки уведомлений", "Выйти из аккаунта", "Очистить сессию"}',
    'new String[]{"Сменить компанию", "Открыть портал", "Настройки уведомлений", "Диагностика push", "Выйти из аккаунта", "Очистить сессию"}',
    'push-diagnostics-menu-item',
)
replace_once(
    '''                    } else if (w == 3) {
                        web.loadUrl(base + "/logout");
                    } else {''',
    '''                    } else if (w == 3) {
                        showPushDiagnostics();
                    } else if (w == 4) {
                        web.loadUrl(base + "/logout");
                    } else {''',
    'push-diagnostics-menu-action',
)

diag_anchor = '''    private void openNotificationSettings() {
'''
diag_method = '''    private void showPushDiagnostics() {
        String js = "(function(){fetch('/api/mobile/push/status',{credentials:'same-origin',cache:'no-store'})"
                + ".then(async function(r){var t=await r.text();var j={};try{j=JSON.parse(t)}catch(e){};"
                + "var msg='HTTP: '+r.status+'\\nКомпания: '+(j.company_key||'?')+'\\nУстройств: '+(j.registered_devices===undefined?'?':j.registered_devices)+'\\nFirebase key: '+(j.firebase_key_present?'OK':'NO');"
                + "if(window.BonifaciyAndroid)window.BonifaciyAndroid.showDiagnostic(msg);})"
                + ".catch(function(e){if(window.BonifaciyAndroid)window.BonifaciyAndroid.showDiagnostic('Ошибка: '+e);});})()";
        web.evaluateJavascript(js, null);
    }

'''
replace_once(diag_anchor, diag_method + diag_anchor, 'push-diagnostics-method')

replace_once(
    '''        public void notifyNewMessage(String author, String messageId) {
            if (!appInForeground) runOnUiThread(() -> showMessageNotification(author));
        }''',
    '''        public void notifyNewMessage(String author, String chatTitle, String preview, String messageId) {
            // Always keep the WebView background fallback. NotificationHelper
            // deduplicates it against FCM using company + message id.
            if (!appInForeground) {
                runOnUiThread(() -> showMessageNotification(author, chatTitle, preview, messageId));
            }
        }

        @JavascriptInterface
        public void showDiagnostic(String value) {
            runOnUiThread(() -> new AlertDialog.Builder(MainActivity.this)
                    .setTitle("Диагностика push")
                    .setMessage(value == null ? "Нет данных" : value)
                    .setPositiveButton("OK", null)
                    .show());
        }''',
    'rich-local-notification-bridge-and-diagnostics',
)

path.write_text(text, encoding='utf-8')
print('V3B source patch OK:', ', '.join(checks))
