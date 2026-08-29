package ru.leorix.bonifaciychat;

import android.app.Activity;
import android.app.Application;
import android.os.Bundle;

import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;

public class BonifaciyApp extends Application {
    private static volatile boolean firebaseConfigured = false;

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationHelper.ensureChannel(this);
        firebaseConfigured = initializeFirebase();

        if (firebaseConfigured) {
            PushRegistrar.scheduleRegistration(this, 1500L, 7000L, 20000L, 60000L);
            PushRegistrar.startPeriodic(this);
            registerActivityLifecycleCallbacks(new ActivityLifecycleCallbacks() {
                @Override public void onActivityCreated(Activity activity, Bundle state) {}
                @Override public void onActivityStarted(Activity activity) {}
                @Override public void onActivityResumed(Activity activity) {
                    PushRegistrar.scheduleRegistration(BonifaciyApp.this, 1200L, 8000L);
                }
                @Override public void onActivityPaused(Activity activity) {}
                @Override public void onActivityStopped(Activity activity) {}
                @Override public void onActivitySaveInstanceState(Activity activity, Bundle outState) {}
                @Override public void onActivityDestroyed(Activity activity) {}
            });
        }
    }

    private boolean initializeFirebase() {
        String appId = BuildConfig.FIREBASE_APP_ID == null ? "" : BuildConfig.FIREBASE_APP_ID.trim();
        String apiKey = BuildConfig.FIREBASE_API_KEY == null ? "" : BuildConfig.FIREBASE_API_KEY.trim();
        String projectId = BuildConfig.FIREBASE_PROJECT_ID == null ? "" : BuildConfig.FIREBASE_PROJECT_ID.trim();
        String senderId = BuildConfig.FIREBASE_SENDER_ID == null ? "" : BuildConfig.FIREBASE_SENDER_ID.trim();
        if (appId.isEmpty() || apiKey.isEmpty() || projectId.isEmpty() || senderId.isEmpty()) return false;

        try {
            if (!FirebaseApp.getApps(this).isEmpty()) return true;
            FirebaseOptions options = new FirebaseOptions.Builder()
                    .setApplicationId(appId)
                    .setApiKey(apiKey)
                    .setProjectId(projectId)
                    .setGcmSenderId(senderId)
                    .build();
            FirebaseApp.initializeApp(this, options);
            return !FirebaseApp.getApps(this).isEmpty();
        } catch (Exception ignored) {
            return false;
        }
    }

    public static boolean isFirebaseConfigured() {
        return firebaseConfigured;
    }
}
