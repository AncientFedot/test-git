from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"V4C patch anchor {label!r}: expected 1, found {count}")
    return text.replace(old, new, 1)


raw = MAIN.read_text(encoding="utf-8").replace("\r\n", "\n")

required_v4b_markers = [
    'JSONObject author = m.optJSONObject("author")',
    'boolean own = m.optBoolean("is_own", false)',
    'scroll.fullScroll(View.FOCUS_DOWN)',
    'companyButton.setText(V4Core.companyName(company) + "  ▾")',
]
for marker in required_v4b_markers:
    if marker not in raw:
        raise SystemExit(f"V4C requires accepted V4B source marker: {marker}")

s = raw

s = replace_once(
    s,
    "import android.content.Context;\n",
    "import android.content.Context;\nimport android.content.ClipData;\n",
    "ClipData import",
)
s = replace_once(
    s,
    "import android.widget.Button;\n",
    "import android.widget.Button;\nimport android.widget.CheckBox;\n",
    "CheckBox import",
)
s = replace_once(
    s,
    "import android.widget.Toast;\n",
    "import android.widget.Toast;\nimport android.webkit.MimeTypeMap;\n",
    "MimeTypeMap import",
)

helper_anchor = '''    private void showLogin(String note) {
'''
helpers = '''    private String rememberedUsername(String targetCompany) {
        return V4Core.SecureStore.get(this, "remember_username_" + targetCompany);
    }

    private String rememberedPassword(String targetCompany) {
        return V4Core.SecureStore.get(this, "remember_password_" + targetCompany);
    }

    private void saveRememberedCredentials(String targetCompany, String username, String password) {
        V4Core.SecureStore.put(this, "remember_username_" + targetCompany, username);
        V4Core.SecureStore.put(this, "remember_password_" + targetCompany, password);
    }

    private void clearRememberedCredentials(String targetCompany) {
        V4Core.SecureStore.remove(this, "remember_username_" + targetCompany);
        V4Core.SecureStore.remove(this, "remember_password_" + targetCompany);
    }

    private boolean hasRememberedCredentials(String targetCompany) {
        return !rememberedUsername(targetCompany).isBlank()
                && !rememberedPassword(targetCompany).isBlank();
    }

    private void showLogin(String note) {
'''
s = replace_once(s, helper_anchor, helpers, "credential helpers")

old_login = '''        EditText username = new EditText(this);
        username.setHint("Логин");
        username.setSingleLine(true);
        box.addView(username, new LinearLayout.LayoutParams(-1, dp(56)));

        EditText password = new EditText(this);
        password.setHint("Пароль");
        password.setSingleLine(true);
        password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        box.addView(password, new LinearLayout.LayoutParams(-1, dp(56)));

        Button login = button("Войти");
        login.setOnClickListener(v -> doLogin(username.getText().toString(), password.getText().toString()));
        box.addView(login, new LinearLayout.LayoutParams(-1, dp(54)));
        replaceBody(box);
    }

    private void doLogin(String username, String password) {
'''
new_login = '''        String savedUsername = rememberedUsername(company);
        String savedPassword = rememberedPassword(company);

        EditText username = new EditText(this);
        username.setHint("Логин");
        username.setSingleLine(true);
        username.setText(savedUsername);
        box.addView(username, new LinearLayout.LayoutParams(-1, dp(56)));

        EditText password = new EditText(this);
        password.setHint("Пароль");
        password.setSingleLine(true);
        password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        password.setText(savedPassword);
        box.addView(password, new LinearLayout.LayoutParams(-1, dp(56)));

        CheckBox remember = new CheckBox(this);
        remember.setText("Запомнить меня на этом телефоне");
        remember.setChecked(!savedUsername.isBlank() && !savedPassword.isBlank());
        box.addView(remember, new LinearLayout.LayoutParams(-1, dp(48)));

        if (!savedUsername.isBlank() || !savedPassword.isBlank()) {
            Button forget = button("Забыть сохранённые данные");
            forget.setOnClickListener(v -> {
                clearRememberedCredentials(company);
                username.setText("");
                password.setText("");
                remember.setChecked(false);
                Toast.makeText(this, "Сохранённые данные удалены", Toast.LENGTH_SHORT).show();
            });
            box.addView(forget, new LinearLayout.LayoutParams(-1, dp(46)));
        }

        Button login = button("Войти");
        login.setOnClickListener(v -> doLogin(
                username.getText().toString(),
                password.getText().toString(),
                remember.isChecked()));
        box.addView(login, new LinearLayout.LayoutParams(-1, dp(54)));
        replaceBody(box);
    }

    private void doLogin(String username, String password, boolean rememberCredentials) {
'''
s = replace_once(s, old_login, new_login, "remembered login UI")

