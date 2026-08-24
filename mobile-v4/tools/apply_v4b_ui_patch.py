from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java"
EXPECTED_SHA = "f2090f39c4635858dc0f05adb08f8187dc546c91"  # Git blob SHA of accepted V4A source


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"V4B patch anchor {label!r}: expected 1, found {count}")
    return text.replace(old, new, 1)


raw = MAIN.read_bytes()
actual = git_blob_sha(raw)
if actual != EXPECTED_SHA:
    raise SystemExit(f"V4B source guard failed: MainActivity blob={actual} expected={EXPECTED_SHA}")

s = raw.decode("utf-8").replace("\r\n", "\n")

s = replace_once(
    s,
    "import android.graphics.Color;\n",
    "import android.graphics.Color;\nimport android.graphics.drawable.GradientDrawable;\n",
    "GradientDrawable import",
)

s = replace_once(
    s,
    '''    private Button button(String label) {\n        Button b = new Button(this);\n        b.setText(label);\n        b.setAllCaps(false);\n        b.setMinHeight(0);\n        b.setMinWidth(0);\n        return b;\n    }\n''',
    '''    private Button button(String label) {\n        Button b = new Button(this);\n        b.setText(label);\n        b.setAllCaps(false);\n        b.setMinHeight(0);\n        b.setMinWidth(0);\n        return b;\n    }\n\n    private GradientDrawable rounded(int fill, int radiusDp) {\n        GradientDrawable d = new GradientDrawable();\n        d.setColor(fill);\n        d.setCornerRadius(dp(radiusDp));\n        return d;\n    }\n\n    private GradientDrawable roundedStroke(int fill, int radiusDp, int stroke) {\n        GradientDrawable d = rounded(fill, radiusDp);\n        d.setStroke(dp(1), stroke);\n        return d;\n    }\n\n    private String shortTimestamp(String raw) {\n        String value = raw == null ? "" : raw.trim();\n        if (value.length() >= 16 && value.charAt(2) == '.' && value.charAt(5) == '.') {\n            return value.substring(0, 5) + " · " + value.substring(11, 16);\n        }\n        return value;\n    }\n''',
    "UI helpers",
)

s = replace_once(
    s,
    '''        Button dialogs = button("☰");\n        dialogs.setTextColor(Color.WHITE);\n        dialogs.setBackgroundColor(Color.TRANSPARENT);\n''',
    '''        Button dialogs = button("☰");\n        dialogs.setContentDescription("Список чатов");\n        dialogs.setTextColor(Color.WHITE);\n        dialogs.setBackgroundColor(Color.TRANSPARENT);\n''',
    "dialogs accessibility",
)

s = replace_once(
    s,
    '''        Button reload = button("↻");\n        reload.setTextColor(Color.WHITE);\n        reload.setBackgroundColor(Color.TRANSPARENT);\n''',
    '''        Button reload = button("↻");\n        reload.setContentDescription("Обновить чат");\n        reload.setTextColor(Color.WHITE);\n        reload.setBackgroundColor(Color.TRANSPARENT);\n''',
    "reload accessibility",
)

s = replace_once(
    s,
    '''        Button logout = button("⎋");\n        logout.setTextColor(Color.WHITE);\n        logout.setBackgroundColor(Color.TRANSPARENT);\n''',
    '''        Button logout = button("⏻");\n        logout.setContentDescription("Выйти");\n        logout.setTextColor(Color.WHITE);\n        logout.setBackgroundColor(Color.TRANSPARENT);\n''',
    "logout icon",
)

s = replace_once(
    s,
    '''    private void updateCompanyLabel() {\n        companyButton.setText("TEST V4 · " + V4Core.companyName(company));\n    }\n''',
    '''    private void updateCompanyLabel() {\n        companyButton.setText(V4Core.companyName(company) + "  ▾");\n        companyButton.setContentDescription("Компания: " + V4Core.companyName(company));\n    }\n''',
    "company label",
)

s = replace_once(
    s,
    '''        ScrollView scroll = new ScrollView(this);\n        LinearLayout messages = new LinearLayout(this);\n''',
    '''        ScrollView scroll = new ScrollView(this);\n        scroll.setFillViewport(true);\n        scroll.setFocusable(false);\n        scroll.setSmoothScrollingEnabled(false);\n        LinearLayout messages = new LinearLayout(this);\n''',
    "scroll settings",
)

