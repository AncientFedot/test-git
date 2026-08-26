from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java"
SERVICE = ROOT / "app/src/main/java/ru/leorix/bonifaciychat/BonifaciyMessagingService.java"
NOTIFY = ROOT / "app/src/main/java/ru/leorix/bonifaciychat/NotificationHelper.java"
BUILD = ROOT / "app/build.gradle"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"V4E patch anchor {label!r}: expected 1, found {count}")
    return text.replace(old, new, 1)


s = MAIN.read_text(encoding="utf-8").replace("\r\n", "\n")

required = [
    'versionName \'4.0d-native-internal\'' in BUILD.read_text(encoding="utf-8"),
    'nativeAttachmentPathFromWebUrl' in s,
    'V4Core.SecureStore.get(this, "remember_password_"' in s,
    'companyButton.setText(V4Core.companyName(company) + "  ▾")' in s,
]
if not all(required):
    raise SystemExit("V4E requires accepted V4D/V4C/V4B source")

s = replace_once(
    s,
    "import java.net.URLEncoder;\n",
    "import java.lang.ref.WeakReference;\nimport java.net.URLEncoder;\n",
    "WeakReference import",
)

fields_old = '''    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private FrameLayout body;
'''
fields_new = '''    private static WeakReference<MainActivity> foregroundActivity = new WeakReference<>(null);

    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private FrameLayout body;
'''
s = replace_once(s, fields_old, fields_new, "foreground activity field")

pending_old = '''    private String pendingPushCompany = "";
    private String pendingPushChatId = "";
'''
pending_new = '''    private String pendingPushCompany = "";
    private String pendingPushChatId = "";
    private String pendingPushChatTitle = "";

    private boolean activityResumed = false;
    private volatile boolean chatSyncInFlight = false;
    private LinearLayout activeMessagesContainer;
    private ScrollView activeMessagesScroll;
    private TextView activeChatTitleView;
    private TextView newMessagesIndicator;
    private int lastMessageId = 0;
'''
s = replace_once(s, pending_old, pending_new, "live sync state fields")

lifecycle_old = '''    @Override
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
'''
lifecycle_new = '''    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        consumePushIntent(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        activityResumed = true;
        foregroundActivity = new WeakReference<>(this);
        if (!currentScopeType.isBlank() && activeMessagesContainer != null) {
            syncOpenChatIncremental(false);
        }
    }

    @Override
    protected void onPause() {
        activityResumed = false;
        MainActivity current = foregroundActivity.get();
        if (current == this) foregroundActivity.clear();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        activityResumed = false;
        MainActivity current = foregroundActivity.get();
        if (current == this) foregroundActivity.clear();
        io.shutdownNow();
        super.onDestroy();
    }

    static void onChatPushReceived(String pushCompany, String chatId, String chatTitle) {
        MainActivity activity = foregroundActivity.get();
        if (activity == null) return;
        activity.runOnUiThread(() -> activity.handleForegroundChatPush(pushCompany, chatId, chatTitle));
    }
'''
s = replace_once(s, lifecycle_old, lifecycle_new, "resume/push lifecycle")

login_push_old = '''                    if (!pendingPushChatId.isBlank() && targetCompany.equals(pendingPushCompany)) {
                        String chat = pendingPushChatId;
                        pendingPushChatId = "";
                        pendingPushCompany = "";
                        openChatId(chat);
                    } else {
'''
login_push_new = '''                    if (!pendingPushChatId.isBlank() && targetCompany.equals(pendingPushCompany)) {
                        String chat = pendingPushChatId;
                        String title = pendingPushChatTitle;
                        pendingPushChatId = "";
                        pendingPushCompany = "";
                        pendingPushChatTitle = "";
                        openChatId(chat, title);
                    } else {
'''
s = replace_once(s, login_push_old, login_push_new, "pending push title after login")

show_chat_title_old = '''        TextView titleView = text(currentTitle, 18);
        titleView.setTextColor(Color.rgb(15, 23, 42));
        titleView.setSingleLine(true);
        wrap.addView(titleView, new LinearLayout.LayoutParams(-1, dp(44)));
'''
show_chat_title_new = '''        TextView titleView = text(currentTitle, 18);
        titleView.setTextColor(Color.rgb(15, 23, 42));
        titleView.setSingleLine(true);
        activeChatTitleView = titleView;
        wrap.addView(titleView, new LinearLayout.LayoutParams(-1, dp(44)));
'''
s = replace_once(s, show_chat_title_old, show_chat_title_new, "active chat title reference")

