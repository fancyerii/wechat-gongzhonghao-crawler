package com.github.fancyerii.wechatcrawler.server.service;

import com.antbrains.httpclientfetcher.HttpClientFetcher;
import com.antbrains.mysqltool.PoolManager;
import com.github.fancyerii.wechatcrawler.server.data.Counter;
import com.github.fancyerii.wechatcrawler.server.data.MysqlArchiver;
import com.github.fancyerii.wechatcrawler.server.data.State;
import com.github.fancyerii.wechatcrawler.server.data.WebPage;
import com.github.fancyerii.wechatcrawler.server.tool.ConfigReader;
import com.github.fancyerii.wechatcrawler.server.tool.MyDateTypeAdapter;
import com.github.fancyerii.wechatcrawler.server.tool.Tool;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import lombok.extern.slf4j.Slf4j;

import javax.crypto.SecretKey;
import javax.crypto.spec.IvParameterSpec;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

@Slf4j
public class PageAndCounterSyncer implements Runnable {
    private MysqlArchiver archiver;
    private int pageSize = 20;
    private int counterSize = 200;
    private long crawlInterval = 3000;
    private long failInterval = 5 * 60 * 1000L;
    private long emptySleep = 60 * 1000L;
    private Gson gson;
    private JsonParser jp = new JsonParser();
    private SecretKey key;
    private IvParameterSpec ivParameterSpec;
    private HttpClientFetcher fetcher;
    private String serverUrl;
    private String wechatId;

    public PageAndCounterSyncer(MysqlArchiver archiver) throws Exception {
        this.archiver = archiver;
        wechatId = ConfigReader.getProp("wechat_id");
        String pass = ConfigReader.getProp("enc_pass");
        String salt = ConfigReader.getProp("salt");
        String iv = ConfigReader.getProp("iv");
        serverUrl = ConfigReader.getProp("server_url");
        key = Tool.getKeyFromPassword(pass, salt);
        ivParameterSpec = Tool.getIvFromBase64(iv);
        fetcher = new HttpClientFetcher(WebContentCrawler.class.getName());

        fetcher.init();
        gson = new GsonBuilder().registerTypeAdapter(Date.class, new MyDateTypeAdapter()).create();
    }

    String algorithm = "AES/CBC/PKCS5Padding";

    private String encPages(List<WebPage> pages) throws Exception {
        String s = gson.toJson(pages);

        String cipherText = Tool.encrypt(algorithm, s, key, ivParameterSpec);

        return cipherText;
    }

    private String encCounters(List<Counter> counters) throws Exception {
        String s = gson.toJson(counters);

        String cipherText = Tool.encrypt(algorithm, s, key, ivParameterSpec);

        return cipherText;
    }

    private int syncCounters() {
        List<State> states = new ArrayList<>(0);
        try {
            states = archiver.getNeedSyncCounters(counterSize);
        } catch (SQLException e) {
            log.error(e.getMessage(), e);
        }
        List<Integer> ids = new ArrayList<>(states.size());
        for (State state : states) {
            ids.add(state.getId());
        }
        List<Counter> counters = archiver.getCounters(ids);
        if (!counters.isEmpty()) {
            boolean syncSuccess = false;
            try {
                String s = this.encCounters(counters);
                String rsp = null;
                String url = serverUrl + "/synccounters?wechatId=" +
                        java.net.URLEncoder.encode(wechatId, "UTF-8");
                rsp = fetcher.httpPost(url
                        , s, null);
                JsonObject jo = jp.parse(rsp).getAsJsonObject();
                syncSuccess = jo.get("success").getAsBoolean();
                if (syncSuccess) {
                    archiver.updateSyncedCounters(ids);
                } else {
                    log.error(rsp);
                }
            } catch (Exception e) {
                log.error(e.getMessage(), e);
                try {
                    Thread.sleep(this.failInterval);
                } catch (InterruptedException ex) {
                }
                return 0;
            }

        }


        return counters.size();
    }

    private String syncDebugInfo(String lastInfo) {
        String info;
        try {
            info = archiver.getDebugInfo(wechatId);
        } catch (SQLException e) {
            log.error(e.getMessage(), e);
            return null;
        }
        if (info == null) return null;
        if (info.equals(lastInfo)) return info;
        try {
            String url = serverUrl + "/adddebuginfo?wechatId=" +
                    java.net.URLEncoder.encode(wechatId, "UTF-8");
            String rsp = fetcher.httpPost(url
                    , info, null);

        } catch (Exception e) {
            log.error(e.getMessage(), e);
            return null;
        }
        return info;

    }


    private int syncPages() {
        List<State> states = new ArrayList<>(0);
        try {
            states = archiver.getNeedSyncPages(pageSize);
        } catch (SQLException e) {
            log.error(e.getMessage(), e);
        }
        List<Integer> ids = new ArrayList<>(states.size());
        for (State state : states) {
            ids.add(state.getId());
        }
        List<WebPage> pages = archiver.getWebPages(ids);
        if (!pages.isEmpty()) {
            boolean syncSuccess = false;
            try {
                String s = this.encPages(pages);
                String rsp = null;

                String url = serverUrl + "/syncpages?wechatId=" +
                        java.net.URLEncoder.encode(wechatId, "UTF-8");
                rsp = fetcher.httpPost(url
                        , s, null);

                JsonObject jo = jp.parse(rsp).getAsJsonObject();
                syncSuccess = jo.get("success").getAsBoolean();
                if (syncSuccess) {
                    archiver.updateSyncedPages(ids);
                } else {
                    log.error(rsp);
                }
            } catch (Exception e) {
                log.error(e.getMessage(), e);
                try {
                    Thread.sleep(this.failInterval);
                } catch (InterruptedException ex) {
                }
                return 0;
            }

        }


        return pages.size();
    }

    @Override
    public void run() {
        long lastUpdateDebugTime = 0;
        String lastInfo = null;
        while (true) {
            int syncPages = this.syncPages();

            int syncCounter = this.syncCounters();

            if (syncPages == 0 && syncCounter == 0) {
                try {
                    Thread.sleep(emptySleep);
                } catch (InterruptedException e) {

                }
            } else {
                log.info("syncPages: {}, syncCounter: {}", syncPages, syncCounter);
            }

            if (System.currentTimeMillis() - lastUpdateDebugTime > 1 * 60 * 1000L) {
                lastInfo = syncDebugInfo(lastInfo);
                lastUpdateDebugTime = System.currentTimeMillis();
            }
        }
    }

    public static void main(String[] args) throws Exception {
        PoolManager.StartPool("conf", "wechat");
        MysqlArchiver archiver = new MysqlArchiver();
        new Thread(new PageAndCounterSyncer(archiver)).start();
    }

}
