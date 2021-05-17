package com.github.fancyerii.wechatcrawler.server.service;

import com.antbrains.mysqltool.PoolManager;
import com.github.fancyerii.wechatcrawler.server.data.Counter;
import com.github.fancyerii.wechatcrawler.server.data.MysqlArchiver;
import com.github.fancyerii.wechatcrawler.server.data.WebPage;
import com.github.fancyerii.wechatcrawler.server.tool.ConfigReader;
import com.github.fancyerii.wechatcrawler.server.tool.MyDateTypeAdapter;
import com.github.fancyerii.wechatcrawler.server.tool.Tool;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import lombok.extern.slf4j.Slf4j;
import spark.Route;

import javax.crypto.SecretKey;
import javax.crypto.spec.IvParameterSpec;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import static spark.Spark.*;

@Slf4j
public class WechatSyncServer {
    private ConcurrentHashMap<String, SecretKey> keyMap;
    private IvParameterSpec ivParameterSpec;

    private MysqlArchiver archiver;
    private String salt;
    String algorithm = "AES/CBC/PKCS5Padding";
    private String clearPass;
    private ConcurrentHashMap<String, String> debugInfoMap;
    public WechatSyncServer(MysqlArchiver archiver) throws Exception{
        salt=ConfigReader.getProp("salt");
        String iv=ConfigReader.getProp("iv");
        clearPass=ConfigReader.getProp("clear_pass");
        ivParameterSpec = Tool.getIvFromBase64(iv);
        keyMap=new ConcurrentHashMap<>();
        debugInfoMap = new ConcurrentHashMap<>();
        this.archiver=archiver;
    }

    public void addDebugInfo(String key, String value){
        debugInfoMap.put(key, value);
    }

    public String getDebugInfo(String key){
        return debugInfoMap.get(key);
    }

    public boolean clearPassMatch(String pass){
        return clearPass.equals(pass);
    }

    public void clearAllPasses(){
        keyMap.clear();
    }

    public String decypt(String wechatId, String text) throws Exception{
        SecretKey key = getKey(wechatId);
        if(key==null) throw new RuntimeException("weichatId未注册，请联系管理员");
        return Tool.decrypt(algorithm, text, key, ivParameterSpec);
    }

    private SecretKey getKey(String wechatId) throws Exception {
        SecretKey key=keyMap.get(wechatId);
        if(key!=null) return key;
        String pass=archiver.getWechatPass(wechatId);
        if(pass == null) return null;
        key=Tool.getKeyFromPassword(pass, salt);
        keyMap.put(wechatId, key);
        return key;
    }

    public static void main(String[] args) throws Exception {
        PoolManager.StartPool("conf","wechat");
        MysqlArchiver archiver=new MysqlArchiver();
        WechatSyncServer server=new WechatSyncServer(archiver);
        port(7654);
        staticFiles.location("/public");

        //get("/searchview", searchView(ts), new ThymeleafTemplateEngine());
        post("/syncpages", "application/json", syncPages(archiver, server), gson::toJson);
        post("/synccounters", "application/json", syncCounters(archiver, server), gson::toJson);
        post("/adddebuginfo", "application/json", addDebugInfo(archiver, server), gson::toJson);
        get("/clearpass", "application/json", clearPass(archiver, server), gson::toJson);
        get("/getdebuginfo", "text/plain", getDebugInfo(archiver, server));


    }

    static Gson gson=new GsonBuilder().registerTypeAdapter(Date.class, new MyDateTypeAdapter()).create();

    private static Route syncPages(final MysqlArchiver archiver, final WechatSyncServer server){
        return (request, response) -> {
            Map<String,Object> result=new HashMap<>();
            String body=request.body();
            try {
                String wechatId=request.queryParams("wechatId");
                if(Tool.isEmpty(wechatId)){
                    result.put("success", false);
                    result.put("msg", "wechatId不能空");
                    return result;
                }
                List<WebPage> pages=null;
                try {
                    body = server.decypt(wechatId, body);
                    pages = gson.fromJson(body, new TypeToken<List<WebPage>>(){}.getType());

                    for(WebPage page:pages){
                        if(!page.getCrawlWechatId().equals(wechatId)){
                            result.put("msg", "上传者"+wechatId+" 和网页抓取者不匹配");
                            result.put("success", false);
                            return result;
                        }
                    }
                }catch(Exception e){
                    //log.error(e.getMessage(), e);
                    result.put("msg", "无法解密文本，请联系管理员："+e.getMessage());
                    result.put("success", false);
                    return result;
                }
                for(WebPage page:pages){
                    archiver.upsertAllWebPages(page);
                }
                result.put("success", true);
            }catch(Exception e){
                log.error(e.getMessage(), e);
                result.put("msg", e.getMessage());
                result.put("success", false);
            }
            return result;
        };
    }

    private static Route clearPass(final MysqlArchiver archiver, final WechatSyncServer server){
        return (request, response) -> {
            Map<String,Object> result=new HashMap<>();

            try {
                String pass=request.queryParams("pass");
                if(!server.clearPassMatch(pass)){
                    result.put("success", false);
                    result.put("msg", "密码错误");
                    result.put("pass", pass);
                    return result;
                }
                server.clearAllPasses();
                result.put("success", true);
            }catch(Exception e){
                result.put("msg", e.getMessage());
                result.put("success", false);
            }
            return result;
        };
    }

    private static Route getDebugInfo(final MysqlArchiver archiver, final WechatSyncServer server) {
        return (request, response) -> {
            String key=request.queryParams("wechatId");
            if(Tool.isEmpty(key)){
                return "无key";
            }
            String value = server.getDebugInfo(key);
            if (Tool.isEmpty(value)) {
                return "无value";
            }
            return value;
        };
    }

    private static Route addDebugInfo(final MysqlArchiver archiver, final WechatSyncServer server) {
        return (request, response) -> {
            String key=request.queryParams("wechatId");

            String value=request.body();
            if(Tool.isEmpty(key) || Tool.isEmpty(value)){
                return "fail";
            }
            server.addDebugInfo(key, value);
            return "success";
        };
    }

    private static Route syncCounters(final MysqlArchiver archiver, final WechatSyncServer server){
        return (request, response) -> {
            Map<String,Object> result=new HashMap<>();
            String body=request.body();
            try {
                String wechatId=request.queryParams("wechatId");
                if(Tool.isEmpty(wechatId)){
                    result.put("success", false);
                    result.put("msg", "wechatId不能空");
                    return result;
                }
                List<Counter> counters=null;
                try {
                    body = server.decypt(wechatId, body);
                    counters = gson.fromJson(body, new TypeToken<List<Counter>>(){}.getType());

                    for(Counter counter:counters){
                        if(!counter.getCrawlWechatId().equals(wechatId)){
                            result.put("msg", "上传者"+wechatId+" 和网页抓取者不匹配");
                            result.put("success", false);
                            return result;
                        }
                    }
                }catch(Exception e){
                    log.error(e.getMessage(), e);
                    result.put("msg", "无法解密文本，请联系管理员："+e.getMessage());
                    result.put("success", false);
                    return result;
                }
                for(Counter counter:counters){
                    archiver.upsertCounters(counter);
                }
                result.put("success", true);
            }catch(Exception e){
                result.put("msg", e.getMessage());
                result.put("success", false);
            }
            return result;
        };
    }

}