indicator_anchor = '''        selectedAttachmentLabel = text("", 12);
        selectedAttachmentLabel.setVisibility(View.GONE);
        wrap.addView(selectedAttachmentLabel, new LinearLayout.LayoutParams(-1, -2));
'''
indicator_new = '''        newMessagesIndicator = text("↓ Новые сообщения", 13);
        newMessagesIndicator.setTextColor(Color.rgb(30, 64, 175));
        newMessagesIndicator.setGravity(Gravity.CENTER);
        newMessagesIndicator.setPadding(dp(8), dp(5), dp(8), dp(5));
        newMessagesIndicator.setVisibility(View.GONE);
        newMessagesIndicator.setOnClickListener(v -> scrollChatToBottom());
        wrap.addView(newMessagesIndicator, new LinearLayout.LayoutParams(-1, -2));

        selectedAttachmentLabel = text("", 12);
        selectedAttachmentLabel.setVisibility(View.GONE);
        wrap.addView(selectedAttachmentLabel, new LinearLayout.LayoutParams(-1, -2));
'''
s = replace_once(s, indicator_anchor, indicator_new, "new messages indicator")

show_chat_end_old = '''        wrap.addView(composerRow, new LinearLayout.LayoutParams(-1, -2));
        replaceBody(wrap);
        loadMessages(messages, scroll);
    }
'''
show_chat_end_new = '''        wrap.addView(composerRow, new LinearLayout.LayoutParams(-1, -2));
        replaceBody(wrap);
        activeMessagesContainer = messages;
        activeMessagesScroll = scroll;
        lastMessageId = 0;
        chatSyncInFlight = false;
        loadMessages(messages, scroll);
    }
'''
s = replace_once(s, show_chat_end_old, show_chat_end_new, "active chat references")

