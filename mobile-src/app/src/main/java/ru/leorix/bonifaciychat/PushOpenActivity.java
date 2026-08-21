package ru.leorix.bonifaciychat;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

public class PushOpenActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        String companyKey = getIntent().getStringExtra("company_key");
        if (!"borey".equals(companyKey)) companyKey = "rk";
        String chatUrl = getIntent().getStringExtra("chat_url");
        String chatId = getIntent().getStringExtra("chat_id");

        getSharedPreferences("boni", MODE_PRIVATE).edit()
                .putString("company", companyKey)
                .putString("pending_push_chat_url", chatUrl == null ? "" : chatUrl)
                .putString("pending_push_chat_id", chatId == null ? "" : chatId)
                .apply();

        Intent main = new Intent(this, MainActivity.class);
        main.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(main);
        finish();
    }
}
