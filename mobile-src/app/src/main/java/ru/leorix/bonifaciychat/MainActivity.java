package ru.leorix.bonifaciychat;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Message;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import java.text.SimpleDateFormat;
import java.util.Collections;
import java.util.Date;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public class MainActivity extends Activity {
    private static final int PICK_FILE = 501;
    private static final int REQ_NOTIFICATIONS = 502;
    private static final int REQ_STORAGE = 503;

    private static final String RK = "https://crm.leorix.ru";
    private static final String BOREY = "https://borey.crm.leorix.ru";
    private static final String CHANNEL_MESSAGES = "bonifaciy_chat_messages";

    private WebView web;
    private ProgressBar progress;
    private TextView company;
    private ValueCallback<Uri[]> fileCallback;
    private String base;
    private String companyName = "Бонифаций";
    private volatile boolean appInForeground = false;

    private final Set<Long> autoOpenDownloads = Collections.synchronizedSet(new HashSet<>());
    private final Map<Long, String> downloadNames = new ConcurrentHashMap<>();
    private BroadcastReceiver downloadReceiver;

    private String pendingDownloadUrl;
    private String pendingDownloadName;
    private boolean pendingDownloadOpen;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        createNotificationChannel();
        registerDownloadReceiver();
        buildUi();
        configureWeb();
        requestNotificationPermissionIfNeeded();

        String saved = getSharedPreferences("boni", MODE_PRIVATE).getString("company", "");
        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);
    }

    @Override
    protected void onResume() {
        super.onResume();
        appInForeground = true;
    }

    @Override
    protected void onPause() {
        appInForeground = false;
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        try {
            if (downloadReceiver != null) unregisterReceiver(downloadReceiver);
        } catch (Exception ignored) {
        }
        super.onDestroy();
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private Button barButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(21);
        b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.TRANSPARENT);
        b.setAllCaps(false);
        b.setMinWidth(0);
        b.setMinHeight(0);
        b.setPadding(0, 0, 0, 0);
        return b;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(11, 18, 32));

        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(4), 0, dp(4), 0);
        bar.setBackgroundColor(Color.rgb(17, 24, 39));
        root.addView(bar, new LinearLayout.LayoutParams(-1, dp(56)));

        Button dialogs = barButton("☰");
        dialogs.setContentDescription("Диалоги");
        dialogs.setOnClickListener(v -> web.evaluateJavascript(
                "window.__boniToggleDialogs&&window.__boniToggleDialogs()", null));
        bar.addView(dialogs, new LinearLayout.LayoutParams(dp(48), dp(48)));

        company = new TextView(this);
        company.setTextColor(Color.WHITE);
        company.setTextSize(15);
        company.setGravity(Gravity.CENTER_VERTICAL);
        company.setPadding(dp(10), 0, dp(8), 0);
        company.setSingleLine(true);
        company.setOnClickListener(v -> chooseCompany(false));
        bar.addView(company, new LinearLayout.LayoutParams(0, -1, 1f));

        Button reload = barButton("↻");
        reload.setContentDescription("Обновить");
        reload.setOnClickListener(v -> web.reload());
        bar.addView(reload, new LinearLayout.LayoutParams(dp(48), dp(48)));

        Button menu = barButton("⋮");
        menu.setContentDescription("Меню");
        menu.setOnClickListener(v -> showMenu());
        bar.addView(menu, new LinearLayout.LayoutParams(dp(48), dp(48)));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        root.addView(progress, new LinearLayout.LayoutParams(-1, dp(3)));

        web = new WebView(this);
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);
    }

    private void configureWeb() {
        CookieManager.getInstance().setAcceptCookie(true);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowContentAccess(true);
        s.setAllowFileAccess(false);
        s.setSupportZoom(false);
        s.setUseWideViewPort(false);
        s.setLoadWithOverviewMode(false);
        s.setTextZoom(100);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setUserAgentString(s.getUserAgentString() + " BonifaciyChatAndroid/2.0");
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);

        web.addJavascriptInterface(new AndroidBridge(), "BonifaciyAndroid");

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView v, int p) {
                progress.setProgress(p);
                progress.setVisibility(p >= 100 ? View.GONE : View.VISIBLE);
            }

            @Override
            public boolean onShowFileChooser(WebView w, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;

                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);

                if (params != null) {
                    String[] accepts = params.getAcceptTypes();
                    if (accepts != null && accepts.length == 1 && accepts[0] != null && !accepts[0].isBlank()) {
                        i.setType(accepts[0]);
                    } else if (accepts != null && accepts.length > 1) {
                        i.putExtra(Intent.EXTRA_MIME_TYPES, accepts);
                    }
                }

                try {
                    startActivityForResult(i, PICK_FILE);
                    return true;
                } catch (ActivityNotFoundException e) {
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, "Не найдено приложение для выбора файла", Toast.LENGTH_LONG).show();
                    return false;
                }
            }

            @Override
            public boolean onCreateWindow(WebView view, boolean isDialog, boolean isUserGesture, Message resultMsg) {
                WebView.HitTestResult hit = view.getHitTestResult();
                String url = hit == null ? null : hit.getExtra();
                if (url != null && !url.isBlank()) {
                    if (trustedAttachmentUri(url) != null) {
                        enqueueAttachment(url, "Вложение Бонифаций", true);
                    } else {
                        Uri uri = Uri.parse(url);
                        if (isTrustedPortalUri(uri)) view.loadUrl(url); else openExternal(uri);
                    }
                    return false;
                }
                return false;
            }
        });

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r) {
                Uri u = r.getUrl();
                if (trustedAttachmentUri(u.toString()) != null) {
                    enqueueAttachment(u.toString(), "Вложение Бонифаций", true);
                    return true;
                }
                if (isTrustedPortalUri(u)) return false;
                if ("http".equalsIgnoreCase(u.getScheme()) || "https".equalsIgnoreCase(u.getScheme())) {
                    openExternal(u);
                    return true;
                }
                return false;
            }

            @Override
            public void onPageFinished(WebView v, String url) {
                injectMobile();
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e) {
                if (r.isForMainFrame()) {
                    Toast.makeText(MainActivity.this, "Нет соединения. Нажмите ↻", Toast.LENGTH_LONG).show();
                }
            }
        });
    }

    private boolean isTrustedPortalUri(Uri uri) {
        if (uri == null || !"https".equalsIgnoreCase(uri.getScheme())) return false;
        String host = uri.getHost();
        if (host == null) return false;
        host = host.toLowerCase(Locale.ROOT);
        return "crm.leorix.ru".equals(host) || "borey.crm.leorix.ru".equals(host);
    }

    private Uri trustedAttachmentUri(String rawUrl) {
        try {
            Uri uri = Uri.parse(rawUrl);
            if (!isTrustedPortalUri(uri)) return null;
            String path = uri.getPath();
            if (path == null) return null;
            if (path.startsWith("/chat/attachments/") || path.startsWith("/chat/attachment")) return uri;
        } catch (Exception ignored) {
        }
        return null;
    }

    private void openExternal(Uri uri) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (Exception e) {
            Toast.makeText(this, "Не удалось открыть ссылку", Toast.LENGTH_SHORT).show();
        }
    }

    private void enqueueAttachment(String rawUrl, String suggestedName, boolean openAfterDownload) {
        Uri uri = trustedAttachmentUri(rawUrl);
        if (uri == null) {
            Toast.makeText(this, "Загрузка заблокирована: недоверенный адрес", Toast.LENGTH_LONG).show();
            return;
        }

        if (Build.VERSION.SDK_INT <= 28 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            pendingDownloadUrl = rawUrl;
            pendingDownloadName = suggestedName;
            pendingDownloadOpen = openAfterDownload;
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_STORAGE);
            return;
        }

        String safeName = uniqueDownloadName(sanitizeFileName(suggestedName));
        try {
            DownloadManager.Request request = new DownloadManager.Request(uri);
            request.setAllowedOverMetered(true);
            request.setAllowedOverRoaming(true);
            request.setTitle(safeName);
            request.setDescription("Бонифаций Чат");
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, safeName);

            String cookie = CookieManager.getInstance().getCookie(rawUrl);
            if (cookie != null && !cookie.isBlank()) request.addRequestHeader("Cookie", cookie);
            request.addRequestHeader("User-Agent", web.getSettings().getUserAgentString());
            request.addRequestHeader("Accept", "*/*");
            if (base != null) request.addRequestHeader("Referer", base + "/chat");

            DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            long id = dm.enqueue(request);
            downloadNames.put(id, safeName);
            if (openAfterDownload) autoOpenDownloads.add(id);

            Toast.makeText(this,
                    openAfterDownload ? "Загружаю файл для открытия…" : "Файл загружается в Downloads",
                    Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Не удалось загрузить файл", Toast.LENGTH_LONG).show();
        }
    }

    private String sanitizeFileName(String raw) {
        String name = raw == null ? "" : raw.trim();
        name = name.replace("📎", "").replace("⬇", "").replace("Скачать", "").replace("Открыть", "").trim();
        name = name.replaceAll("[\\\\/:*?\"<>|\\r\\n]+", "_");
        name = name.replaceAll("\\s+", " ").trim();
        if (name.isEmpty() || name.length() > 120) name = "Вложение_Бонифаций";
        if (name.length() > 120) name = name.substring(0, 120);
        return name;
    }

    private String uniqueDownloadName(String name) {
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.ROOT).format(new Date());
        int dot = name.lastIndexOf('.');
        if (dot > 0 && dot < name.length() - 1) {
            return name.substring(0, dot) + "_" + stamp + name.substring(dot);
        }
        return name + "_" + stamp;
    }

    private void registerDownloadReceiver() {
        downloadReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                if (!DownloadManager.ACTION_DOWNLOAD_COMPLETE.equals(intent.getAction())) return;
                long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
                if (id < 0) return;
                String name = downloadNames.remove(id);
                boolean shouldOpen = autoOpenDownloads.remove(id);
                if (shouldOpen) openDownloadedFile(id, name);
            }
        };

        IntentFilter filter = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(downloadReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(downloadReceiver, filter);
        }
    }

    private void openDownloadedFile(long id, String name) {
        DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        Uri localUri = dm.getUriForDownloadedFile(id);
        if (localUri == null) {
            Toast.makeText(this, "Файл не удалось открыть после загрузки", Toast.LENGTH_LONG).show();
            return;
        }

        String mime = dm.getMimeTypeForDownloadedFile(id);
        if (mime == null || mime.isBlank()) mime = mimeFromName(name);
        if (mime == null || mime.isBlank()) mime = "*/*";

        Intent view = new Intent(Intent.ACTION_VIEW);
        view.setDataAndType(localUri, mime);
        view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(view);
        } catch (ActivityNotFoundException e) {
            try {
                Intent fallback = new Intent(Intent.ACTION_VIEW);
                fallback.setDataAndType(localUri, "*/*");
                fallback.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(fallback);
            } catch (Exception ignored) {
                Toast.makeText(this,
                        "Файл сохранён в Downloads, но на телефоне нет приложения для его открытия",
                        Toast.LENGTH_LONG).show();
            }
        }
    }

    private String mimeFromName(String name) {
        if (name == null) return null;
        int dot = name.lastIndexOf('.');
        if (dot < 0 || dot == name.length() - 1) return null;
        String ext = name.substring(dot + 1).toLowerCase(Locale.ROOT);
        String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        if (mime != null) return mime;
        switch (ext) {
            case "doc": return "application/msword";
            case "docx": return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
            case "xls": return "application/vnd.ms-excel";
            case "xlsx": return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
            case "pdf": return "application/pdf";
            case "csv": return "text/csv";
            default: return null;
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_MESSAGES,
                "Сообщения Бонифация",
                NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("Новые сообщения рабочего чата Бонифаций");
        channel.enableVibration(true);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(channel);
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATIONS);
        }
    }

    private void showMessageNotification(String author) {
        if (appInForeground) return;
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return;

        String cleanAuthor = author == null ? "" : author.trim();
        String text = cleanAuthor.isEmpty() ? "Новое сообщение" : "Новое сообщение от " + cleanAuthor;

        Intent launch = new Intent(this, MainActivity.class);
        launch.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pending = PendingIntent.getActivity(
                this,
                0,
                launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_MESSAGES)
                : new Notification.Builder(this);

        builder.setSmallIcon(R.drawable.ic_notification)
                .setContentTitle("Бонифаций · " + companyName)
                .setContentText(text)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setContentIntent(pending);

        if (Build.VERSION.SDK_INT < 26) {
            builder.setPriority(Notification.PRIORITY_HIGH);
        }

        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.notify((int) (System.currentTimeMillis() & 0x7fffffff), builder.build());
    }

    private void injectMobile() {
        String css = "html,body{width:100%!important;max-width:100%!important;overflow-x:hidden!important;-webkit-text-size-adjust:100%!important}" +
                "body.boniapp .topbar,body.boniapp .app-drawer,body.boniapp .drawer-backdrop,body.boniapp .split-header{display:none!important}" +
                "body.boniapp .main,body.boniapp main.main{width:100%!important;max-width:none!important;margin:0!important;padding:0!important}" +
                "body.boniapp #chat-layout-root{display:block!important;width:100%!important;max-width:none!important;height:100dvh!important;min-height:0!important;margin:0!important;padding:0!important;border:0!important;overflow:hidden!important}" +
                "body.boniapp .chat-reset-main{display:flex!important;flex-direction:column!important;height:100dvh!important;min-height:0!important;padding:0 7px 7px!important;box-sizing:border-box!important}" +
                "body.boniapp .chat-reset-header{flex:0 0 auto!important;min-height:45px!important;padding:7px 5px!important}body.boniapp .chat-reset-header .muted.small{display:none!important}" +
                "body.boniapp .chat-reset-feed-region{flex:1 1 auto!important;min-height:0!important;height:auto!important;overflow:hidden!important}body.boniapp #chat-box{height:100%!important;max-height:none!important;overflow-y:auto!important;padding:7px 2px 12px!important}" +
                "body.boniapp .chat-message{max-width:92%!important;font-size:15px!important;line-height:1.38!important;padding:9px 11px!important;border-radius:16px!important;overflow-wrap:anywhere!important}" +
                "body.boniapp #chat-form{flex:0 0 auto!important;margin:0!important}body.boniapp .chat-reset-composer{padding:7px!important;border-radius:16px!important}" +
                "body.boniapp #chat-message{width:100%!important;min-height:48px!important;max-height:120px!important;font-size:16px!important;padding:11px!important;border-radius:14px!important;box-sizing:border-box!important}" +
                "body.boniapp .chat-reset-actions{display:flex!important;gap:5px!important;flex-wrap:nowrap!important}body.boniapp .chat-reset-actions button,body.boniapp .chat-reset-actions .file-btn,body.boniapp .chat-send-btn{min-height:44px!important;min-width:44px!important;border-radius:12px!important}" +
                "body.boniapp .chat-reset-sidebar{position:fixed!important;z-index:1000!important;left:0!important;top:0!important;bottom:0!important;width:min(88vw,390px)!important;height:100dvh!important;overflow:auto!important;padding:10px!important;background:#111827!important;box-shadow:16px 0 40px rgba(0,0,0,.4)!important;transform:translateX(-105%)!important;transition:transform .18s ease!important}" +
                "body.boniapp.dialogs .chat-reset-sidebar{transform:translateX(0)!important}body.boniapp .chat-reset-dialog-item{min-height:56px!important;border-radius:13px!important}body.boniapp .chat-dialog-search-v176a input{min-height:46px!important;font-size:16px!important}" +
                "body.boniapp .auth-card{width:calc(100vw - 24px)!important;max-width:520px!important;margin:20px auto!important;padding:18px 15px!important;box-sizing:border-box!important}body.boniapp .auth-card input,body.boniapp .auth-card button{min-height:50px!important;font-size:16px!important;border-radius:13px!important}" +
                "body.boniapp a[data-boni-android-attachment='1']{display:inline-flex!important;align-items:center!important;min-height:42px!important;max-width:100%!important;overflow-wrap:anywhere!important}" +
                "body.boniapp .boni-native-download{display:inline-flex!important;align-items:center!important;justify-content:center!important;min-height:40px!important;margin:4px 0 4px 6px!important;padding:7px 10px!important;border-radius:11px!important;font-size:13px!important}";

        String js = "document.body.classList.add('boniapp');" +
                "var m=document.querySelector('meta[name=viewport]');if(!m){m=document.createElement('meta');m.name='viewport';document.head.appendChild(m)}m.content='width=device-width,initial-scale=1,viewport-fit=cover';" +
                "window.__boniToggleDialogs=function(){document.body.classList.toggle('dialogs')};" +
                "var s=document.getElementById('boniappcss');if(!s){s=document.createElement('style');s.id='boniappcss';document.head.appendChild(s)}s.textContent=" + quote(css) + ";" +
                "var bridge=window.BonifaciyAndroid;" +
                "function boniTrustedAttachment(a){try{var u=new URL(a.href,location.origin);return u.protocol==='https:'&&(u.hostname==='crm.leorix.ru'||u.hostname==='borey.crm.leorix.ru')&&(u.pathname.indexOf('/chat/attachments/')===0||u.pathname.indexOf('/chat/attachment')===0)}catch(e){return false}}" +
                "function boniName(a){var t=(a.textContent||'').replace(/📎/g,'').trim();return t||'Вложение Бонифаций'}" +
                "function boniWireAttachment(a){if(!bridge||!boniTrustedAttachment(a)||a.dataset.boniAndroidAttachment==='1')return;a.dataset.boniAndroidAttachment='1';a.removeAttribute('target');a.addEventListener('click',function(e){e.preventDefault();bridge.openAttachment(a.href,boniName(a))},true);var b=document.createElement('button');b.type='button';b.className='boni-native-download';b.textContent='⬇ Скачать';b.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();bridge.downloadAttachment(a.href,boniName(a))});a.insertAdjacentElement('afterend',b)}" +
                "function boniWireAll(root){var r=root&&root.querySelectorAll?root:document;r.querySelectorAll('a[href]').forEach(boniWireAttachment)}" +
                "boniWireAll(document);" +
                "var wireObserver=new MutationObserver(function(ms){ms.forEach(function(mu){mu.addedNodes.forEach(function(n){if(n.nodeType===1){if(n.matches&&n.matches('a[href]'))boniWireAttachment(n);boniWireAll(n)}})})});wireObserver.observe(document.body,{childList:true,subtree:true});" +
                "var f=document.getElementById('chat-box');if(f){setTimeout(function(){f.scrollTop=f.scrollHeight},150);var seen=new Set();f.querySelectorAll('[data-message-id]').forEach(function(n){var id=n.getAttribute('data-message-id');if(id)seen.add(id)});" +
                "function boniMaybeNotify(n){if(!bridge||!n||n.nodeType!==1)return;var nodes=[];if(n.matches&&n.matches('[data-message-id]'))nodes.push(n);if(n.querySelectorAll)n.querySelectorAll('[data-message-id]').forEach(function(x){nodes.push(x)});nodes.forEach(function(x){var id=x.getAttribute('data-message-id');if(!id||seen.has(id))return;seen.add(id);var an=x.querySelector('.compact-chat-author strong,.chat-message-author strong,.chat-author strong');var author=an?(an.textContent||'').trim():'';bridge.notifyNewMessage(author,id)})}" +
                "var msgObserver=new MutationObserver(function(ms){ms.forEach(function(mu){mu.addedNodes.forEach(boniMaybeNotify)})});msgObserver.observe(f,{childList:true,subtree:true});}";

        web.evaluateJavascript("(function(){" + js + "})()", null);
    }

    private String quote(String x) {
        return "'" + x.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ") + "'";
    }

    private void chooseCompany(boolean first) {
        String[] x = {"РК-ТЕХНИКА\ncrm.leorix.ru", "НПО БОРЕЙ\nborey.crm.leorix.ru"};
        AlertDialog d = new AlertDialog.Builder(this)
                .setTitle("Выберите компанию")
                .setItems(x, (q, w) -> setCompany(w == 1 ? "borey" : "rk", true))
                .create();
        d.setCancelable(!first);
        d.setCanceledOnTouchOutside(!first);
        d.show();
    }

    private void setCompany(String key, boolean load) {
        boolean b = "borey".equals(key);
        base = b ? BOREY : RK;
        companyName = b ? "НПО БОРЕЙ" : "РК-ТЕХНИКА";
        company.setText(companyName + "  ▾");
        getSharedPreferences("boni", MODE_PRIVATE).edit().putString("company", b ? "borey" : "rk").apply();
        if (load) web.loadUrl(base + "/chat");
    }

    private void showMenu() {
        new AlertDialog.Builder(this)
                .setItems(new String[]{"Сменить компанию", "Открыть портал", "Настройки уведомлений", "Выйти из аккаунта", "Очистить сессию"}, (d, w) -> {
                    if (w == 0) {
                        chooseCompany(false);
                    } else if (w == 1) {
                        try {
                            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(base)));
                        } catch (Exception ignored) {
                        }
                    } else if (w == 2) {
                        openNotificationSettings();
                    } else if (w == 3) {
                        web.loadUrl(base + "/logout");
                    } else {
                        CookieManager.getInstance().removeAllCookies(ok -> {
                            CookieManager.getInstance().flush();
                            web.clearCache(true);
                            web.loadUrl(base + "/chat");
                        });
                    }
                }).show();
    }

    private void openNotificationSettings() {
        try {
            Intent i = new Intent();
            if (Build.VERSION.SDK_INT >= 26) {
                i.setAction("android.settings.CHANNEL_NOTIFICATION_SETTINGS");
                i.putExtra("android.provider.extra.APP_PACKAGE", getPackageName());
                i.putExtra("android.provider.extra.CHANNEL_ID", CHANNEL_MESSAGES);
            } else {
                i.setAction("android.settings.APP_NOTIFICATION_SETTINGS");
                i.putExtra("app_package", getPackageName());
                i.putExtra("app_uid", getApplicationInfo().uid);
            }
            startActivity(i);
        } catch (Exception e) {
            Toast.makeText(this, "Не удалось открыть настройки уведомлений", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onBackPressed() {
        web.evaluateJavascript("document.body&&document.body.classList.contains('dialogs')", v -> {
            if ("true".equals(v)) {
                web.evaluateJavascript("document.body.classList.remove('dialogs')", null);
            } else if (web.canGoBack()) {
                web.goBack();
            } else {
                super.onBackPressed();
            }
        });
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        if (request == PICK_FILE) {
            Uri[] out = null;
            if (result == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int n = data.getClipData().getItemCount();
                    out = new Uri[n];
                    for (int i = 0; i < n; i++) out[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) {
                    out = new Uri[]{data.getData()};
                }
            }
            if (fileCallback != null) {
                fileCallback.onReceiveValue(out);
                fileCallback = null;
            }
            return;
        }
        super.onActivityResult(request, result, data);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_STORAGE && grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            String url = pendingDownloadUrl;
            String name = pendingDownloadName;
            boolean open = pendingDownloadOpen;
            pendingDownloadUrl = null;
            pendingDownloadName = null;
            if (url != null) enqueueAttachment(url, name, open);
        }
    }

    private final class AndroidBridge {
        @JavascriptInterface
        public void openAttachment(String url, String name) {
            runOnUiThread(() -> enqueueAttachment(url, name, true));
        }

        @JavascriptInterface
        public void downloadAttachment(String url, String name) {
            runOnUiThread(() -> enqueueAttachment(url, name, false));
        }

        @JavascriptInterface
        public void notifyNewMessage(String author, String messageId) {
            if (!appInForeground) runOnUiThread(() -> showMessageNotification(author));
        }
    }
}
