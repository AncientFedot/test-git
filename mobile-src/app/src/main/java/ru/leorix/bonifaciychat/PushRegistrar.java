package ru.leorix.bonifaciychat;

import android.Manifest;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.webkit.CookieManager;

import com.google.android.gms.tasks.Tasks;
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
import java.util.concurrent.TimeUnit;
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

    public interface DiagnosticsCallback {
        void onResult(String report);
    }

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

    public static void collectDiagnostics(Context context, DiagnosticsCallback callback) {
        final Context app = context.getApplicationContext();
        final String company = selectedCompany(app);
        final String base = "borey".equals(company) ? BOREY : RK;
        final String cookie = readCookie(base);
        final boolean notificationPermission = Build.VERSION.SDK_INT < 33
                || app.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;

        IO.execute(() -> {
            SharedPreferences p = app.getSharedPreferences("boni_push", Context.MODE_PRIVATE);
            String fid = "";
            String token = "";
            String fidError = "";
            String tokenError = "";

            if (BonifaciyApp.isFirebaseConfigured()) {
                try {
                    fid = Tasks.await(FirebaseInstallations.getInstance().getId(), 8, TimeUnit.SECONDS);
                    if (fid == null) fid = "";
                } catch (Exception e) {
                    fidError = shortError(e);
                }
                try {
                    token = Tasks.await(FirebaseMessaging.getInstance().getToken(), 10, TimeUnit.SECONDS);
                    if (token == null) token = "";
                    if (!token.isBlank()) p.edit().putString("fresh_fcm_token", token).apply();
                } catch (Exception e) {
                    tokenError = shortError(e);
                    token = p.getString("fresh_fcm_token", "");
                }
            }

            if (!cookie.isBlank() && !fid.isBlank() && !token.isBlank()) {
                register(app, company, base, cookie, fid, token, p);
            }

            ServerStatus status = queryServerStatus(base, cookie);
            StringBuilder r = new StringBuilder();
            r.append("V3C native diagnostics\n");
            r.append("App: ").append(appVersion(app)).append('\n');
            r.append("Company: ").append(company).append('\n');
            r.append("Firebase configured: ").append(BonifaciyApp.isFirebaseConfigured() ? "YES" : "NO").append('\n');
            r.append("Notifications permission: ").append(notificationPermission ? "YES" : "NO").append('\n');
            r.append("Session cookie: ").append(cookie.isBlank() ? "NO" : "YES").append('\n');
            r.append("FID: ").append(fid.isBlank() ? "NO" : "YES");
            if (!fidError.isBlank()) r.append(" [").append(fidError).append(']');
            r.append('\n');
            r.append("FCM token: ").append(token.isBlank() ? "NO" : "YES");
            if (!token.isBlank()) r.append(" (len ").append(token.length()).append(')');
            if (!tokenError.isBlank()) r.append(" [").append(tokenError).append(']');
            r.append('\n');
            r.append("Register HTTP: ").append(p.getInt("last_http_" + company, 0)).append('\n');
            String stage = p.getString("last_stage_" + company, "never");
            r.append("Register stage: ").append(stage == null ? "never" : stage).append('\n');
            String lastError = p.getString("last_error_" + company, "");
            r.append("Register error: ").append(lastError == null || lastError.isBlank() ? "NONE" : lastError).append('\n');
            r.append("Last success: ").append(p.getLong("last_success_" + company, 0L) > 0L ? "YES" : "NO").append('\n');
            r.append("Status HTTP: ").append(status.httpCode).append('\n');
            r.append("Registered devices: ").append(status.registeredDevices).append('\n');
            r.append("Server Firebase key: ").append(status.firebaseKey).append('\n');
            if (!status.error.isBlank()) r.append("Status error: ").append(status.error).append('\n');

            MAIN.post(() -> {
                if (callback != null) callback.onResult(r.toString());
            });
        });
    }

    private static void attempt(Context context, boolean force) {
        if (!BonifaciyApp.isFirebaseConfigured()) return;
        long now = System.currentTimeMillis();
        long previous = LAST_ATTEMPT.get();
        if (now - previous < ATTEMPT_RATE_LIMIT_MS) return;
        if (!LAST_ATTEMPT.compareAndSet(previous, now)) return;

        String company = selectedCompany(context);
        String base = "borey".equals(company) ? BOREY : RK;
        String cookie = readCookie(base);

        SharedPreferences p = context.getSharedPreferences("boni_push", Context.MODE_PRIVATE);
        p.edit()
                .putLong("last_attempt_" + company, now)
                .putString("last_stage_" + company, cookie.isBlank() ? "NO_SESSION" : "WAITING_FIREBASE")
                .apply();

        if (cookie.isBlank()) {
            revokeIfBound(context, company, base, p);
            return;
        }

        long lastSuccess = p.getLong("last_success_" + company, 0L);
        if (!force && now - lastSuccess < SUCCESS_TTL_MS) return;

        final String sessionCookie = cookie;
        FirebaseInstallations.getInstance().getId().addOnCompleteListener(fidTask -> {
            if (!fidTask.isSuccessful()) {
                p.edit().putString("last_stage_" + company, "FID_ERROR")
                        .putString("last_error_" + company, shortError(fidTask.getException())).apply();
                return;
            }
            String fid = fidTask.getResult();
            if (fid == null || fid.isBlank()) {
                p.edit().putString("last_stage_" + company, "FID_EMPTY").apply();
                return;
            }

            FirebaseMessaging.getInstance().getToken().addOnCompleteListener(tokenTask -> {
                String token = tokenTask.isSuccessful() ? tokenTask.getResult() : p.getString("fresh_fcm_token", "");
                if (!tokenTask.isSuccessful()) {
                    p.edit().putString("last_stage_" + company, "TOKEN_ERROR")
                            .putString("last_error_" + company, shortError(tokenTask.getException())).apply();
                }
                if (token == null || token.isBlank()) {
                    p.edit().putString("last_stage_" + company, "TOKEN_EMPTY").apply();
                    return;
                }
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
            p.edit().putString("last_stage_" + company, "REGISTERING")
                    .putString("last_error_" + company, "").apply();
            URL url = new URL(base + "/api/mobile/push/register");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(7000);
            conn.setReadTimeout(7000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("Cookie", cookie);
            conn.setRequestProperty("User-Agent", "BonifaciyChatAndroid/3.2");
            conn.setRequestProperty("X-Bonifaciy-Mobile-App", "android-v3c");

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
            p.edit().putInt("last_http_" + company, code).apply();
            if (code < 200 || code >= 300) {
                p.edit().putString("last_stage_" + company, "HTTP_ERROR").apply();
                return;
            }

            String body = readBody(conn.getInputStream());
            String revokeSecret = "";
            try {
                JSONObject response = body.isBlank() ? new JSONObject() : new JSONObject(body);
                revokeSecret = response.optString("revoke_secret", "");
            } catch (Exception ignored) {
            }

            SharedPreferences.Editor e = p.edit()
                    .putString("fid_" + company, fid)
                    .putLong("last_success_" + company, System.currentTimeMillis())
                    .putString("last_stage_" + company, "OK")
                    .putString("last_error_" + company, "");
            if (!revokeSecret.isBlank()) e.putString("revoke_secret_" + company, revokeSecret);
            e.apply();
        } catch (Exception e) {
            p.edit().putString("last_stage_" + company, "EXCEPTION")
                    .putString("last_error_" + company, shortError(e)).apply();
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
                conn.setRequestProperty("User-Agent", "BonifaciyChatAndroid/3.2");
                conn.setRequestProperty("X-Bonifaciy-Mobile-App", "android-v3c");

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

    private static ServerStatus queryServerStatus(String base, String cookie) {
        ServerStatus out = new ServerStatus();
        if (cookie == null || cookie.isBlank()) {
            out.error = "NO_SESSION";
            return out;
        }
        HttpURLConnection conn = null;
        try {
            URL url = new URL(base + "/api/mobile/push/status");
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(7000);
            conn.setReadTimeout(7000);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Accept", "application/json");
            conn.setRequestProperty("Cookie", cookie);
            conn.setRequestProperty("User-Agent", "BonifaciyChatAndroid/3.2");
            out.httpCode = conn.getResponseCode();
            InputStream input = out.httpCode >= 200 && out.httpCode < 400 ? conn.getInputStream() : conn.getErrorStream();
            String body = readBody(input);
            if (!body.isBlank()) {
                try {
                    JSONObject j = new JSONObject(body);
                    out.registeredDevices = String.valueOf(j.optInt("registered_devices", -1));
                    if (j.has("firebase_key_present")) out.firebaseKey = j.optBoolean("firebase_key_present") ? "OK" : "NO";
                } catch (Exception e) {
                    out.error = "BAD_JSON";
                }
            }
        } catch (Exception e) {
            out.error = shortError(e);
        } finally {
            if (conn != null) conn.disconnect();
        }
        return out;
    }

    private static String readCookie(String base) {
        try {
            String cookie = CookieManager.getInstance().getCookie(base + "/chat");
            return cookie == null ? "" : cookie;
        } catch (Exception ignored) {
            return "";
        }
    }

    private static String selectedCompany(Context context) {
        String company = context.getSharedPreferences("boni", Context.MODE_PRIVATE).getString("company", "rk");
        return "borey".equals(company) ? "borey" : "rk";
    }

    private static String appVersion(Context context) {
        try {
            return context.getPackageManager().getPackageInfo(context.getPackageName(), 0).versionName;
        } catch (Exception ignored) {
            return "3.2-test";
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

    private static String shortError(Throwable e) {
        if (e == null) return "UNKNOWN";
        Throwable root = e;
        while (root.getCause() != null && root.getCause() != root) root = root.getCause();
        String name = root.getClass().getSimpleName();
        String msg = root.getMessage();
        if (msg == null || msg.isBlank()) return name;
        msg = msg.replace('\n', ' ').replace('\r', ' ').trim();
        if (msg.length() > 180) msg = msg.substring(0, 180) + "…";
        return name + ": " + msg;
    }

    private static final class ServerStatus {
        int httpCode = 0;
        String registeredDevices = "?";
        String firebaseKey = "?";
        String error = "";
    }
}