render_old = '''    private void renderMessages(LinearLayout container, JSONArray messages) {
        container.removeAllViews();
        int bubbleMax = Math.max(dp(220), getResources().getDisplayMetrics().widthPixels - dp(96));
        for (int i = 0; i < messages.length(); i++) {
            JSONObject m = messages.optJSONObject(i);
            if (m == null) continue;
            boolean own = m.optBoolean("is_own", false);

            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(dp(11), dp(7), dp(11), dp(8));
            card.setBackground(rounded(
                    own ? Color.rgb(225, 236, 255) : Color.WHITE,
                    15));
            card.setElevation(dp(1));

            String author = own ? "Вы" : authorOf(m);
            String created = shortTimestamp(first(m, "created_at", "created", "timestamp"));
            String metaValue = (author.isBlank() ? "Сообщение" : author)
                    + (created.isBlank() ? "" : "  ·  " + created);
            TextView meta = text(metaValue, 11);
            meta.setMaxWidth(bubbleMax);
            meta.setTextColor(own ? Color.rgb(30, 64, 175) : Color.rgb(71, 85, 105));
            card.addView(meta);

            String message = first(m, "message", "text", "content");
            if (!message.isBlank()) {
                TextView value = text(message, 16);
                value.setMaxWidth(bubbleMax);
                value.setTextIsSelectable(true);
                value.setTextColor(Color.rgb(15, 23, 42));
                card.addView(value);
            }
            addAttachmentButtons(card, m);

            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);
            lp.gravity = own ? Gravity.END : Gravity.START;
            if (own) lp.setMargins(dp(52), 0, dp(8), dp(8));
            else lp.setMargins(dp(8), 0, dp(52), dp(8));
            container.addView(card, lp);
        }
        if (messages.length() == 0) {
            TextView empty = text("Здесь пока нет сообщений", 14);
            empty.setGravity(Gravity.CENTER);
            container.addView(empty, new LinearLayout.LayoutParams(-1, -2));
        }
    }
'''
render_new = '''    private void renderMessages(LinearLayout container, JSONArray messages) {
        container.removeAllViews();
        lastMessageId = 0;
        for (int i = 0; i < messages.length(); i++) {
            JSONObject m = messages.optJSONObject(i);
            if (m == null) continue;
            addMessageCard(container, m);
            lastMessageId = Math.max(lastMessageId, m.optInt("id", 0));
        }
        if (messages.length() == 0) {
            TextView empty = text("Здесь пока нет сообщений", 14);
            empty.setGravity(Gravity.CENTER);
            container.addView(empty, new LinearLayout.LayoutParams(-1, -2));
        }
    }

    private int appendMessages(LinearLayout container, JSONArray messages) {
        int added = 0;
        for (int i = 0; i < messages.length(); i++) {
            JSONObject m = messages.optJSONObject(i);
            if (m == null) continue;
            int messageId = m.optInt("id", 0);
            if (messageId > 0 && messageId <= lastMessageId) continue;
            if (container.getChildCount() == 1) {
                View only = container.getChildAt(0);
                if (only instanceof TextView && "Здесь пока нет сообщений".contentEquals(((TextView) only).getText())) {
                    container.removeAllViews();
                }
            }
            addMessageCard(container, m);
            if (messageId > 0) lastMessageId = Math.max(lastMessageId, messageId);
            added++;
        }
        return added;
    }

    private void addMessageCard(LinearLayout container, JSONObject m) {
        int bubbleMax = Math.max(dp(220), getResources().getDisplayMetrics().widthPixels - dp(96));
        boolean own = m.optBoolean("is_own", false);

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(11), dp(7), dp(11), dp(8));
        card.setBackground(rounded(own ? Color.rgb(225, 236, 255) : Color.WHITE, 15));
        card.setElevation(dp(1));

        String author = own ? "Вы" : authorOf(m);
        String created = shortTimestamp(first(m, "created_at", "created", "timestamp"));
        String metaValue = (author.isBlank() ? "Сообщение" : author)
                + (created.isBlank() ? "" : "  ·  " + created);
        TextView meta = text(metaValue, 11);
        meta.setMaxWidth(bubbleMax);
        meta.setTextColor(own ? Color.rgb(30, 64, 175) : Color.rgb(71, 85, 105));
        card.addView(meta);

        String message = first(m, "message", "text", "content");
        if (!message.isBlank()) {
            TextView value = text(message, 16);
            value.setMaxWidth(bubbleMax);
            value.setTextIsSelectable(true);
            value.setTextColor(Color.rgb(15, 23, 42));
            card.addView(value);
        }
        addAttachmentButtons(card, m);

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);
        lp.gravity = own ? Gravity.END : Gravity.START;
        if (own) lp.setMargins(dp(52), 0, dp(8), dp(8));
        else lp.setMargins(dp(8), 0, dp(52), dp(8));
        container.addView(card, lp);
    }
'''
s = replace_once(s, render_old, render_new, "incremental message renderer")

