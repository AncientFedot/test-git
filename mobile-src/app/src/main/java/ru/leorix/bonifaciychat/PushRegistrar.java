package ru.leorix.bonifaciychat;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.webkit.CookieManager;

import com.google.firebase.installations.FirebaseInstallations;
import com.google.firebase.messaging.FirebaseMessaging;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

public final class PushRegistrar {
    private static final String RK = "https://crm.leorix.ru";
    private static final String BOREY = "https://borey.crm.leorix.ru";
    private static final long SUCCESS_TTL_MS = 6L * 60L * 60L * 1000L;
    private static final long ATTEMPT_RATE_LIMIT_MS = 4000L;

    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final ExecutorService IO = Executors.newSingleThreadExecutor();
    private static final AtomicLong LAST_ATTEMPT = new AtomicLong(0L);
    private static final AtomicBoolean PERIODIC_STARTED = new AtomicBoolean(false);

    private PushRegistrar() {}

    public static void startPeriodic(Context context) {
        Context app = context.getApplicationContext();
        if (!PERIODIC_STARTED.compareAndSet(false, true)) return;
        Runnable task = new Runnable() {
            @Override public void run() {
                attempt(app, false);
                MAIN.postDelayed(this, 30000L);
            }
        };
        MAIN.postDelayed(task, 30000L);
    }

    public static void scheduleRegistration(Context context, long... delaysMs) {
        Context app = context.getApplicationContext();
        if (!BonifaciyApp.isFirebaseConfigured()) return;
        if (delaysMs == null || delaysMs.length == 0) {
            MAIN.post(() -> attempt(app, true));
            return;
        }
        for (long delay : delaysMs) {
            MAIN.postDelayed(() -> attempt(app, true), Math.max(0L, delay));
        }
    }

    public static void noteFreshToken(Context context, String token) {
        if (token == null || token.isBlank()) return;
        SharedPreferences p = context.getSharedPreferences("boni_push", Context.MODE_PRIVATE);
        p.edit().putString("fresh_fcm_token", token).apply();
        String company = selectedCompany(context);
        p.edit().putLong("last_success_" + company, 0L).apply();
    }

    private static void attempt(Context context, boolean force) {
        if (!BonifaciyApp.isFirebaseConfigured()) return;
        long now = System.currentTimeMillis();
        long previous = LAST_ATTEMPT.get();
        if (now - previous < ATTEMPT_RATE_LIMIT_MS) return;
        if (!LAST_ATTEMPT.compareAndSet(previous, now)) return;

        String company = selectedCompany(context);
        String base = "borey".equals(company) ? BOREY : RK;
        String cookie;
        try {
            cookie = CookieManager.getInstance().getCookie(base + "/chat");
        } catch (Exception ignored) {
            cookie = null;
        }

        SharedPreferences p = context.getSharedPreferences("boni_push", Context.MODE_PRIVATE);
        if (cookie == null || cookie.isBlank()) {
            revokeIfBound(context, company, base, p);
            return;
        }

        long lastSuccess = p.getLong("last_success_" + company, 0L);
        if (!force && now - lastSuccess < SUCCESS_TTL_MS) return;

        final String sessionCookie = cookie;
        FirebaseInstallations.getInstance().getId().addOnCompleteListener(fidTask -> {
            if (!fidTask.isSuccessful()) return;
            String fid = fidTask.getResult();
            if (fid == null || fid.isBlank()) return;

            FirebaseMessaging.getInstance().getToken().addOnCompleteListener(tokenTask -> {
                String token = tokenTask.isSuccessful() ? tokenTask.getResult() : p.getString("fresh_fcm_token", "");
                IO.execute(() -> register(context, company, base, sessionCookie, fid, token, p));
            });
        });
    }

    private static void register(
            Context context,
            String company,
            String base,
            String cookie,
            String fid,
            String token,
            SharedPreferences p) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(base + "/api/mobile/push/register");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(7000);
            conn.setReadTimeout(7000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("Cookie", cookie);
            conn.setRequestProperty("User-Agent", "BonifaciyChatAndroid/3.0");
            conn.setRequestProperty("X-Bonifaciy-Mobile-App", "android-v3");

            JSONObject payload = new JSONObject();
            payload.put("platform", "android");
            payload.put("company_key", company);
            payload.put("fid", fid);
            payload.put("registration_token", token == null ? "" : token);
            payload.put("device_model", Build.MANUFACTURER + " " + Build.MODEL);
            payload.put("android_sdk", Build.VERSION.SDK_INT);
            payload.put("app_version", appVersion(context));

            byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
            conn.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(bytes);
            }

            int code = conn.getResponseCode();
            if (code < 200 || code >= 300) return;

            String body = readBody(conn.getInputStream());
            String revokeSecret = "";
            try {
                JSONObject response = body.isBlank() ? new JSONObject() : new JSONObject(body);
                revokeSecret = response.optString("revoke_secret", "");
            } catch (Exception ignored) {
            }

            SharedPreferences.Editor e = p.edit()
                    .putString("fid_" + company, fid)
                    .putLong("last_success_" + company, System.currentTimeMillis());
            if (!revokeSecret.isBlank()) e.putString("revoke_secret_" + company, revokeSecret);
            e.apply();
        } catch (Exception ignored) {
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private static void revokeIfBound(Context context, String company, String base, SharedPreferences p) {
        String fid = p.getString("fid_" + company, "");
        String secret = p.getString("revoke_secret_" + company, "");
        if (fid.isBlank() || secret.isBlank()) return;

        IO.execute(() -> {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(base + "/api/mobile/push/unregister");
                conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(7000);
                conn.setReadTimeout(7000);
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setRequestProperty("Accept", "application/json");
                conn.setRequestProperty("User-Agent", "BonifaciyChatAndroid/3.0");
                conn.setRequestProperty("X-Bonifaciy-Mobile-App", "android-v3");

                JSONObject payload = new JSONObject();
                payload.put("platform", "android");
                payload.put("company_key", company);
                payload.put("fid", fid);
                payload.put("revoke_secret", secret);
                byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
                conn.setFixedLengthStreamingMode(bytes.length);
                try (OutputStream out = conn.getOutputStream()) {
                    out.write(bytes);
                }

                int code = conn.getResponseCode();
                if (code >= 200 && code < 300) {
                    p.edit()
                            .remove("fid_" + company)
                            .remove("revoke_secret_" + company)
                            .remove("last_success_" + company)
                            .apply();
                }
            } catch (Exception ignored) {
            } finally {
                if (conn != null) conn.disconnect();
            }
        });
    }

    private static String selectedCompany(Context context) {
        String company = context.getSharedPreferences("boni", Context.MODE_PRIVATE).getString("company", "rk");
        return "borey".equals(company) ? "borey" : "rk";
    }

    private static String appVersion(Context context) {
        try {
            return context.getPackageManager().getPackageInfo(context.getPackageName(), 0).versionName;
        } catch (Exception ignored) {
            return "3.0-test";
        }
    }

    private static String readBody(InputStream input) {
        if (input == null) return "";
        StringBuilder out = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) out.append(line);
        } catch (Exception ignored) {
        }
        return out.toString();
    }
}