s = replace_once(
    s,
    '''        LinearLayout composerRow = new LinearLayout(this);\n        composerRow.setGravity(Gravity.BOTTOM);\n        Button attach = button("＋");\n        attach.setOnClickListener(v -> pickFile());\n        composerRow.addView(attach, new LinearLayout.LayoutParams(dp(52), dp(52)));\n\n        composer = new EditText(this);\n        composer.setHint("Сообщение");\n        composer.setMaxLines(4);\n        composer.setMinLines(1);\n        composerRow.addView(composer, new LinearLayout.LayoutParams(0, -2, 1f));\n\n        Button send = button("➤");\n        send.setOnClickListener(v -> sendCurrent());\n        composerRow.addView(send, new LinearLayout.LayoutParams(dp(58), dp(52)));\n        wrap.addView(composerRow, new LinearLayout.LayoutParams(-1, -2));\n''',
    '''        LinearLayout composerRow = new LinearLayout(this);\n        composerRow.setGravity(Gravity.CENTER_VERTICAL);\n        composerRow.setPadding(dp(8), dp(6), dp(8), dp(8));\n        composerRow.setBackgroundColor(Color.WHITE);\n\n        Button attach = button("📎");\n        attach.setTextSize(19);\n        attach.setContentDescription("Прикрепить файл");\n        attach.setBackground(rounded(Color.rgb(226, 232, 240), 14));\n        attach.setOnClickListener(v -> pickFile());\n        LinearLayout.LayoutParams attachLp = new LinearLayout.LayoutParams(dp(48), dp(48));\n        attachLp.setMargins(0, 0, dp(7), 0);\n        composerRow.addView(attach, attachLp);\n\n        composer = new EditText(this);\n        composer.setHint("Написать сообщение…");\n        composer.setTextSize(16);\n        composer.setPadding(dp(12), dp(9), dp(12), dp(9));\n        composer.setBackground(roundedStroke(Color.WHITE, 16, Color.rgb(203, 213, 225)));\n        composer.setMaxLines(4);\n        composer.setMinLines(1);\n        LinearLayout.LayoutParams composerLp = new LinearLayout.LayoutParams(0, -2, 1f);\n        composerLp.setMargins(0, 0, dp(7), 0);\n        composerRow.addView(composer, composerLp);\n\n        Button send = button("➤");\n        send.setTextSize(18);\n        send.setTextColor(Color.WHITE);\n        send.setContentDescription("Отправить сообщение");\n        send.setBackground(rounded(Color.rgb(92, 35, 35), 14));\n        send.setOnClickListener(v -> sendCurrent());\n        composerRow.addView(send, new LinearLayout.LayoutParams(dp(52), dp(48)));\n        wrap.addView(composerRow, new LinearLayout.LayoutParams(-1, -2));\n''',
    "composer UI",
)

s = replace_once(
    s,
    '''                runOnUiThread(() -> {\n                    renderMessages(container, finalMessages);\n                    scroll.post(() -> scroll.fullScroll(View.FOCUS_DOWN));\n                });\n''',
    '''                runOnUiThread(() -> {\n                    renderMessages(container, finalMessages);\n                    container.post(() -> scroll.postDelayed(() -> {\n                        scroll.fullScroll(View.FOCUS_DOWN);\n                        scroll.scrollTo(0, Math.max(0, container.getHeight() - scroll.getHeight()));\n                    }, 80));\n                });\n''',
    "reliable bottom scroll",
)

old_render = '''    private void renderMessages(LinearLayout container, JSONArray messages) {\n        container.removeAllViews();\n        for (int i = 0; i < messages.length(); i++) {\n            JSONObject m = messages.optJSONObject(i);\n            if (m == null) continue;\n            LinearLayout card = new LinearLayout(this);\n            card.setOrientation(LinearLayout.VERTICAL);\n            card.setPadding(dp(10), dp(7), dp(10), dp(7));\n            card.setBackgroundColor(i % 2 == 0 ? Color.rgb(241, 245, 249) : Color.rgb(248, 250, 252));\n\n            String author = authorOf(m);\n            String created = first(m, "created_at", "created", "timestamp");\n            TextView meta = text((author.isBlank() ? "Сообщение" : author) + (created.isBlank() ? "" : "  ·  " + created), 12);\n            meta.setTextColor(Color.rgb(71, 85, 105));\n            card.addView(meta);\n\n            String message = first(m, "message", "text", "content");\n            if (!message.isBlank()) {\n                TextView value = text(message, 15);\n                value.setTextIsSelectable(true);\n                card.addView(value);\n            }\n            addAttachmentButtons(card, m);\n            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);\n            lp.setMargins(0, 0, 0, dp(5));\n            container.addView(card, lp);\n        }\n        if (messages.length() == 0) container.addView(text("Сообщений пока нет", 14));\n    }\n\n    private String authorOf(JSONObject m) {\n        JSONObject u = m.optJSONObject("user");\n        if (u != null) {\n            String v = first(u, "full_name", "name", "username");\n            if (!v.isBlank()) return v;\n        }\n        return first(m, "user_full_name", "author", "author_name", "username", "user_name");\n    }\n\n    private String first(JSONObject o, String... keys) {\n        for (String key : keys) {\n            String v = o.optString(key, "").trim();\n            if (!v.isBlank() && !"null".equalsIgnoreCase(v)) return v;\n        }\n        return "";\n    }\n'''

