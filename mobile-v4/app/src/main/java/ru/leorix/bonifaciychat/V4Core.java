package ru.leorix.bonifaciychat;

import android.content.ContentResolver;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.UUID;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class V4Core {
    private V4Core() {}

    public static final String RK = "rk";
    public static final String BOREY = "borey";
    public static final int MAX_JSON_BYTES = 2 * 1024 * 1024;
    public static final long MAX_UPLOAD_BYTES = 25L * 1024L * 1024L;
    public static final long MAX_DOWNLOAD_BYTES = 50L * 1024L * 1024L;

    public static String baseUrl(String company) {
        if (BOREY.equals(company)) return BuildConfig.BOREY_BASE_URL;
        if (RK.equals(company)) return BuildConfig.RK_BASE_URL;
        throw new IllegalArgumentException("Unknown company");
    }

    public static String companyName(String company) {
        return BOREY.equals(company) ? "НПО БОРЕЙ" : "РК-ТЕХНИКА";
    }

    public static String deviceId(Context context) {
        SharedPreferences p = context.getSharedPreferences("boni_v4_plain", Context.MODE_PRIVATE);
        String id = p.getString("device_id", "");
        if (id == null || id.isBlank()) {
            id = UUID.randomUUID().toString();
            p.edit().putString("device_id", id).apply();
        }
        return id;
    }

    public static final class SecureStore {
        private static final String ALIAS = "bonifaciy_chat_v4_aes";
        private static final String PREF = "boni_v4_secure";

        private SecureStore() {}

        private static SecretKey key() throws Exception {
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            if (ks.containsAlias(ALIAS)) {
                return (SecretKey) ks.getKey(ALIAS, null);
            }
            KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            kg.init(new KeyGenParameterSpec.Builder(
                    ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setRandomizedEncryptionRequired(true)
                    .build());
            return kg.generateKey();
        }

        public static void put(Context context, String name, String value) {
            try {
                if (value == null || value.isBlank()) {
                    remove(context, name);
                    return;
                }
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.ENCRYPT_MODE, key());
                byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
                String packed = Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)
                        + "." + Base64.encodeToString(encrypted, Base64.NO_WRAP);
                context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                        .edit().putString(name, packed).apply();
            } catch (Exception e) {
                throw new IllegalStateException("Secure storage failed", e);
            }
        }

        public static String get(Context context, String name) {
            String packed = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
                    .getString(name, "");
            if (packed == null || packed.isBlank()) return "";
            try {
                String[] parts = packed.split("\\.", 2);
                if (parts.length != 2) return "";
                byte[] iv = Base64.decode(parts[0], Base64.NO_WRAP);
                byte[] encrypted = Base64.decode(parts[1], Base64.NO_WRAP);
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
                cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
                return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
            } catch (Exception e) {
                remove(context, name);
                return "";
            }
        }

        public static void remove(Context context, String name) {
            context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit().remove(name).apply();
        }

        public static String token(Context c, String company) { return get(c, "token_" + company); }
        public static void token(Context c, String company, String value) { put(c, "token_" + company, value); }
        public static String revoke(Context c, String company) { return get(c, "revoke_" + company); }
        public static void revoke(Context c, String company, String value) { put(c, "revoke_" + company, value); }
    }

    public static final class ApiException extends Exception {
        public final int status;
        public ApiException(int status, String message) { super(message); this.status = status; }
    }

    public static final class DownloadResult {
        public final File file;
        public final String mimeType;
        public DownloadResult(File file, String mimeType) { this.file = file; this.mimeType = mimeType; }
    }

    public static final class Api {
        private Api() {}

        private static HttpURLConnection open(String company, String path, String method, String token) throws Exception {
            if (path == null || !path.startsWith("/api/mobile/v4/")) {
                throw new SecurityException("Blocked non-V4 API path");
            }
            URL url = new URL(baseUrl(company) + path);
            String expectedHost = new URL(baseUrl(company)).getHost();
            if (!"https".equalsIgnoreCase(url.getProtocol())
                    || !expectedHost.equalsIgnoreCase(url.getHost())
                    || (url.getPort() != -1 && url.getPort() != 443)) {
                throw new SecurityException("Blocked API destination");
            }
            HttpURLConnection c = (HttpURLConnection) url.openConnection();
            c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(10_000);
            c.setReadTimeout(15_000);
            c.setRequestMethod(method);
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("Cache-Control", "no-store");
            c.setRequestProperty("User-Agent", "BonifaciyChatNative/4.0a Android");
            if (token != null && !token.isBlank()) c.setRequestProperty("Authorization", "Bearer " + token);
            return c;
        }

        private static byte[] readBounded(InputStream input, int max) throws Exception {
            if (input == null) return new byte[0];
            try (InputStream in = new BufferedInputStream(input); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[8192];
                int total = 0;
                int n;
                while ((n = in.read(buf)) >= 0) {
                    total += n;
                    if (total > max) throw new ApiException(0, "Ответ сервера слишком большой");
                    out.write(buf, 0, n);
                }
                return out.toByteArray();
            }
        }

        private static String errorMessage(int status, byte[] bytes) {
            String raw = new String(bytes, StandardCharsets.UTF_8).trim();
            try {
                JSONObject o = new JSONObject(raw);
                String detail = o.optString("detail", "").trim();
                if (!detail.isBlank()) return detail;
            } catch (Exception ignored) {}
            if (!raw.isBlank()) return raw.length() > 300 ? raw.substring(0, 300) : raw;
            return "HTTP " + status;
        }

        public static JSONObject json(String company, String method, String path, String token, JSONObject body) throws Exception {
            HttpURLConnection c = open(company, path, method, token);
            if (body != null) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
                if (payload.length > 256 * 1024) throw new IllegalArgumentException("JSON request too large");
                try (OutputStream out = new BufferedOutputStream(c.getOutputStream())) { out.write(payload); }
            }
            int status = c.getResponseCode();
            if (status >= 300 && status < 400) throw new ApiException(status, "Redirect blocked");
            byte[] bytes = readBounded(status >= 200 && status < 300 ? c.getInputStream() : c.getErrorStream(), MAX_JSON_BYTES);
            if (status < 200 || status >= 300) throw new ApiException(status, errorMessage(status, bytes));
            String raw = new String(bytes, StandardCharsets.UTF_8);
            return raw.isBlank() ? new JSONObject() : new JSONObject(raw);
        }

        public static JSONObject login(String company, String username, String password, String deviceId) throws Exception {
            JSONObject body = new JSONObject();
            body.put("username", username);
            body.put("password", password);
            body.put("device_id", deviceId);
            return json(company, "POST", "/api/mobile/v4/auth/login", "", body);
        }

        public static JSONObject sendMessage(Context context, String company, String token,
                                             String scopeType, int scopeId, String message, Uri attachment) throws Exception {
            String boundary = "----BoniV4" + UUID.randomUUID().toString().replace("-", "");
            HttpURLConnection c = open(company, "/api/mobile/v4/chat/send", "POST", token);
            c.setDoOutput(true);
            c.setChunkedStreamingMode(8192);
            c.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
            try (OutputStream out = new BufferedOutputStream(c.getOutputStream())) {
                form(out, boundary, "scope_type", scopeType);
                form(out, boundary, "scope_id", String.valueOf(scopeId));
                form(out, boundary, "message", message == null ? "" : message);
                form(out, boundary, "reply_to_id", "0");
                if (attachment != null) filePart(context, out, boundary, attachment);
                out.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
            }
            int status = c.getResponseCode();
            if (status >= 300 && status < 400) throw new ApiException(status, "Redirect blocked");
            byte[] bytes = readBounded(status >= 200 && status < 300 ? c.getInputStream() : c.getErrorStream(), MAX_JSON_BYTES);
            if (status < 200 || status >= 300) throw new ApiException(status, errorMessage(status, bytes));
            return new JSONObject(new String(bytes, StandardCharsets.UTF_8));
        }

        private static void form(OutputStream out, String boundary, String name, String value) throws Exception {
            String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + name + "\"\r\n\r\n";
            out.write(head.getBytes(StandardCharsets.UTF_8));
            out.write(value.getBytes(StandardCharsets.UTF_8));
            out.write("\r\n".getBytes(StandardCharsets.UTF_8));
        }

        private static void filePart(Context context, OutputStream out, String boundary, Uri uri) throws Exception {
            ContentResolver resolver = context.getContentResolver();
            long size = contentSize(resolver, uri);
            if (size > MAX_UPLOAD_BYTES) throw new IllegalArgumentException("Файл больше 25 МБ");
            String name = safeFileName(displayName(resolver, uri));
            String mime = resolver.getType(uri);
            if (mime == null || mime.isBlank()) mime = "application/octet-stream";
            String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"attachments\"; filename=\"" + name + "\"\r\nContent-Type: " + mime + "\r\n\r\n";
            out.write(head.getBytes(StandardCharsets.UTF_8));
            long total = 0;
            try (InputStream in = resolver.openInputStream(uri)) {
                if (in == null) throw new IllegalArgumentException("Не удалось открыть файл");
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) >= 0) {
                    total += n;
                    if (total > MAX_UPLOAD_BYTES) throw new IllegalArgumentException("Файл больше 25 МБ");
                    out.write(buf, 0, n);
                }
            }
            out.write("\r\n".getBytes(StandardCharsets.UTF_8));
        }

        public static DownloadResult download(Context context, String company, String token, String path, String suggestedName) throws Exception {
            HttpURLConnection c = open(company, path, "GET", token);
            c.setRequestProperty("Accept", "*/*");
            int status = c.getResponseCode();
            if (status >= 300 && status < 400) throw new ApiException(status, "Redirect blocked");
            if (status < 200 || status >= 300) {
                byte[] err = readBounded(c.getErrorStream(), MAX_JSON_BYTES);
                throw new ApiException(status, errorMessage(status, err));
            }
            long declared = c.getContentLengthLong();
            if (declared > MAX_DOWNLOAD_BYTES) throw new ApiException(0, "Файл больше 50 МБ");
            String name = safeFileName(suggestedName);
            if (name.isBlank()) name = "Вложение";
            File dir = new File(context.getFilesDir(), "attachments");
            if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("Не удалось создать приватную папку");
            File file = new File(dir, System.currentTimeMillis() + "_" + name);
            long total = 0;
            try (InputStream in = new BufferedInputStream(c.getInputStream()); OutputStream out = new FileOutputStream(file)) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) >= 0) {
                    total += n;
                    if (total > MAX_DOWNLOAD_BYTES) {
                        file.delete();
                        throw new ApiException(0, "Файл больше 50 МБ");
                    }
                    out.write(buf, 0, n);
                }
            }
            String mime = c.getContentType();
            if (mime == null || mime.isBlank()) mime = "application/octet-stream";
            return new DownloadResult(file, mime.split(";", 2)[0]);
        }

        private static long contentSize(ContentResolver resolver, Uri uri) {
            try (Cursor c = resolver.query(uri, new String[]{OpenableColumns.SIZE}, null, null, null)) {
                if (c != null && c.moveToFirst() && !c.isNull(0)) return c.getLong(0);
            } catch (Exception ignored) {}
            return -1;
        }

        private static String displayName(ContentResolver resolver, Uri uri) {
            try (Cursor c = resolver.query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                if (c != null && c.moveToFirst()) return c.getString(0);
            } catch (Exception ignored) {}
            String tail = uri.getLastPathSegment();
            return tail == null ? "Вложение" : tail;
        }

        public static String safeFileName(String raw) {
            String s = raw == null ? "" : raw.trim();
            s = s.replaceAll("[\\\\/:*?\"<>|\\r\\n]+", "_");
            s = s.replaceAll("\\s+", " ").trim();
            if (s.isBlank()) s = "Вложение";
            if (s.length() > 120) s = s.substring(0, 120);
            return s;
        }
    }

    public static void clearPrivateFiles(Context context) {
        deleteTree(new File(context.getFilesDir(), "attachments"));
    }

    private static void deleteTree(File file) {
        if (file == null || !file.exists()) return;
        File[] children = file.listFiles();
        if (children != null) for (File child : children) deleteTree(child);
        file.delete();
    }
}
