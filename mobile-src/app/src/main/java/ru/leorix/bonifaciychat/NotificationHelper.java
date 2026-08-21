package ru.leorix.bonifaciychat;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

import java.util.Locale;

public final class NotificationHelper {
    public static final String CHANNEL_MESSAGES = "bonifaciy_chat_messages";
    private NotificationHelper() {}

    public static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_MESSAGES,
                "Сообщения Бонифация",
                NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("Новые сообщения рабочего чата Бонифаций");
        channel.enableVibration(true);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.createNotificationChannel(channel);
    }

    public static void showMessage(
            Context context,
            String companyKey,
            String companyName,
            String chatId,
            String chatTitle,
            String sender,
            String preview,
            String attachmentName,
            String messageId,
            String chatUrl,
            int unreadCount) {

        if (Build.VERSION.SDK_INT >= 33 && context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        ensureChannel(context);
        String cleanSender = clean(sender, 80);
        String cleanChat = clean(chatTitle, 100);
        String cleanPreview = cleanPreview(preview);
        String cleanAttachment = clean(attachmentName, 120);
        String cleanCompany = clean(companyName, 80);

        if (cleanPreview.isEmpty()) {
            cleanPreview = cleanAttachment.isEmpty() ? "Новое сообщение" : "📎 " + cleanAttachment;
        }

        String title;
        if (!cleanSender.isEmpty() && !cleanChat.isEmpty()) title = cleanSender + " · " + cleanChat;
        else if (!cleanSender.isEmpty()) title = cleanSender;
        else if (!cleanChat.isEmpty()) title = cleanChat;
        else title = cleanCompany.isEmpty() ? "Бонифаций" : "Бонифаций · " + cleanCompany;

        Intent open = new Intent(context, PushOpenActivity.class);
        open.putExtra("company_key", safeCompanyKey(companyKey));
        open.putExtra("chat_url", chatUrl == null ? "" : chatUrl);
        open.putExtra("chat_id", chatId == null ? "" : chatId);
        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);

        int requestCode = stableHash((companyKey == null ? "" : companyKey) + "|" + (chatId == null ? "" : chatId));
        PendingIntent pending = PendingIntent.getActivity(
                context,
                requestCode,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(context, CHANNEL_MESSAGES)
                : new Notification.Builder(context);

        Notification.BigTextStyle style = new Notification.BigTextStyle()
                .setBigContentTitle(title)
                .bigText(cleanPreview);
        if (!cleanCompany.isEmpty()) style.setSummaryText(cleanCompany);

        builder.setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(cleanPreview)
                .setStyle(style)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setContentIntent(pending)
                .setOnlyAlertOnce(false)
                .setGroup("boni_chat_" + safeCompanyKey(companyKey))
                .setNumber(Math.max(1, unreadCount));

        Notification publicVersion = (Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(context, CHANNEL_MESSAGES)
                : new Notification.Builder(context))
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle("Бонифаций")
                .setContentText("Новое сообщение")
                .setCategory(Notification.CATEGORY_MESSAGE)
                .build();
        builder.setPublicVersion(publicVersion);

        if (Build.VERSION.SDK_INT < 26) builder.setPriority(Notification.PRIORITY_HIGH);

        String notificationKey = safeCompanyKey(companyKey) + "|" + (chatId == null ? "" : chatId);
        int notificationId = stableHash(notificationKey);
        if (notificationId == 0) notificationId = stableHash(messageId == null ? "bonifaciy" : messageId);

        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.notify(notificationId, builder.build());
    }

    private static String cleanPreview(String value) {
        String text = clean(value, 360);
        text = text.replaceAll("\\s+", " ").trim();
        return text;
    }

    private static String clean(String value, int max) {
        if (value == null) return "";
        String out = value.replace('\u0000', ' ').replaceAll("[\\r\\n\\t]+", " ").trim();
        if (out.length() > max) out = out.substring(0, max - 1).trim() + "…";
        return out;
    }

    private static String safeCompanyKey(String key) {
        String value = key == null ? "" : key.trim().toLowerCase(Locale.ROOT);
        return "borey".equals(value) ? "borey" : "rk";
    }

    private static int stableHash(String value) {
        int hash = value == null ? 1 : value.hashCode();
        return hash == Integer.MIN_VALUE ? 1 : Math.abs(hash);
    }
}