new_render = '''    private void renderMessages(LinearLayout container, JSONArray messages) {\n        container.removeAllViews();\n        int bubbleMax = Math.max(dp(220), getResources().getDisplayMetrics().widthPixels - dp(96));\n        for (int i = 0; i < messages.length(); i++) {\n            JSONObject m = messages.optJSONObject(i);\n            if (m == null) continue;\n            boolean own = m.optBoolean("is_own", false);\n\n            LinearLayout card = new LinearLayout(this);\n            card.setOrientation(LinearLayout.VERTICAL);\n            card.setPadding(dp(11), dp(7), dp(11), dp(8));\n            card.setBackground(rounded(\n                    own ? Color.rgb(225, 236, 255) : Color.WHITE,\n                    15));\n            card.setElevation(dp(1));\n\n            String author = own ? "Вы" : authorOf(m);\n            String created = shortTimestamp(first(m, "created_at", "created", "timestamp"));\n            String metaValue = (author.isBlank() ? "Сообщение" : author)\n                    + (created.isBlank() ? "" : "  ·  " + created);\n            TextView meta = text(metaValue, 11);\n            meta.setMaxWidth(bubbleMax);\n            meta.setTextColor(own ? Color.rgb(30, 64, 175) : Color.rgb(71, 85, 105));\n            card.addView(meta);\n\n            String message = first(m, "message", "text", "content");\n            if (!message.isBlank()) {\n                TextView value = text(message, 16);\n                value.setMaxWidth(bubbleMax);\n                value.setTextIsSelectable(true);\n                value.setTextColor(Color.rgb(15, 23, 42));\n                card.addView(value);\n            }\n            addAttachmentButtons(card, m);\n\n            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);\n            lp.gravity = own ? Gravity.END : Gravity.START;\n            if (own) lp.setMargins(dp(52), 0, dp(8), dp(8));\n            else lp.setMargins(dp(8), 0, dp(52), dp(8));\n            container.addView(card, lp);\n        }\n        if (messages.length() == 0) {\n            TextView empty = text("Здесь пока нет сообщений", 14);\n            empty.setGravity(Gravity.CENTER);\n            container.addView(empty, new LinearLayout.LayoutParams(-1, -2));\n        }\n    }\n\n    private String authorOf(JSONObject m) {\n        JSONObject author = m.optJSONObject("author");\n        if (author != null) {\n            String v = first(author, "full_name", "name", "username");\n            if (!v.isBlank()) return v;\n        }\n        JSONObject user = m.optJSONObject("user");\n        if (user != null) {\n            String v = first(user, "full_name", "name", "username");\n            if (!v.isBlank()) return v;\n        }\n        return first(m, "user_full_name", "author_name", "username", "user_name");\n    }\n\n    private String first(JSONObject o, String... keys) {\n        for (String key : keys) {\n            Object raw = o.opt(key);\n            if (raw == null || raw == JSONObject.NULL || raw instanceof JSONObject || raw instanceof JSONArray) continue;\n            String v = String.valueOf(raw).trim();\n            if (!v.isBlank() && !"null".equalsIgnoreCase(v)) return v;\n        }\n        return "";\n    }\n'''

s = replace_once(s, old_render, new_render, "message bubbles + author parsing")

s = replace_once(
    s,
    '''            selectedAttachmentLabel.setText("📎 Файл выбран. Нажмите ➤ для отправки");\n''',
    '''            selectedAttachmentLabel.setText("📎 Файл прикреплён · отправится вместе с сообщением");\n''',
    "attachment label",
)

MAIN.write_text(s, encoding="utf-8", newline="\n")
print("V4B_UI_PATCH=OK")
print("MAIN_SHA256=" + hashlib.sha256(MAIN.read_bytes()).hexdigest())
