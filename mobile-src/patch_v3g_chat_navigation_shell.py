from pathlib import Path
import re

main = Path('app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java')
s = main.read_text(encoding='utf-8')

# 1) Push click navigation: chat_id is authoritative.
pattern = re.compile(
    r'    private void openPendingPushChatIfAny\(\) \{.*?\n    \}\n\n    private int dp\(int v\) \{',
    re.S,
)
replacement = r'''    private String pendingPushChatTarget() {
        try {
            android.content.SharedPreferences p = getSharedPreferences("boni", MODE_PRIVATE);
            String chatId = p.getString("pending_push_chat_id", "");
            String chatUrl = p.getString("pending_push_chat_url", "");
            if (base == null || base.isBlank()) return "";

            if (chatId != null && !chatId.isBlank()) {
                String[] parts = chatId.trim().split(":", 2);
                if (parts.length == 2) {
                    String kind = parts[0].trim();
                    String rawId = parts[1].trim();
                    if (rawId.matches("\\d+")) {
                        if ("direct".equals(kind)) return base + "/chat?dialog=" + rawId;
                        if ("project".equals(kind)) return base + "/chat?project=" + rawId;
                        if ("room".equals(kind)) return base + "/chat?room=" + rawId;
                        if ("general".equals(kind)) return base + "/chat";
                    }
                }
            }

            if (chatUrl == null || chatUrl.isBlank()) return "";
            Uri uri;
            if (chatUrl.startsWith("/chat")) {
                uri = Uri.parse(base + chatUrl);
            } else {
                uri = Uri.parse(chatUrl);
                if (!isTrustedPortalUri(uri)) return "";
                Uri baseUri = Uri.parse(base);
                if (baseUri.getHost() == null || uri.getHost() == null
                        || !baseUri.getHost().equalsIgnoreCase(uri.getHost())) return "";
            }
            String path = uri.getPath();
            if (path == null || !path.startsWith("/chat")) return "";
            return uri.toString();
        } catch (Exception ignored) {
            return "";
        }
    }

    private void clearPendingPushChatTarget() {
        getSharedPreferences("boni", MODE_PRIVATE).edit()
                .remove("pending_push_chat_url")
                .remove("pending_push_chat_id")
                .apply();
    }

    private void loadChatSilently(String url) {
        if (url == null || url.isBlank()) return;
        try {
            web.setVisibility(View.INVISIBLE);
            progress.setVisibility(View.VISIBLE);
        } catch (Exception ignored) {
        }
        web.loadUrl(url);
    }

    private boolean openPendingPushChatIfAny() {
        String target = pendingPushChatTarget();
        if (target.isBlank()) return false;
        clearPendingPushChatTarget();
        loadChatSilently(target);
        return true;
    }

    private int dp(int v) {'''
s, count = pattern.subn(replacement, s, count=1)
if count != 1:
    raise SystemExit(f'pending push navigation method replacement failed: {count}')

# Do not load general chat first and then overwrite it with the push target.
old = '''        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);
        web.postDelayed(this::openPendingPushChatIfAny, 700L);'''
new = '''        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);'''
if s.count(old) != 1:
    raise SystemExit(f'onCreate pending navigation anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# Company selection/load must prefer a pending push target.
old = '''        getSharedPreferences("boni", MODE_PRIVATE).edit().putString("company", b ? "borey" : "rk").apply();
        if (load) web.loadUrl(base + "/chat");'''
new = '''        getSharedPreferences("boni", MODE_PRIVATE).edit().putString("company", b ? "borey" : "rk").apply();
        if (load) {
            if (!openPendingPushChatIfAny()) loadChatSilently(base + "/chat");
        }'''
if s.count(old) != 1:
    raise SystemExit(f'setCompany load anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# Hide the raw portal while a chat page is navigating. Reveal only after mobile CSS is injected.
old = '''            @Override
            public void onPageFinished(WebView v, String url) {
                injectMobile();
                PushRegistrar.scheduleRegistration(MainActivity.this, 250L, 2000L, 7000L);
            }'''
new = '''            @Override
            public void onPageStarted(WebView v, String url, android.graphics.Bitmap favicon) {
                try {
                    Uri u = Uri.parse(url == null ? "" : url);
                    String path = u.getPath();
                    if (isTrustedPortalUri(u) && path != null && path.startsWith("/chat")) {
                        v.setVisibility(View.INVISIBLE);
                        progress.setVisibility(View.VISIBLE);
                    }
                } catch (Exception ignored) {
                }
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                injectMobile();
                PushRegistrar.scheduleRegistration(MainActivity.this, 250L, 2000L, 7000L);
                v.postDelayed(() -> {
                    try { v.setVisibility(View.VISIBLE); } catch (Exception ignored) {}
                }, 70L);
            }'''
if s.count(old) != 1:
    raise SystemExit(f'WebViewClient page lifecycle anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# Remove the large vertical gap and make the mobile chat the only visible shell.
old = '                "body.boniapp .chat-reset-main{height:100dvh!important;padding:0 4px 4px!important;gap:5px!important}" +\n'
new = (
    '                "body.boniapp{margin:0!important;padding:0!important;overflow:hidden!important}" +\n'
    '                "body.boniapp #chat-layout-root{position:fixed!important;inset:0!important;z-index:2147482000!important;width:100%!important;height:100dvh!important;min-height:0!important;margin:0!important;padding:0!important;border:0!important;background:var(--bg,#0b1220)!important;overflow:hidden!important}" +\n'
    '                "body.boniapp .chat-reset-main{height:100%!important;min-height:0!important;margin:0!important;padding:0 4px 4px!important;gap:3px!important}" +\n'
)
if s.count(old) != 1:
    raise SystemExit(f'compact mobile main CSS anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# Slightly tighten the in-chat header as part of removing the dead area.
s = s.replace(
    '"body.boniapp .chat-reset-header{min-height:34px!important;padding:3px!important}',
    '"body.boniapp .chat-reset-header{min-height:30px!important;margin:0!important;padding:2px 3px!important}',
    1,
)

main.write_text(s, encoding='utf-8')

# V3G app identity. Explicitly bump versionCode above V3F so Android updates in place.
gradle = Path('app/build.gradle')
g = gradle.read_text(encoding='utf-8')
g = re.sub(r'versionCode\s+\d+', 'versionCode 10', g, count=1)
g = re.sub(r"versionName\s+'[^']+'", "versionName '3.6-test'", g, count=1)
gradle.write_text(g, encoding='utf-8')

# Diagnostics / native network UA version only; server protocol stays android-v3.
push = Path('app/src/main/java/ru/leorix/bonifaciychat/PushRegistrar.java')
p = push.read_text(encoding='utf-8')
p = p.replace('BonifaciyChatAndroid/3.5', 'BonifaciyChatAndroid/3.6')
p = p.replace('V3F native diagnostics', 'V3G native diagnostics')
p = p.replace('return "3.5-test";', 'return "3.6-test";')
push.write_text(p, encoding='utf-8')

print('V3G patch OK: exact push chat navigation + portal flash suppression + compact chat shell + version 3.6')
