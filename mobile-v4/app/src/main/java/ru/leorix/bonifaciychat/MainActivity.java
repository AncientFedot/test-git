package ru.leorix.bonifaciychat;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int REQ_NOTIFICATIONS = 4101;
    private static final int REQ_FILE = 4102;

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private FrameLayout body;
    private ProgressBar progress;
    private Button companyButton;
    private String company = V4Core.RK;
    private String currentScopeType = "";
    private int currentScopeId = 0;
    private String currentTitle = "";
    private Uri selectedAttachment;
    private TextView selectedAttachmentLabel;
    private EditText composer;

    private String pendingPushCompany = "";
    private String pendingPushChatId = "";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        company = getSharedPreferences("boni_v4_plain", MODE_PRIVATE)
                .getString("selected_company", V4Core.RK);
        if (!V4Core.RK.equals(company) && !V4Core.BOREY.equals(company)) company = V4Core.RK;
        buildShell();
        requestNotificationPermission();
        if (!consumePushIntent(getIntent())) {
            if (V4Core.SecureStore.token(this, company).isBlank()) showLogin("");
            else showDialogs();
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        consumePushIntent(intent);
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        super.onDestroy();
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private TextView text(String value, float size) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(size);
        t.setTextColor(Color.rgb(31, 41, 55));
        t.setPadding(dp(8), dp(6), dp(8), dp(6));
        return t;
    }

    private Button button(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setMinHeight(0);
        b.setMinWidth(0);
        return b;
    }

    private void buildShell() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(248, 250, 252));
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });

        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(4), 0, dp(4), 0);
        bar.setBackgroundColor(Color.rgb(92, 35, 35));
        root.addView(bar, new LinearLayout.LayoutParams(-1, dp(52)));

        Button dialogs = button("☰");
        dialogs.setTextColor(Color.WHITE);
        dialogs.setBackgroundColor(Color.TRANSPARENT);
        dialogs.setOnClickListener(v -> showDialogs());
        bar.addView(dialogs, new LinearLayout.LayoutParams(dp(48), dp(48)));

        companyButton = button("");
        companyButton.setTextColor(Color.WHITE);
        companyButton.setTextSize(14);
        companyButton.setGravity(Gravity.CENTER_VERTICAL);
        companyButton.setBackgroundColor(Color.TRANSPARENT);
        companyButton.setOnClickListener(v -> chooseCompany());
        bar.addView(companyButton, new LinearLayout.LayoutParams(0, dp(48), 1f));

        Button reload = button("↻");
        reload.setTextColor(Color.WHITE);
        reload.setBackgroundColor(Color.TRANSPARENT);
        reload.setOnClickListener(v -> refreshCurrent());
        bar.addView(reload, new LinearLayout.LayoutParams(dp(48), dp(48)));

        Button logout = button("⎋");
        logout.setTextColor(Color.WHITE);
        logout.setBackgroundColor(Color.TRANSPARENT);
        logout.setOnClickListener(v -> confirmLogout());
        bar.addView(logout, new LinearLayout.LayoutParams(dp(48), dp(48)));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setVisibility(View.GONE);
        root.addView(progress, new LinearLayout.LayoutParams(-1, dp(3)));

        body = new FrameLayout(this);
        root.addView(body, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);
        updateCompanyLabel();
    }

    private void updateCompanyLabel() {
        companyButton.setText("TEST V4 · " + V4Core.companyName(company));
    }

    private void loading(boolean value) {
        runOnUiThread(() -> progress.setVisibility(value ? View.VISIBLE : View.GONE));
    }

    private void replaceBody(View view) {
        body.removeAllViews();
        body.addView(view, new FrameLayout.LayoutParams(-1, -1));
    }

    private void showLogin(String note) {
        currentScopeType = "";
        selectedAttachment = null;
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(28), dp(20), dp(20));

        TextView title = text("Вход · " + V4Core.companyName(company), 21);
        title.setTextColor(Color.rgb(15, 23, 42));
        box.addView(title);
        TextView marker = text("INTERNAL TEST · нативный клиент без WebView", 12);
        marker.setTextColor(Color.rgb(127, 29, 29));
        box.addView(marker);
        if (note != null && !note.isBlank()) {
            TextView n = text(note, 14);
            n.setTextColor(Color.rgb(153, 27, 27));
            box.addView(n);
        }

        EditText username = new EditText(this);
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
        if (username.trim().isBlank() || password.isBlank()) {
            Toast.makeText(this, "Введите логин и пароль", Toast.LENGTH_SHORT).show();
            return;
        }
        loading(true);
        final String targetCompany = company;
        io.execute(() -> {
            try {
                JSONObject r = V4Core.Api.login(targetCompany, username.trim(), password, V4Core.deviceId(this));
                String token = r.optString("access_token", "");
                if (token.length() < 40) throw new Exception("Сервер не вернул access token");
                V4Core.SecureStore.token(this, targetCompany, token);
                getSharedPreferences("boni_v4_plain", MODE_PRIVATE).edit()
                        .putString("selected_company", targetCompany).apply();
                PushWorker.enqueueRegister(this, targetCompany);
                runOnUiThread(() -> {
                    loading(false);
                    if (!pendingPushChatId.isBlank() && targetCompany.equals(pendingPushCompany)) {
                        String chat = pendingPushChatId;
                        pendingPushChatId = "";
                        pendingPushCompany = "";
                        openChatId(chat);
                    } else {
                        showDialogs();
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    loading(false);
                    showLogin(messageOf(e));
                });
            }
        });
    }

    private void chooseCompany() {
        String[] labels = {"РК-ТЕХНИКА", "НПО БОРЕЙ"};
        new AlertDialog.Builder(this)
                .setTitle("Компания")
                .setItems(labels, (d, which) -> switchCompany(which == 1 ? V4Core.BOREY : V4Core.RK))
                .show();
    }

    private void switchCompany(String next) {
        company = next;
        getSharedPreferences("boni_v4_plain", MODE_PRIVATE).edit().putString("selected_company", company).apply();
        updateCompanyLabel();
        currentScopeType = "";
        selectedAttachment = null;
        if (V4Core.SecureStore.token(this, company).isBlank()) showLogin("");
        else showDialogs();
    }

    private void showDialogs() {
        if (V4Core.SecureStore.token(this, company).isBlank()) {
            showLogin("Сначала войдите в эту компанию");
            return;
        }
        currentScopeType = "";
        selectedAttachment = null;
        LinearLayout wrap = new LinearLayout(this);
        wrap.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("Диалоги", 20);
        title.setTextColor(Color.rgb(15, 23, 42));
        wrap.addView(title, new LinearLayout.LayoutParams(-1, dp(48)));
        TextView state = text("Загрузка…", 14);
        wrap.addView(state);
        replaceBody(wrap);
        loading(true);
        final String targetCompany = company;
        final String token = V4Core.SecureStore.token(this, targetCompany);
        io.execute(() -> {
            try {
                JSONObject r = V4Core.Api.json(targetCompany, "GET", "/api/mobile/v4/chat/dialogs", token, null);
                JSONArray items = r.optJSONArray("items");
                if (items == null) items = new JSONArray();
                JSONArray finalItems = items;
                runOnUiThread(() -> renderDialogs(finalItems));
            } catch (Exception e) {
                runOnUiThread(() -> authAwareError(e));
            } finally {
                loading(false);
            }
        });
    }

    private void renderDialogs(JSONArray items) {
        LinearLayout wrap = new LinearLayout(this);
        wrap.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("Диалоги · " + items.length(), 20);
        title.setTextColor(Color.rgb(15, 23, 42));
        wrap.addView(title, new LinearLayout.LayoutParams(-1, dp(48)));

        List<String> labels = new ArrayList<>();
        List<JSONObject> data = new ArrayList<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject o = items.optJSONObject(i);
            if (o == null) continue;
            data.add(o);
            int unread = o.optInt("unread_count", 0);
            String label = o.optString("title", "Чат");
            if (unread > 0) label = "● " + label + "   " + unread;
            if (o.optBoolean("archived", false)) label += "  [архив]";
            labels.add(label);
        }
        ListView list = new ListView(this);
        list.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, labels));
        list.setOnItemClickListener((parent, view, position, id) -> {
            JSONObject o = data.get(position);
            showChat(o.optString("scope_type", "general"), o.optInt("scope_id", 0), o.optString("title", "Чат"));
        });
        wrap.addView(list, new LinearLayout.LayoutParams(-1, 0, 1f));
        replaceBody(wrap);
    }

    private void showChat(String scopeType, int scopeId, String title) {
        currentScopeType = scopeType;
        currentScopeId = scopeId;
        currentTitle = title == null || title.isBlank() ? "Чат" : title;
        selectedAttachment = null;

        LinearLayout wrap = new LinearLayout(this);
        wrap.setOrientation(LinearLayout.VERTICAL);
        TextView titleView = text(currentTitle, 18);
        titleView.setTextColor(Color.rgb(15, 23, 42));
        titleView.setSingleLine(true);
        wrap.addView(titleView, new LinearLayout.LayoutParams(-1, dp(44)));

        ScrollView scroll = new ScrollView(this);
        LinearLayout messages = new LinearLayout(this);
        messages.setOrientation(LinearLayout.VERTICAL);
        messages.setPadding(dp(6), dp(4), dp(6), dp(8));
        scroll.addView(messages, new ScrollView.LayoutParams(-1, -2));
        wrap.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1f));

        selectedAttachmentLabel = text("", 12);
        selectedAttachmentLabel.setVisibility(View.GONE);
        wrap.addView(selectedAttachmentLabel, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout composerRow = new LinearLayout(this);
        composerRow.setGravity(Gravity.BOTTOM);
        Button attach = button("＋");
        attach.setOnClickListener(v -> pickFile());
        composerRow.addView(attach, new LinearLayout.LayoutParams(dp(52), dp(52)));

        composer = new EditText(this);
        composer.setHint("Сообщение");
        composer.setMaxLines(4);
        composer.setMinLines(1);
        composerRow.addView(composer, new LinearLayout.LayoutParams(0, -2, 1f));

        Button send = button("➤");
        send.setOnClickListener(v -> sendCurrent());
        composerRow.addView(send, new LinearLayout.LayoutParams(dp(58), dp(52)));
        wrap.addView(composerRow, new LinearLayout.LayoutParams(-1, -2));
        replaceBody(wrap);
        loadMessages(messages, scroll);
    }

    private void loadMessages(LinearLayout container, ScrollView scroll) {
        loading(true);
        final String c = company;
        final String token = V4Core.SecureStore.token(this, c);
        final String scope = currentScopeType;
        final int id = currentScopeId;
        String path = "/api/mobile/v4/chat/messages?scope_type="
                + URLEncoder.encode(scope, StandardCharsets.UTF_8)
                + "&scope_id=" + id + "&limit=100";
        io.execute(() -> {
            try {
                JSONObject r = V4Core.Api.json(c, "GET", path, token, null);
                JSONArray messages = r.optJSONArray("messages");
                if (messages == null) messages = new JSONArray();
                JSONArray finalMessages = messages;
                runOnUiThread(() -> {
                    renderMessages(container, finalMessages);
                    scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));
                });
                JSONObject read = new JSONObject();
                read.put("scope_type", scope);
                read.put("scope_id", id);
                V4Core.Api.json(c, "POST", "/api/mobile/v4/chat/read", token, read);
            } catch (Exception e) {
                runOnUiThread(() -> authAwareError(e));
            } finally {
                loading(false);
            }
        });
    }

    private void renderMessages(LinearLayout container, JSONArray messages) {
        container.removeAllViews();
        for (int i = 0; i < messages.length(); i++) {
            JSONObject m = messages.optJSONObject(i);
            if (m == null) continue;
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(dp(10), dp(7), dp(10), dp(7));
            card.setBackgroundColor(i % 2 == 0 ? Color.rgb(241, 245, 249) : Color.rgb(248, 250, 252));

            String author = authorOf(m);
            String created = first(m, "created_at", "created", "timestamp");
            TextView meta = text((author.isBlank() ? "Сообщение" : author) + (created.isBlank() ? "" : "  ·  " + created), 12);
            meta.setTextColor(Color.rgb(71, 85, 105));
            card.addView(meta);

            String message = first(m, "message", "text", "content");
            if (!message.isBlank()) {
                TextView value = text(message, 15);
                value.setTextIsSelectable(true);
                card.addView(value);
            }
            addAttachmentButtons(card, m);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.setMargins(0, 0, 0, dp(5));
            container.addView(card, lp);
        }
        if (messages.length() == 0) container.addView(text("Сообщений пока нет", 14));
    }

    private String authorOf(JSONObject m) {
        JSONObject u = m.optJSONObject("user");
        if (u != null) {
            String v = first(u, "full_name", "name", "username");
            if (!v.isBlank()) return v;
        }
        return first(m, "user_full_name", "author", "author_name", "username", "user_name");
    }

    private String first(JSONObject o, String... keys) {
        for (String key : keys) {
            String v = o.optString(key, "").trim();
            if (!v.isBlank() && !"null".equalsIgnoreCase(v)) return v;
        }
        return "";
    }

    private void addAttachmentButtons(LinearLayout card, JSONObject m) {
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

    private void pickFile() {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        try {
            startActivityForResult(i, REQ_FILE);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Нет приложения для выбора файла", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_FILE || resultCode != RESULT_OK || data == null || data.getData() == null) return;
        selectedAttachment = data.getData();
        try {
            getContentResolver().takePersistableUriPermission(selectedAttachment,
                    data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION));
        } catch (Exception ignored) {}
        if (selectedAttachmentLabel != null) {
            selectedAttachmentLabel.setText("📎 Файл выбран. Нажмите ➤ для отправки");
            selectedAttachmentLabel.setVisibility(View.VISIBLE);
        }
    }

    private void sendCurrent() {
        if (currentScopeType.isBlank()) return;
        String value = composer == null ? "" : composer.getText().toString().trim();
        Uri file = selectedAttachment;
        if (value.isBlank() && file == null) return;
        loading(true);
        final String c = company;
        final String token = V4Core.SecureStore.token(this, c);
        final String scope = currentScopeType;
        final int id = currentScopeId;
        final String title = currentTitle;
        io.execute(() -> {
            try {
                V4Core.Api.sendMessage(this, c, token, scope, id, value, file);
                runOnUiThread(() -> {
                    loading(false);
                    selectedAttachment = null;
                    showChat(scope, id, title);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    loading(false);
                    authAwareError(e);
                });
            }
        });
    }

    private void downloadAndOpen(String path, String name) {
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

    private void refreshCurrent() {
        if (currentScopeType.isBlank()) showDialogs();
        else showChat(currentScopeType, currentScopeId, currentTitle);
    }

    private boolean consumePushIntent(Intent intent) {
        if (intent == null) return false;
        String pushCompany = intent.getStringExtra("push_company");
        String chatId = intent.getStringExtra("push_chat_id");
        if ((!V4Core.RK.equals(pushCompany) && !V4Core.BOREY.equals(pushCompany)) || chatId == null || chatId.isBlank()) return false;
        pendingPushCompany = pushCompany;
        pendingPushChatId = chatId;
        company = pushCompany;
        getSharedPreferences("boni_v4_plain", MODE_PRIVATE).edit().putString("selected_company", company).apply();
        updateCompanyLabel();
        if (V4Core.SecureStore.token(this, company).isBlank()) showLogin("Войдите, чтобы открыть сообщение");
        else {
            pendingPushCompany = "";
            pendingPushChatId = "";
            openChatId(chatId);
        }
        intent.removeExtra("push_company");
        intent.removeExtra("push_chat_id");
        return true;
    }

    private void openChatId(String chatId) {
        String[] parts = chatId.split(":", 2);
        if (parts.length != 2) { showDialogs(); return; }
        String scope = parts[0].trim();
        int id;
        try { id = Integer.parseInt(parts[1].trim()); } catch (Exception e) { showDialogs(); return; }
        if ("general".equals(scope)) { showChat("general", 0, "Общий чат"); return; }
        if (!("direct".equals(scope) || "project".equals(scope) || "room".equals(scope)) || id <= 0) {
            showDialogs(); return;
        }
        String title = "direct".equals(scope) ? "Личный чат" : "project".equals(scope) ? "Проектный чат" : "Рабочий чат";
        showChat(scope, id, title);
    }

    private void confirmLogout() {
        new AlertDialog.Builder(this)
                .setTitle("Завершить сеанс?")
                .setMessage("Будут отозваны push-привязки РК-ТЕХНИКА и НПО БОРЕЙ, очищены токены и приватные вложения.")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Выйти", (d, w) -> logoutAll())
                .show();
    }

    private void logoutAll() {
        final String rkToken = V4Core.SecureStore.token(this, V4Core.RK);
        final String boreyToken = V4Core.SecureStore.token(this, V4Core.BOREY);

        // Audit requirement: durable push revocation is queued before local sessions disappear.
        PushWorker.enqueueUnregisterBoth(this);
        V4Core.SecureStore.token(this, V4Core.RK, "");
        V4Core.SecureStore.token(this, V4Core.BOREY, "");
        V4Core.clearPrivateFiles(this);
        NotificationHelper.clearDedupe(this);
        getSharedPreferences("boni_v4_plain", MODE_PRIVATE).edit()
                .remove("pending_chat").apply();
        currentScopeType = "";
        pendingPushCompany = "";
        pendingPushChatId = "";
        showLogin("Сеанс завершён");

        io.execute(() -> {
            try { if (!rkToken.isBlank()) V4Core.Api.json(V4Core.RK, "POST", "/api/mobile/v4/auth/logout", rkToken, new JSONObject()); } catch (Exception ignored) {}
            try { if (!boreyToken.isBlank()) V4Core.Api.json(V4Core.BOREY, "POST", "/api/mobile/v4/auth/logout", boreyToken, new JSONObject()); } catch (Exception ignored) {}
        });
    }

    private void authAwareError(Exception e) {
        if (e instanceof V4Core.ApiException && (((V4Core.ApiException) e).status == 401 || ((V4Core.ApiException) e).status == 403)) {
            V4Core.SecureStore.token(this, company, "");
            showLogin(messageOf(e));
        } else {
            Toast.makeText(this, messageOf(e), Toast.LENGTH_LONG).show();
        }
    }

    private String messageOf(Exception e) {
        String m = e == null ? "Неизвестная ошибка" : e.getMessage();
        if (m == null || m.isBlank()) m = e.getClass().getSimpleName();
        return m.length() > 300 ? m.substring(0, 300) : m;
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATIONS);
        }
    }
}