old_login_success = '''                V4Core.SecureStore.token(this, targetCompany, token);
                getSharedPreferences("boni_v4_plain", MODE_PRIVATE).edit()
                        .putString("selected_company", targetCompany).apply();
'''
new_login_success = '''                V4Core.SecureStore.token(this, targetCompany, token);
                if (rememberCredentials) {
                    saveRememberedCredentials(targetCompany, username.trim(), password);
                } else {
                    clearRememberedCredentials(targetCompany);
                }
                getSharedPreferences("boni_v4_plain", MODE_PRIVATE).edit()
                        .putString("selected_company", targetCompany).apply();
'''
s = replace_once(s, old_login_success, new_login_success, "save credentials after successful login")

old_attachments = '''    private void addAttachmentButtons(LinearLayout card, JSONObject m) {
        JSONArray a = m.optJSONArray("attachments");
        if (a != null) {
            for (int i = 0; i < a.length(); i++) {
                JSONObject item = a.optJSONObject(i);
                if (item == null) continue;
                int attachmentId = item.optInt("id", item.optInt("attachment_id", 0));
                String name = first(item, "original_name", "filename", "name");
                if (attachmentId > 0) attachmentButton(card, name, "/api/mobile/v4/chat/attachment/file/" + attachmentId);
            }
        }
        JSONObject single = m.optJSONObject("attachment");
        if (single != null) {
            int attachmentId = single.optInt("id", single.optInt("attachment_id", 0));
            String name = first(single, "original_name", "filename", "name");
            if (attachmentId > 0) attachmentButton(card, name, "/api/mobile/v4/chat/attachment/file/" + attachmentId);
        }
        String legacyName = first(m, "attachment_original_name", "attachment_name");
        int messageId = m.optInt("id", 0);
        if (!legacyName.isBlank() && messageId > 0) {
            attachmentButton(card, legacyName, "/api/mobile/v4/chat/attachment/message/" + messageId);
        }
    }

    private void attachmentButton(LinearLayout card, String name, String path) {
        String safeName = name == null || name.isBlank() ? "Вложение" : name;
        Button b = button("📎 " + safeName);
        b.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        b.setOnClickListener(v -> downloadAndOpen(path, safeName));
        card.addView(b, new LinearLayout.LayoutParams(-1, dp(48)));
    }
'''
new_attachments = '''    private void addAttachmentButtons(LinearLayout card, JSONObject m) {
        int messageId = m.optInt("id", 0);
        String messageFallback = messageId > 0
                ? "/api/mobile/v4/chat/attachment/message/" + messageId
                : "";
        boolean added = false;

        JSONArray a = m.optJSONArray("attachments");
        if (a != null) {
            for (int i = 0; i < a.length(); i++) {
                JSONObject item = a.optJSONObject(i);
                if (item == null) continue;
                int attachmentId = item.optInt("id", item.optInt("attachment_id", 0));
                String name = first(item, "original_name", "filename", "name");
                if (attachmentId > 0) {
                    attachmentButton(
                            card,
                            name,
                            "/api/mobile/v4/chat/attachment/file/" + attachmentId,
                            messageFallback);
                    added = true;
                }
            }
        }

        JSONObject single = m.optJSONObject("attachment");
        if (single != null) {
            int attachmentId = single.optInt("id", single.optInt("attachment_id", 0));
            String name = first(single, "original_name", "filename", "name");
            if (attachmentId > 0) {
                attachmentButton(
                        card,
                        name,
                        "/api/mobile/v4/chat/attachment/file/" + attachmentId,
                        messageFallback);
                added = true;
            }
        }

        String legacyName = first(m, "attachment_original_name", "attachment_name");
        if (!added && !legacyName.isBlank() && messageId > 0) {
            attachmentButton(card, legacyName, messageFallback, "");
            added = true;
        }

        String messageText = first(m, "message", "text", "content");
        if (!added && messageId > 0 && messageText.startsWith("Файлы:")) {
            String inferredName = messageText.substring("Файлы:".length())
                    .replace('\\n', ' ')
                    .replace('\\r', ' ')
                    .trim();
            if (inferredName.isBlank()) inferredName = "Вложение";
            attachmentButton(card, inferredName, messageFallback, "");
        }
    }

    private void attachmentButton(LinearLayout card, String name, String primaryPath, String fallbackPath) {
        String safeName = name == null || name.isBlank() ? "Вложение" : name;
        Button b = button("📎 Открыть · " + safeName);
        b.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        b.setContentDescription("Открыть вложение " + safeName);
        b.setOnClickListener(v -> downloadAndOpen(primaryPath, fallbackPath, safeName));
        card.addView(b, new LinearLayout.LayoutParams(-1, dp(50)));
    }
'''
s = replace_once(s, old_attachments, new_attachments, "attachment metadata + legacy fallback")

