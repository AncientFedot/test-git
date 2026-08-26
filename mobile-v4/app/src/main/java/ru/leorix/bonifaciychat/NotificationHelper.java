package ru.leorix.bonifaciychat;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import org.json.JSONArray;

public final class NotificationHelper {
    private static final String CHANNEL = "bonifaciy_v4_messages";
    private static final Object DEDUPE_LOCK = new Object();

    private NotificationHelper() {}

    public static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationChannel c = new NotificationChannel(
                CHANNEL, "Сообщения Бонифация", NotificationManager.IMPORTANCE_HIGH);
        c.setDescription("Новые сообщения Бонифаций Чат V4");
        c.enableVibration(true);
        c.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
        context.getSystemService(NotificationManager.class).createNotificationChannel(c);
    }

    private static boolean remember(Context context, String key) {
        synchronized (DEDUPE_LOCK) {
            try {
                String raw = context.getSharedPreferences("boni_v4_push_dedupe", Context.MODE_PRIVATE)
                        .getString("keys", "[]");
                JSONArray a = new JSONArray(raw == null ? "[]" : raw);
                for (int i = 0; i < a.length(); i++) if (key.equals(a.optString(i))) return false;
                JSONArray next = new JSONArray();
                int start = Math.max(0, a.length() - 199);
                for (int i = start; i < a.length(); i++) next.put(a.optString(i));
                next.put(key);
                context.getSharedPreferences("boni_v4_push_dedupe", Context.MODE_PRIVATE)
                        .edit().putString("keys", next.toString()).commit();
                return true;
            } catch (Exception e) {
                return true;
            }
        }
    }

    public static void clearDedupe(Context context) {
        synchronized (DEDUPE_LOCK) {
            context.getSharedPreferences("boni_v4_push_dedupe", Context.MODE_PRIVATE).edit().clear().commit();
        }
    }

    public static void showChat(Context context, java.util.Map<String, String> data) {
        String company = safe(data.get("company_key"));
        String chatId = safe(data.get("chat_id"));
        String messageId = safe(data.get("message_id"));
        if ((!V4Core.RK.equals(company) && !V4Core.BOREY.equals(company)) || chatId.isBlank()) return;
        if (!remember(context, company + "|" + messageId)) return;

        String sender = safe(data.get("sender"));
        String chatTitle = safe(data.get("chat_title"));
        String preview = safe(data.get("preview"));
        String attachment = safe(data.get("attachment_name"));
        if (preview.isBlank() && !attachment.isBlank()) preview = "📎 " + attachment;
        if (preview.isBlank()) preview = "Новое сообщение";
        String title = sender.isBlank() ? V4Core.companyName(company)
                : sender + (chatTitle.isBlank() ? "" : " · " + chatTitle);

        Intent intent = new Intent(context, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        intent.putExtra("push_company", company);
        intent.putExtra("push_chat_id", chatId);
        intent.putExtra("push_message_id", messageId);
        int requestCode = (company + "|" + chatId).hashCode() & 0x7fffffff;
        PendingIntent pending = PendingIntent.getActivity(
                context, requestCode, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(context, CHANNEL)
                : new Notification.Builder(context);
        b.setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle(title)
                .setContentText(preview)
                .setStyle(new Notification.BigTextStyle().bigText(preview))
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setContentIntent(pending)
                .setPublicVersion(new Notification.Builder(context)
                        .setSmallIcon(android.R.drawable.stat_notify_chat)
                        .setContentTitle("Бонифаций Чат")
                        .setContentText("Новое рабочее сообщение")
                        .build());
        if (Build.VERSION.SDK_INT < 26) b.setPriority(Notification.PRIORITY_HIGH);
        int id = (company + "|" + chatId).hashCode() & 0x7fffffff;
        ((NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE)).notify(id, b.build());
    }

    private static String safe(String s) { return s == null ? "" : s.trim(); }
}