sync_anchor = '''    private void refreshCurrent() {
        if (currentScopeType.isBlank()) showDialogs();
        else showChat(currentScopeType, currentScopeId, currentTitle);
    }
'''
sync_code = '''    private boolean isChatNearBottom() {
        if (activeMessagesContainer == null || activeMessagesScroll == null) return true;
        int remaining = activeMessagesContainer.getHeight()
                - (activeMessagesScroll.getScrollY() + activeMessagesScroll.getHeight());
        return remaining <= dp(96);
    }

    private void scrollChatToBottom() {
        if (activeMessagesContainer == null || activeMessagesScroll == null) return;
        if (newMessagesIndicator != null) newMessagesIndicator.setVisibility(View.GONE);
        activeMessagesContainer.post(() -> activeMessagesScroll.post(() -> {
            activeMessagesScroll.fullScroll(View.FOCUS_DOWN);
            activeMessagesScroll.scrollTo(0, Math.max(0,
                    activeMessagesContainer.getHeight() - activeMessagesScroll.getHeight()));
        }));
    }

    private String currentChatId() {
        if (currentScopeType.isBlank()) return "";
        return currentScopeType + ":" + ("general".equals(currentScopeType) ? 0 : currentScopeId);
    }

    private void handleForegroundChatPush(String pushCompany, String chatId, String chatTitle) {
        if (!activityResumed || !company.equals(pushCompany) || !currentChatId().equals(chatId)) return;
        if (chatTitle != null && !chatTitle.isBlank()) {
            currentTitle = chatTitle.trim();
            if (activeChatTitleView != null) activeChatTitleView.setText(currentTitle);
        }
        syncOpenChatIncremental(true);
    }

    private void syncOpenChatIncremental(boolean pushTriggered) {
        if (chatSyncInFlight || currentScopeType.isBlank() || activeMessagesContainer == null || activeMessagesScroll == null) return;
        final String c = company;
        final String token = V4Core.SecureStore.token(this, c);
        if (token.isBlank()) return;
        final String scope = currentScopeType;
        final int scopeId = currentScopeId;
        final int afterId = lastMessageId;
        if (afterId <= 0) return;
        final LinearLayout container = activeMessagesContainer;
        final ScrollView scroll = activeMessagesScroll;
        final boolean nearBottomBefore = isChatNearBottom();
        final String path = "/api/mobile/v4/chat/messages?scope_type="
                + URLEncoder.encode(scope, StandardCharsets.UTF_8)
                + "&scope_id=" + scopeId
                + "&after_id=" + afterId
                + "&limit=100";

        chatSyncInFlight = true;
        io.execute(() -> {
            try {
                JSONObject response = V4Core.Api.json(c, "GET", path, token, null);
                JSONArray messages = response.optJSONArray("messages");
                if (messages == null) messages = new JSONArray();
                JSONArray finalMessages = messages;
                if (messages.length() > 0) {
                    JSONObject read = new JSONObject();
                    read.put("scope_type", scope);
                    read.put("scope_id", scopeId);
                    try { V4Core.Api.json(c, "POST", "/api/mobile/v4/chat/read", token, read); }
                    catch (Exception ignored) {}
                }
                runOnUiThread(() -> {
                    if (!company.equals(c) || !currentScopeType.equals(scope) || currentScopeId != scopeId
                            || activeMessagesContainer != container || activeMessagesScroll != scroll) return;
                    int added = appendMessages(container, finalMessages);
                    if (added <= 0) return;
                    if (nearBottomBefore) {
                        scrollChatToBottom();
                    } else if (newMessagesIndicator != null) {
                        newMessagesIndicator.setText("↓ Новые сообщения (" + added + ")");
                        newMessagesIndicator.setVisibility(View.VISIBLE);
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    if (e instanceof V4Core.ApiException
                            && ((((V4Core.ApiException) e).status == 401) || (((V4Core.ApiException) e).status == 403))) {
                        authAwareError(e);
                    }
                });
            } finally {
                chatSyncInFlight = false;
            }
        });
    }

    private void refreshCurrent() {
        if (currentScopeType.isBlank()) showDialogs();
        else showChat(currentScopeType, currentScopeId, currentTitle);
    }
'''
s = replace_once(s, sync_anchor, sync_code, "event-driven incremental sync")

consume_old = '''        String pushCompany = intent.getStringExtra("push_company");
        String chatId = intent.getStringExtra("push_chat_id");
        if ((!V4Core.RK.equals(pushCompany) && !V4Core.BOREY.equals(pushCompany)) || chatId == null || chatId.isBlank()) return false;
        pendingPushCompany = pushCompany;
        pendingPushChatId = chatId;
'''
consume_new = '''        String pushCompany = intent.getStringExtra("push_company");
        String chatId = intent.getStringExtra("push_chat_id");
        String chatTitle = intent.getStringExtra("push_chat_title");
        if ((!V4Core.RK.equals(pushCompany) && !V4Core.BOREY.equals(pushCompany)) || chatId == null || chatId.isBlank()) return false;
        pendingPushCompany = pushCompany;
        pendingPushChatId = chatId;
        pendingPushChatTitle = chatTitle == null ? "" : chatTitle.trim();
'''
s = replace_once(s, consume_old, consume_new, "consume push title")

