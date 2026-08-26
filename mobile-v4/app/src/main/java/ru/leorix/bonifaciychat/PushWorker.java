package ru.leorix.bonifaciychat;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;

import androidx.annotation.NonNull;
import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import com.google.android.gms.tasks.Tasks;
import com.google.firebase.installations.FirebaseInstallations;
import com.google.firebase.messaging.FirebaseMessaging;

import org.json.JSONObject;

import java.util.concurrent.TimeUnit;

public final class PushWorker extends Worker {
    private static final String MODE_REGISTER = "register";
    private static final String MODE_UNREGISTER = "unregister";

    public PushWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    public static void enqueueRegister(Context context, String company) {
        enqueue(context, company, MODE_REGISTER, ExistingWorkPolicy.REPLACE);
    }

    public static void enqueueRegisterBoth(Context context) {
        for (String company : new String[]{V4Core.RK, V4Core.BOREY}) {
            if (!V4Core.SecureStore.token(context, company).isBlank()) enqueueRegister(context, company);
        }
    }

    public static void enqueueUnregister(Context context, String company) {
        if (!V4Core.SecureStore.revoke(context, company).isBlank()) {
            enqueue(context, company, MODE_UNREGISTER, ExistingWorkPolicy.REPLACE);
        }
    }

    public static void enqueueUnregisterBoth(Context context) {
        enqueueUnregister(context, V4Core.RK);
        enqueueUnregister(context, V4Core.BOREY);
    }

    private static void enqueue(Context context, String company, String mode, ExistingWorkPolicy policy) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(PushWorker.class)
                .setInputData(new androidx.work.Data.Builder()
                        .putString("company", company)
                        .putString("mode", mode)
                        .build())
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build();
        WorkManager.getInstance(context).enqueueUniqueWork(
                "boni-v4-push-" + mode + "-" + company,
                policy,
                request);
    }

    @NonNull
    @Override
    public Result doWork() {
        String company = getInputData().getString("company");
        String mode = getInputData().getString("mode");
        if (!V4Core.RK.equals(company) && !V4Core.BOREY.equals(company)) return Result.failure();
        try {
            if (MODE_UNREGISTER.equals(mode)) return unregister(company);
            return register(company);
        } catch (V4Core.ApiException e) {
            if (e.status == 401 || e.status == 403 || e.status == 400 || e.status == 404) return Result.success();
            return Result.retry();
        } catch (Exception e) {
            return Result.retry();
        }
    }

    private Result register(String company) throws Exception {
        String accessToken = V4Core.SecureStore.token(getApplicationContext(), company);
        if (accessToken.isBlank()) return Result.success();

        String fcm = Tasks.await(FirebaseMessaging.getInstance().getToken(), 20, TimeUnit.SECONDS);
        String fid = Tasks.await(FirebaseInstallations.getInstance().getId(), 20, TimeUnit.SECONDS);
        if (fcm == null || fcm.length() < 40 || fid == null || fid.isBlank()) return Result.retry();

        JSONObject body = new JSONObject();
        body.put("platform", "android");
        body.put("company_key", company);
        body.put("fid", fid);
        body.put("registration_token", fcm);
        body.put("device_model", Build.MANUFACTURER + " " + Build.MODEL);
        body.put("android_sdk", Build.VERSION.SDK_INT);
        body.put("app_version", BuildConfig.VERSION_NAME);

        JSONObject response = V4Core.Api.json(
                company, "POST", "/api/mobile/v4/push/register", accessToken, body);
        String revoke = response.optString("revoke_secret", "");
        if (!revoke.isBlank()) V4Core.SecureStore.revoke(getApplicationContext(), company, revoke);
        getApplicationContext().getSharedPreferences("boni_v4_plain", Context.MODE_PRIVATE)
                .edit().putString("fid_" + company, fid).apply();
        return Result.success();
    }

    private Result unregister(String company) throws Exception {
        Context context = getApplicationContext();
        String revoke = V4Core.SecureStore.revoke(context, company);
        if (revoke.isBlank()) return Result.success();
        SharedPreferences plain = context.getSharedPreferences("boni_v4_plain", Context.MODE_PRIVATE);
        String fid = plain.getString("fid_" + company, "");
        if (fid == null || fid.isBlank()) {
            try {
                fid = Tasks.await(FirebaseInstallations.getInstance().getId(), 20, TimeUnit.SECONDS);
            } catch (Exception ignored) {
                return Result.retry();
            }
        }
        JSONObject body = new JSONObject();
        body.put("platform", "android");
        body.put("company_key", company);
        body.put("fid", fid);
        body.put("revoke_secret", revoke);
        V4Core.Api.json(company, "POST", "/api/mobile/v4/push/unregister", "", body);
        V4Core.SecureStore.revoke(context, company, "");
        plain.edit().remove("fid_" + company).apply();
        return Result.success();
    }
}
