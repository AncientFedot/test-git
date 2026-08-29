from pathlib import Path
import re

main = Path('app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java')
s = main.read_text(encoding='utf-8')

# 1) Refresh must never reload a stray portal page. It only refreshes the current chat URL.
old = '        reload.setOnClickListener(v -> web.reload());\n'
new = '        reload.setOnClickListener(v -> safeReloadChat());\n'
if s.count(old) != 1:
    raise SystemExit(f'reload anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# 2) Add strict same-company chat/auth navigation helpers before buildUi().
anchor = '    private void buildUi() {\n'
if s.count(anchor) != 1:
    raise SystemExit(f'buildUi anchor mismatch: {s.count(anchor)}')
helpers = r'''    private boolean isCurrentCompanyPortalUri(Uri uri) {
        if (!isTrustedPortalUri(uri) || base == null || base.isBlank()) return false;
        try {
            Uri b = Uri.parse(base);
            return b.getHost() != null && uri.getHost() != null
                    && b.getHost().equalsIgnoreCase(uri.getHost());
        } catch (Exception ignored) {
            return false;
        }
    }

    private boolean isChatPath(Uri uri) {
        if (uri == null) return false;
        String path = uri.getPath();
        return path != null && ("/chat".equals(path) || path.startsWith("/chat/"));
    }

    private boolean isAuthPath(Uri uri) {
        if (uri == null) return false;
        String path = uri.getPath();
        if (path == null) return false;
        return path.equals("/login") || path.startsWith("/login/")
                || path.equals("/logout") || path.startsWith("/logout/")
                || path.equals("/auth") || path.startsWith("/auth/")
                || path.equals("/oauth") || path.startsWith("/oauth/");
    }

    private boolean isAllowedInAppUri(Uri uri) {
        return isCurrentCompanyPortalUri(uri) && (isChatPath(uri) || isAuthPath(uri));
    }

    private void safeReloadChat() {
        String current = web == null ? null : web.getUrl();
        try {
            Uri uri = current == null ? null : Uri.parse(current);
            if (isCurrentCompanyPortalUri(uri) && isChatPath(uri)) {
                loadChatSilently(uri.toString());
                return;
            }
        } catch (Exception ignored) {
        }
        if (base != null && !base.isBlank()) loadChatSilently(base + "/chat");
    }

    private void recoverToChat() {
        if (base == null || base.isBlank()) return;
        loadChatSilently(base + "/chat");
    }

'''
s = s.replace(anchor, helpers + anchor, 1)

# 3) New-window navigation: chat/auth can remain inside; all other portal pages open externally.
old = '''                        Uri uri = Uri.parse(url);
                        if (isTrustedPortalUri(uri)) view.loadUrl(url); else openExternal(uri);'''
new = '''                        Uri uri = Uri.parse(url);
                        if (isAllowedInAppUri(uri)) {
                            loadChatSilently(url);
                        } else {
                            openExternal(uri);
                        }'''
if s.count(old) != 1:
    raise SystemExit(f'onCreateWindow navigation anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# 4) Main-frame navigation: same-company WebView is chat/auth only.
old = '''                if (isTrustedPortalUri(u)) return false;
                if ("http".equalsIgnoreCase(u.getScheme()) || "https".equalsIgnoreCase(u.getScheme())) {
                    openExternal(u);
                    return true;
                }
                return false;'''
new = '''                if (isAllowedInAppUri(u)) return false;
                if (isCurrentCompanyPortalUri(u)) {
                    recoverToChat();
                    Toast.makeText(MainActivity.this, "В приложении доступен только чат", Toast.LENGTH_SHORT).show();
                    return true;
                }
                if ("http".equalsIgnoreCase(u.getScheme()) || "https".equalsIgnoreCase(u.getScheme())) {
                    openExternal(u);
                    return true;
                }
                return true;'''
if s.count(old) != 1:
    raise SystemExit(f'shouldOverrideUrlLoading anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# 5) Harden V3G page lifecycle. Never reveal an unexpected main portal page in the WebView.
old = '''            @Override
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
new = '''            @Override
            public void onPageStarted(WebView v, String url, android.graphics.Bitmap favicon) {
                try {
                    Uri u = Uri.parse(url == null ? "" : url);
                    if (isCurrentCompanyPortalUri(u) && !isChatPath(u) && !isAuthPath(u)) {
                        v.setVisibility(View.INVISIBLE);
                        progress.setVisibility(View.VISIBLE);
                        v.stopLoading();
                        v.post(MainActivity.this::recoverToChat);
                        return;
                    }
                    if (isCurrentCompanyPortalUri(u) && isChatPath(u)) {
                        v.setVisibility(View.INVISIBLE);
                        progress.setVisibility(View.VISIBLE);
                    }
                } catch (Exception ignored) {
                }
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                try {
                    Uri u = Uri.parse(url == null ? "" : url);
                    if (isCurrentCompanyPortalUri(u) && isChatPath(u)) {
                        injectMobile();
                        PushRegistrar.scheduleRegistration(MainActivity.this, 250L, 2000L, 7000L);
                        v.postDelayed(() -> {
                            try { v.setVisibility(View.VISIBLE); } catch (Exception ignored) {}
                        }, 70L);
                        return;
                    }
                    if (isCurrentCompanyPortalUri(u) && isAuthPath(u)) {
                        v.setVisibility(View.VISIBLE);
                        return;
                    }
                    if (isCurrentCompanyPortalUri(u)) {
                        v.setVisibility(View.INVISIBLE);
                        v.post(MainActivity.this::recoverToChat);
                    }
                } catch (Exception ignored) {
                }
            }'''
if s.count(old) != 1:
    raise SystemExit(f'V3G lifecycle anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

# 6) If Android Back is pressed from any unexpected portal state, recover directly to chat.
old = '''            if ("true".equals(v)) {
                web.evaluateJavascript("document.body.classList.remove('dialogs')", null);
            } else if (web.canGoBack()) {
                web.goBack();
            } else {
                super.onBackPressed();
            }'''
new = '''            if ("true".equals(v)) {
                web.evaluateJavascript("document.body.classList.remove('dialogs')", null);
            } else {
                try {
                    Uri current = Uri.parse(web.getUrl() == null ? "" : web.getUrl());
                    if (isCurrentCompanyPortalUri(current) && !isChatPath(current) && !isAuthPath(current)) {
                        recoverToChat();
                        return;
                    }
                } catch (Exception ignored) {
                }
                if (web.canGoBack()) web.goBack(); else super.onBackPressed();
            }'''
if s.count(old) != 1:
    raise SystemExit(f'onBackPressed anchor mismatch: {s.count(old)}')
s = s.replace(old, new, 1)

main.write_text(s, encoding='utf-8')

# V3H app identity / in-place update.
gradle = Path('app/build.gradle')
g = gradle.read_text(encoding='utf-8')
g = re.sub(r'versionCode\s+\d+', 'versionCode 11', g, count=1)
g = re.sub(r"versionName\s+'[^']+'", "versionName '3.7-test'", g, count=1)
gradle.write_text(g, encoding='utf-8')

push = Path('app/src/main/java/ru/leorix/bonifaciychat/PushRegistrar.java')
p = push.read_text(encoding='utf-8')
p = p.replace('BonifaciyChatAndroid/3.6', 'BonifaciyChatAndroid/3.7')
p = p.replace('V3G native diagnostics', 'V3H native diagnostics')
p = p.replace('return "3.6-test";', 'return "3.7-test";')
push.write_text(p, encoding='utf-8')

print('V3H patch OK: safe refresh + chat-only WebView navigation + portal recovery + version 3.7')