old_download = '''    private void downloadAndOpen(String path, String name) {
        loading(true);
        final String c = company;
        final String token = V4Core.SecureStore.token(this, c);
        io.execute(() -> {
            try {
                V4Core.DownloadResult r = V4Core.Api.download(this, c, token, path, name);
                runOnUiThread(() -> {
                    loading(false);
                    try {
                        Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".files", r.file);
                        Intent view = new Intent(Intent.ACTION_VIEW);
                        view.setDataAndType(uri, r.mimeType);
                        view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        startActivity(view);
                    } catch (ActivityNotFoundException e) {
                        Toast.makeText(this, "Файл сохранён приватно, но нет приложения для открытия", Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    loading(false);
                    authAwareError(e);
                });
            }
        });
    }
'''
new_download = '''    private boolean attachmentFallbackAllowed(Exception e) {
        if (!(e instanceof V4Core.ApiException)) return false;
        int status = ((V4Core.ApiException) e).status;
        return status == 400 || status == 404 || status == 405 || status == 410 || status == 422;
    }

    private String bestMimeType(String serverMime, String name) {
        String mime = serverMime == null ? "" : serverMime.trim();
        if (!mime.isBlank() && !"application/octet-stream".equalsIgnoreCase(mime)) return mime;
        String safe = name == null ? "" : name.trim();
        int dot = safe.lastIndexOf('.');
        if (dot >= 0 && dot + 1 < safe.length()) {
            String ext = safe.substring(dot + 1).toLowerCase();
            String guessed = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
            if (guessed != null && !guessed.isBlank()) return guessed;
        }
        return "application/octet-stream";
    }

    private void openDownloadedFile(V4Core.DownloadResult r, String name) {
        Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".files", r.file);
        String mime = bestMimeType(r.mimeType, name);

        Intent view = new Intent(Intent.ACTION_VIEW);
        view.setDataAndType(uri, mime);
        view.setClipData(ClipData.newRawUri("Bonifaciy attachment", uri));
        view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

        try {
            startActivity(Intent.createChooser(view, "Открыть вложение"));
        } catch (ActivityNotFoundException first) {
            Intent generic = new Intent(Intent.ACTION_VIEW);
            generic.setDataAndType(uri, "*/*");
            generic.setClipData(ClipData.newRawUri("Bonifaciy attachment", uri));
            generic.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            try {
                startActivity(Intent.createChooser(generic, "Открыть вложение"));
            } catch (ActivityNotFoundException second) {
                Toast.makeText(
                        this,
                        "Файл скачан в приватное хранилище, но на телефоне нет приложения для его открытия",
                        Toast.LENGTH_LONG).show();
            }
        }
    }

    private void downloadAndOpen(String primaryPath, String fallbackPath, String name) {
        loading(true);
        final String c = company;
        final String token = V4Core.SecureStore.token(this, c);
        Toast.makeText(this, "Загрузка вложения…", Toast.LENGTH_SHORT).show();

        io.execute(() -> {
            String usedPath = primaryPath;
            Exception firstError = null;
            try {
                V4Core.DownloadResult r;
                try {
                    r = V4Core.Api.download(this, c, token, primaryPath, name);
                } catch (Exception e) {
                    firstError = e;
                    if (fallbackPath == null
                            || fallbackPath.isBlank()
                            || fallbackPath.equals(primaryPath)
                            || !attachmentFallbackAllowed(e)) {
                        throw e;
                    }
                    usedPath = fallbackPath;
                    r = V4Core.Api.download(this, c, token, fallbackPath, name);
                }

                String finalUsedPath = usedPath;
                runOnUiThread(() -> {
                    loading(false);
                    openDownloadedFile(r, name);
                    if (!finalUsedPath.equals(primaryPath)) {
                        Toast.makeText(this, "Вложение открыто через совместимый режим", Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception e) {
                Exception first = firstError;
                String failedPath = usedPath;
                runOnUiThread(() -> {
                    loading(false);
                    if (e instanceof V4Core.ApiException
                            && ((((V4Core.ApiException) e).status == 401)
                            || (((V4Core.ApiException) e).status == 403))) {
                        authAwareError(e);
                        return;
                    }

                    StringBuilder detail = new StringBuilder("Не удалось открыть вложение");
                    if (first instanceof V4Core.ApiException) {
                        detail.append("\\nПервый путь: HTTP ")
                                .append(((V4Core.ApiException) first).status);
                    }
                    if (e instanceof V4Core.ApiException) {
                        detail.append("\\nПоследний путь: HTTP ")
                                .append(((V4Core.ApiException) e).status);
                    }
                    detail.append("\\n").append(failedPath);
                    String server = messageOf(e);
                    if (!server.isBlank()) detail.append("\\n").append(server);
                    Toast.makeText(this, detail.toString(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }
'''
s = replace_once(s, old_download, new_download, "attachment download fallback + MIME")

