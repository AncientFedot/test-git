package ru.leorix.bonifaciychat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

public class BonifaciyMessagingService extends FirebaseMessagingService {
    @Override
    public void onMessageReceived(RemoteMessage remoteMessage) {
        Map<String, String> data = remoteMessage.getData();
        if (data == null || data.isEmpty()) return;

        String type = data.get("type");
        if (type != null && !type.isBlank() && !"chat_message".equals(type)) return;

        String companyKey = value(data, "company_key", "rk");
        String companyName = value(data, "company_name", "Бонифаций");
        String chatId = value(data, "chat_id", "");
        String chatTitle = value(data, "chat_title", "");
        String sender = value(data, "sender", "");
        String preview = value(data, "preview", "");
        String attachmentName = value(data, "attachment_name", "");
        String messageId = value(data, "message_id", remoteMessage.getMessageId());
        String chatUrl = value(data, "chat_url", "");
        int unreadCount = parseInt(value(data, "unread_count", "1"), 1);

        NotificationHelper.showMessage(
                this,
                companyKey,
                companyName,
                chatId,
                chatTitle,
                sender,
                preview,
                attachmentName,
                messageId,
                chatUrl,
                unreadCount);
    }

    @Override
    public void onNewToken(String token) {
        super.onNewToken(token);
        PushRegistrar.noteFreshToken(this, token);
        PushRegistrar.scheduleRegistration(this, 1000L, 5000L, 20000L);
    }

    private static String value(Map<String, String> data, String key, String fallback) {
        String value = data.get(key);
        return value == null ? fallback : value;
    }

    private static int parseInt(String value, int fallback) {
        try {
            return Math.max(1, Integer.parseInt(value));
        } catch (Exception ignored) {
            return fallback;
        }
    }
}
