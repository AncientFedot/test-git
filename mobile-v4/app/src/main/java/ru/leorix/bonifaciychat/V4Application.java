package ru.leorix.bonifaciychat;

import android.app.Application;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;

public final class V4Application extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        if (FirebaseApp.getApps(this).isEmpty()
                && !BuildConfig.FIREBASE_APP_ID.isBlank()
                && !BuildConfig.FIREBASE_API_KEY.isBlank()
                && !BuildConfig.FIREBASE_PROJECT_ID.isBlank()
                && !BuildConfig.FIREBASE_SENDER_ID.isBlank()) {
            FirebaseOptions options = new FirebaseOptions.Builder()
                    .setApplicationId(BuildConfig.FIREBASE_APP_ID)
                    .setApiKey(BuildConfig.FIREBASE_API_KEY)
                    .setProjectId(BuildConfig.FIREBASE_PROJECT_ID)
                    .setGcmSenderId(BuildConfig.FIREBASE_SENDER_ID)
                    .build();
            FirebaseApp.initializeApp(this, options);
        }
        NotificationHelper.ensureChannel(this);
    }
}
