package ru.leorix.bonifaciychat;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
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

public class MainActivity extends Activity {
    private static final int PICK_FILE = 501;
    private static final String RK = "https://crm.leorix.ru";
    private static final String BOREY = "https://borey.crm.leorix.ru";
    private WebView web;
    private ProgressBar progress;
    private TextView company;
    private ValueCallback<Uri[]> fileCallback;
    private String base;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        buildUi();
        configureWeb();
        String saved = getSharedPreferences("boni", MODE_PRIVATE).getString("company", "");
        if (saved.isEmpty()) chooseCompany(true); else setCompany(saved, true);
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private Button barButton(String text) {
        Button b = new Button(this);
        b.setText(text); b.setTextSize(21); b.setTextColor(Color.WHITE);
        b.setBackgroundColor(Color.TRANSPARENT); b.setAllCaps(false);
        b.setMinWidth(0); b.setMinHeight(0); b.setPadding(0,0,0,0);
        return b;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(11,18,32));
        LinearLayout bar = new LinearLayout(this); bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(4),0,dp(4),0); bar.setBackgroundColor(Color.rgb(17,24,39));
        root.addView(bar, new LinearLayout.LayoutParams(-1, dp(56)));

        Button dialogs = barButton("☰");
        dialogs.setContentDescription("Диалоги");
        dialogs.setOnClickListener(v -> web.evaluateJavascript("window.__boniToggleDialogs&&window.__boniToggleDialogs()", null));
        bar.addView(dialogs, new LinearLayout.LayoutParams(dp(48),dp(48)));

        company = new TextView(this); company.setTextColor(Color.WHITE); company.setTextSize(15);
        company.setGravity(Gravity.CENTER_VERTICAL); company.setPadding(dp(10),0,dp(8),0); company.setSingleLine(true);
        company.setOnClickListener(v -> chooseCompany(false));
        bar.addView(company, new LinearLayout.LayoutParams(0,-1,1f));

        Button reload = barButton("↻"); reload.setOnClickListener(v -> web.reload());
        bar.addView(reload, new LinearLayout.LayoutParams(dp(48),dp(48)));
        Button menu = barButton("⋮"); menu.setOnClickListener(v -> showMenu());
        bar.addView(menu, new LinearLayout.LayoutParams(dp(48),dp(48)));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal); progress.setMax(100);
        root.addView(progress, new LinearLayout.LayoutParams(-1,dp(3)));
        web = new WebView(this); root.addView(web, new LinearLayout.LayoutParams(-1,0,1f));
        setContentView(root);
    }

    private void configureWeb() {
        CookieManager.getInstance().setAcceptCookie(true);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true); s.setDomStorageEnabled(true); s.setDatabaseEnabled(true);
        s.setAllowContentAccess(true); s.setAllowFileAccess(false); s.setSupportZoom(false);
        s.setUseWideViewPort(false); s.setLoadWithOverviewMode(false); s.setTextZoom(100);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setUserAgentString(s.getUserAgentString()+" BonifaciyChatAndroid/1.0");
        CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);

        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onProgressChanged(WebView v,int p){ progress.setProgress(p); progress.setVisibility(p>=100?View.GONE:View.VISIBLE); }
            @Override public boolean onShowFileChooser(WebView w, ValueCallback<Uri[]> cb, FileChooserParams params){
                if(fileCallback!=null) fileCallback.onReceiveValue(null); fileCallback=cb;
                Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT); i.addCategory(Intent.CATEGORY_OPENABLE); i.setType("*/*"); i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);
                try { startActivityForResult(i,PICK_FILE); return true; }
                catch(ActivityNotFoundException e){ fileCallback=null; Toast.makeText(MainActivity.this,"Не найден выбор файлов",Toast.LENGTH_LONG).show(); return false; }
            }
        });

        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest r){
                Uri u=r.getUrl(); String h=u.getHost()==null?"":u.getHost().toLowerCase();
                if(h.equals("crm.leorix.ru")||h.equals("borey.crm.leorix.ru")) return false;
                if("http".equals(u.getScheme())||"https".equals(u.getScheme())) { try{startActivity(new Intent(Intent.ACTION_VIEW,u));}catch(Exception ignored){} return true; }
                return false;
            }
            @Override public void onPageFinished(WebView v,String url){ injectMobile(); }
            @Override public void onReceivedError(WebView v, WebResourceRequest r, WebResourceError e){ if(r.isForMainFrame()) Toast.makeText(MainActivity.this,"Нет соединения. Нажмите ↻",Toast.LENGTH_LONG).show(); }
        });
    }

    private void injectMobile(){
        String css="html,body{width:100%!important;max-width:100%!important;overflow-x:hidden!important;-webkit-text-size-adjust:100%!important}"+
        "body.boniapp .topbar,body.boniapp .app-drawer,body.boniapp .drawer-backdrop,body.boniapp .split-header{display:none!important}"+
        "body.boniapp .main,body.boniapp main.main{width:100%!important;max-width:none!important;margin:0!important;padding:0!important}"+
        "body.boniapp #chat-layout-root{display:block!important;width:100%!important;max-width:none!important;height:100dvh!important;min-height:0!important;margin:0!important;padding:0!important;border:0!important;overflow:hidden!important}"+
        "body.boniapp .chat-reset-main{display:flex!important;flex-direction:column!important;height:100dvh!important;min-height:0!important;padding:0 7px 7px!important;box-sizing:border-box!important}"+
        "body.boniapp .chat-reset-header{flex:0 0 auto!important;min-height:45px!important;padding:7px 5px!important}body.boniapp .chat-reset-header .muted.small{display:none!important}"+
        "body.boniapp .chat-reset-feed-region{flex:1 1 auto!important;min-height:0!important;height:auto!important;overflow:hidden!important}body.boniapp #chat-box{height:100%!important;max-height:none!important;overflow-y:auto!important;padding:7px 2px 12px!important}"+
        "body.boniapp .chat-message{max-width:92%!important;font-size:15px!important;line-height:1.38!important;padding:9px 11px!important;border-radius:16px!important;overflow-wrap:anywhere!important}"+
        "body.boniapp #chat-form{flex:0 0 auto!important;margin:0!important}body.boniapp .chat-reset-composer{padding:7px!important;border-radius:16px!important}"+
        "body.boniapp #chat-message{width:100%!important;min-height:48px!important;max-height:120px!important;font-size:16px!important;padding:11px!important;border-radius:14px!important;box-sizing:border-box!important}"+
        "body.boniapp .chat-reset-actions{display:flex!important;gap:5px!important;flex-wrap:nowrap!important}body.boniapp .chat-reset-actions button,body.boniapp .chat-reset-actions .file-btn,body.boniapp .chat-send-btn{min-height:44px!important;min-width:44px!important;border-radius:12px!important}"+
        "body.boniapp .chat-reset-sidebar{position:fixed!important;z-index:1000!important;left:0!important;top:0!important;bottom:0!important;width:min(88vw,390px)!important;height:100dvh!important;overflow:auto!important;padding:10px!important;background:#111827!important;box-shadow:16px 0 40px rgba(0,0,0,.4)!important;transform:translateX(-105%)!important;transition:transform .18s ease!important}"+
        "body.boniapp.dialogs .chat-reset-sidebar{transform:translateX(0)!important}body.boniapp .chat-reset-dialog-item{min-height:56px!important;border-radius:13px!important}body.boniapp .chat-dialog-search-v176a input{min-height:46px!important;font-size:16px!important}"+
        "body.boniapp .auth-card{width:calc(100vw - 24px)!important;max-width:520px!important;margin:20px auto!important;padding:18px 15px!important;box-sizing:border-box!important}body.boniapp .auth-card input,body.boniapp .auth-card button{min-height:50px!important;font-size:16px!important;border-radius:13px!important}";
        String js="document.body.classList.add('boniapp');var m=document.querySelector('meta[name=viewport]');if(!m){m=document.createElement('meta');m.name='viewport';document.head.appendChild(m)}m.content='width=device-width,initial-scale=1,viewport-fit=cover';window.__boniToggleDialogs=function(){document.body.classList.toggle('dialogs')};var s=document.getElementById('boniappcss');if(!s){s=document.createElement('style');s.id='boniappcss';document.head.appendChild(s)}s.textContent="+quote(css)+";var f=document.getElementById('chat-box');if(f)setTimeout(function(){f.scrollTop=f.scrollHeight},150);";
        web.evaluateJavascript("(function(){"+js+"})()",null);
    }

    private String quote(String x){ return "'"+x.replace("\\","\\\\").replace("'","\\'").replace("\n"," ")+"'"; }

    private void chooseCompany(boolean first){
        String[] x={"РК-ТЕХНИКА\ncrm.leorix.ru","НПО БОРЕЙ\nborey.crm.leorix.ru"};
        AlertDialog d=new AlertDialog.Builder(this).setTitle("Выберите компанию").setItems(x,(q,w)->setCompany(w==1?"borey":"rk",true)).create();
        d.setCancelable(!first); d.setCanceledOnTouchOutside(!first); d.show();
    }

    private void setCompany(String key, boolean load){
        boolean b="borey".equals(key); base=b?BOREY:RK; company.setText((b?"НПО БОРЕЙ":"РК-ТЕХНИКА")+"  ▾");
        getSharedPreferences("boni",MODE_PRIVATE).edit().putString("company",b?"borey":"rk").apply();
        if(load) web.loadUrl(base+"/chat");
    }

    private void showMenu(){
        new AlertDialog.Builder(this).setItems(new String[]{"Сменить компанию","Открыть портал","Выйти из аккаунта","Очистить сессию"},(d,w)->{
            if(w==0) chooseCompany(false);
            else if(w==1) { try{startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(base)));}catch(Exception ignored){} }
            else if(w==2) web.loadUrl(base+"/logout");
            else CookieManager.getInstance().removeAllCookies(ok->{CookieManager.getInstance().flush();web.clearCache(true);web.loadUrl(base+"/chat");});
        }).show();
    }

    @Override public void onBackPressed(){
        web.evaluateJavascript("document.body&&document.body.classList.contains('dialogs')",v->{
            if("true".equals(v)) web.evaluateJavascript("document.body.classList.remove('dialogs')",null);
            else if(web.canGoBack()) web.goBack(); else super.onBackPressed();
        });
    }

    @Override protected void onActivityResult(int request,int result,Intent data){
        if(request==PICK_FILE){
            Uri[] out=null;
            if(result==RESULT_OK&&data!=null){
                if(data.getClipData()!=null){ int n=data.getClipData().getItemCount(); out=new Uri[n]; for(int i=0;i<n;i++) out[i]=data.getClipData().getItemAt(i).getUri(); }
                else if(data.getData()!=null) out=new Uri[]{data.getData()};
            }
            if(fileCallback!=null){fileCallback.onReceiveValue(out);fileCallback=null;} return;
        }
        super.onActivityResult(request,result,data);
    }
}
