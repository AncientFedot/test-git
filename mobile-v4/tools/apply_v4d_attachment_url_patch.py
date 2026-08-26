from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app/src/main/java/ru/leorix/bonifaciychat/MainActivity.java"
BUILD = ROOT / "app/build.gradle"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"V4D patch anchor {label!r}: expected 1, found {count}")
    return text.replace(old, new, 1)


s = MAIN.read_text(encoding="utf-8").replace("\r\n", "\n")

old = '''    private void addAttachmentButtons(LinearLayout card, JSONObject m) {
        int messageId = m.optInt("id", 0);
        String messageFallback = messageId > 0 ? "/api/mobile/v4/chat/attachment/message/" + messageId : "";
        boolean added = false;

        JSONArray a = m.optJSONArray("attachments");
        if (a != null) {
            for (int i = 0; i < a.length(); i++) {
                JSONObject item = a.optJSONObject(i);
                if (item == null) continue;
                int attachmentId = item.optInt("id", item.optInt("attachment_id", 0));
                String name = first(item, "original_name", "filename", "name");
                if (attachmentId > 0) {
                    attachmentButton(card, name, "/api/mobile/v4/chat/attachment/file/" + attachmentId, messageFallback);
                    added = true;
                }
            }
        }
        JSONObject single = m.optJSONObject("attachment");
        if (single != null) {
            int attachmentId = single.optInt("id", single.optInt("attachment_id", 0));
            String name = first(single, "original_name", "filename", "name");
            if (attachmentId > 0) {
                attachmentButton(card, name, "/api/mobile/v4/chat/attachment/file/" + attachmentId, messageFallback);
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
            String inferredName = messageText.substring("Файлы:".length()).replace('\\n', ' ').replace('\\r', ' ').trim();
            if (inferredName.isBlank()) inferredName = "Вложение";
            attachmentButton(card, inferredName, messageFallback, "");
        }
    }
'''

new = '''    private String nativeAttachmentPathFromWebUrl(String rawUrl) {
        String url = rawUrl == null ? "" : rawUrl.trim();
        if (url.isBlank()) return "";
        String filePrefix = "/chat/attachment-files/";
        String messagePrefix = "/chat/attachments/";
        try {
            if (url.startsWith(filePrefix)) {
                int id = Integer.parseInt(url.substring(filePrefix.length()).split("[/?#]", 2)[0]);
                if (id > 0) return "/api/mobile/v4/chat/attachment/file/" + id;
            }
            if (url.startsWith(messagePrefix)) {
                int id = Integer.parseInt(url.substring(messagePrefix.length()).split("[/?#]", 2)[0]);
                if (id > 0) return "/api/mobile/v4/chat/attachment/message/" + id;
            }
        } catch (Exception ignored) {}
        return "";
    }

    private String primaryAttachmentPath(JSONObject item, int messageId) {
        String fromUrl = nativeAttachmentPathFromWebUrl(first(item, "url", "download_url", "href"));
        if (!fromUrl.isBlank()) return fromUrl;
        int attachmentId = item.optInt("attachment_id", item.optInt("id", 0));
        if (attachmentId > 0) return "/api/mobile/v4/chat/attachment/file/" + attachmentId;
        return messageId > 0 ? "/api/mobile/v4/chat/attachment/message/" + messageId : "";
    }

    private void addAttachmentButtons(LinearLayout card, JSONObject m) {
        int messageId = m.optInt("id", 0);
        String messageFallback = messageId > 0 ? "/api/mobile/v4/chat/attachment/message/" + messageId : "";
        boolean added = false;

        JSONArray a = m.optJSONArray("attachments");
        if (a != null) {
            for (int i = 0; i < a.length(); i++) {
                JSONObject item = a.optJSONObject(i);
                if (item == null) continue;
                String name = first(item, "original_name", "filename", "name");
                String primary = primaryAttachmentPath(item, messageId);
                if (!primary.isBlank()) {
                    String fallback = primary.equals(messageFallback) ? "" : messageFallback;
                    attachmentButton(card, name, primary, fallback);
                    added = true;
                }
            }
        }
        JSONObject single = m.optJSONObject("attachment");
        if (single != null) {
            String name = first(single, "original_name", "filename", "name");
            String primary = primaryAttachmentPath(single, messageId);
            if (!primary.isBlank()) {
                String fallback = primary.equals(messageFallback) ? "" : messageFallback;
                attachmentButton(card, name, primary, fallback);
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
            String inferredName = messageText.substring("Файлы:".length()).replace('\\n', ' ').replace('\\r', ' ').trim();
            if (inferredName.isBlank()) inferredName = "Вложение";
            attachmentButton(card, inferredName, messageFallback, "");
        }
    }
'''

s = replace_once(s, old, new, "attachment URL resolver")
MAIN.write_text(s, encoding="utf-8", newline="\n")

b = BUILD.read_text(encoding="utf-8").replace("\r\n", "\n")
b = replace_once(b, "versionCode 22", "versionCode 23", "versionCode")
b = replace_once(b, "versionName '4.0c-native-internal'", "versionName '4.0d-native-internal'", "versionName")
BUILD.write_text(b, encoding="utf-8", newline="\n")

print("V4D_ATTACHMENT_URL_PATCH=OK")
