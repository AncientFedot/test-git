package ru.leorix.bonifaciychat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

public final class BonifaciyMessagingService extends FirebaseMessagingService {
    @Override
    public void onNewToken(String token) {
        super.onNewToken(token);
        PushWorker.enqueueRegisterBoth(this);
    }

    @Override
    public void onMessageReceived(RemoteMessage message) {
        super.onMessageReceived(message);
        if (message == null || message.getData() == null) return;
        if (!"chat_message".equals(message.getData().get("type"))) return;
        NotificationHelper.showChat(this, message.getData());
    }
}