old_logout = '''        V4Core.SecureStore.token(this, V4Core.RK, "");
        V4Core.SecureStore.token(this, V4Core.BOREY, "");
        V4Core.clearPrivateFiles(this);
'''
new_logout = '''        V4Core.SecureStore.token(this, V4Core.RK, "");
        V4Core.SecureStore.token(this, V4Core.BOREY, "");
        clearRememberedCredentials(V4Core.RK);
        clearRememberedCredentials(V4Core.BOREY);
        V4Core.clearPrivateFiles(this);
'''
s = replace_once(s, old_logout, new_logout, "explicit logout clears remembered credentials")

security_checks = {
    "remembered password encrypted": 'V4Core.SecureStore.put(this, "remember_password_"' in s,
    "remembered password read encrypted": 'V4Core.SecureStore.get(this, "remember_password_"' in s,
    "explicit logout clears remembered password": 'clearRememberedCredentials(V4Core.RK)' in s
        and 'clearRememberedCredentials(V4Core.BOREY)' in s,
    "attachment file endpoint retained": '/api/mobile/v4/chat/attachment/file/' in s,
    "attachment message fallback retained": '/api/mobile/v4/chat/attachment/message/' in s,
    "MIME inference enabled": 'MimeTypeMap.getSingleton().getMimeTypeFromExtension' in s,
}
for label, ok in security_checks.items():
    if not ok:
        raise SystemExit(f"V4C generated security check failed: {label}")

MAIN.write_text(s, encoding="utf-8", newline="\n")
print("V4C_ATTACHMENT_CREDENTIAL_PATCH=OK")