consume_open_old = '''        else {
            pendingPushCompany = "";
            pendingPushChatId = "";
            openChatId(chatId);
        }
        intent.removeExtra("push_company");
        intent.removeExtra("push_chat_id");
        return true;
    }

    private void openChatId(String chatId) {
'''
consume_open_new = '''        else {
            String title = pendingPushChatTitle;
            pendingPushCompany = "";
            pendingPushChatId = "";
            pendingPushChatTitle = "";
            openChatId(chatId, title);
        }
        intent.removeExtra("push_company");
        intent.removeExtra("push_chat_id");
        intent.removeExtra("push_chat_title");
        return true;
    }

    private void openChatId(String chatId) {
        openChatId(chatId, "");
    }

    private void openChatId(String chatId, String pushedTitle) {
'''
s = replace_once(s, consume_open_old, consume_open_new, "open push with real title")

open_title_old = '''        String title = "direct".equals(scope) ? "Личный чат" : "project".equals(scope) ? "Проектный чат" : "Рабочий чат";
        showChat(scope, id, title);
'''
open_title_new = '''        String fallbackTitle = "direct".equals(scope) ? "Личный чат" : "project".equals(scope) ? "Проектный чат" : "Рабочий чат";
        String title = pushedTitle == null || pushedTitle.isBlank() ? fallbackTitle : pushedTitle.trim();
        showChat(scope, id, title);
'''
s = replace_once(s, open_title_old, open_title_new, "real pushed room title")

logout_pending_old = '''        pendingPushCompany = "";
        pendingPushChatId = "";
        showLogin("Сеанс завершён");
'''
logout_pending_new = '''        pendingPushCompany = "";
        pendingPushChatId = "";
        pendingPushChatTitle = "";
        showLogin("Сеанс завершён");
'''
s = replace_once(s, logout_pending_old, logout_pending_new, "clear pending push title")

MAIN.write_text(s, encoding="utf-8", newline="\n")

service = SERVICE.read_text(encoding="utf-8").replace("\r\n", "\n")
service_old = '''        if (!"chat_message".equals(message.getData().get("type"))) return;
        NotificationHelper.showChat(this, message.getData());
'''
service_new = '''        if (!"chat_message".equals(message.getData().get("type"))) return;
        NotificationHelper.showChat(this, message.getData());
        MainActivity.onChatPushReceived(
                message.getData().get("company_key"),
                message.getData().get("chat_id"),
                message.getData().get("chat_title"));
'''
service = replace_once(service, service_old, service_new, "foreground push callback")
SERVICE.write_text(service, encoding="utf-8", newline="\n")

notify = NOTIFY.read_text(encoding="utf-8").replace("\r\n", "\n")
notify_old = '''        intent.putExtra("push_company", company);
        intent.putExtra("push_chat_id", chatId);
        intent.putExtra("push_message_id", messageId);
'''
notify_new = '''        intent.putExtra("push_company", company);
        intent.putExtra("push_chat_id", chatId);
        intent.putExtra("push_message_id", messageId);
        intent.putExtra("push_chat_title", chatTitle);
'''
notify = replace_once(notify, notify_old, notify_new, "notification real chat title")
NOTIFY.write_text(notify, encoding="utf-8", newline="\n")

b = BUILD.read_text(encoding="utf-8").replace("\r\n", "\n")
b = replace_once(b, "versionCode 23", "versionCode 24", "versionCode")
b = replace_once(b, "versionName '4.0d-native-internal'", "versionName '4.0e-native-internal'", "versionName")
BUILD.write_text(b, encoding="utf-8", newline="\n")

checks = {
    "event-driven push callback": "onChatPushReceived" in MAIN.read_text(encoding="utf-8"),
    "incremental after_id": "&after_id=" in MAIN.read_text(encoding="utf-8"),
    "resume sync": "protected void onResume()" in MAIN.read_text(encoding="utf-8"),
    "no periodic sync loop": "postDelayed" not in MAIN.read_text(encoding="utf-8"),
    "real push title": "push_chat_title" in MAIN.read_text(encoding="utf-8") and "push_chat_title" in NOTIFY.read_text(encoding="utf-8"),
    "scroll preservation indicator": "Новые сообщения (" in MAIN.read_text(encoding="utf-8"),
}
for label, ok in checks.items():
    if not ok:
        raise SystemExit(f"V4E generated gate failed: {label}")

print("V4E_EVENT_DRIVEN_CHAT_SYNC_PATCH=OK")
