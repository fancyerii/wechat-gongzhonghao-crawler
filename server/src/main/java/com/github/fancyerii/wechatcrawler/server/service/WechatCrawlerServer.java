package com.github.fancyerii.wechatcrawler.server.service;

import com.antbrains.mysqltool.PoolManager;
import com.github.fancyerii.wechatcrawler.server.data.*;
import com.github.fancyerii.wechatcrawler.server.tool.ConfigReader;
import com.github.fancyerii.wechatcrawler.server.tool.MyDateTypeAdapter;
import com.github.fancyerii.wechatcrawler.server.tool.ThymeleafTemplateEngine;
import com.github.fancyerii.wechatcrawler.server.tool.Tool;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.io.FileUtils;
import spark.*;

import java.io.File;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.*;

import static spark.Spark.*;

@Slf4j
public class WechatCrawlerServer {

    public static void main(String[] args) throws Exception {
        port(4567);
        staticFiles.location("/public");
        PoolManager.StartPool("conf","wechat");
        MysqlArchiver archiver=new MysqlArchiver();
        //get("/searchview", searchView(ts), new ThymeleafTemplateEngine());
        post("/getstate", "application/json", getState(archiver), gson::toJson);
        get("/updatecrawlstate", "application/json", updateCrawlState(archiver), gson::toJson);
        post("/updatecounter", "application/json", updateCounter(archiver), gson::toJson);
        post("/heartbeat", "application/json", heartBeat(archiver), gson::toJson);
        post("/addurl", "application/json", addUrl(archiver), gson::toJson);
        post("/debuginfo", "application/json", upsertDebugInfo(archiver), gson::toJson);

        get("/viewPage", viewPage(archiver), new ThymeleafTemplateEngine());
        get("/search", searchView(archiver), new ThymeleafTemplateEngine());

        get("/download", ((request, response) -> {
            String wechatName = request.queryParams("wechatName");
            if (wechatName == null) {
                wechatName = "";
            }
            wechatName = wechatName.trim();
            String startDate = request.queryParams("startDate");
            if(startDate==null){
                startDate = "";
            }
            startDate = startDate.trim();
            String endDate = request.queryParams("endDate");
            if(endDate==null){
                endDate = "";
            }
            endDate = endDate.trim();
            String fields=request.queryParams("fields");
            if(fields==null){
                fields="title,content,url,pubName,pubTime";
            }
            response.raw().setContentType("application/octet-stream");
            response.raw().setHeader("Content-Disposition","attachment; filename="+"data.json");

            OutputStream os=response.raw().getOutputStream();
            archiver.downloadJson(wechatName, startDate, endDate, os, fields);
            os.close();
            return null;
        }));
        Thread crawler = new Thread(new WebContentCrawler(archiver));
        crawler.start();
        String doSync= ConfigReader.getProp("do_sync");
        if("true".equalsIgnoreCase(doSync)) {
            new Thread(new PageAndCounterSyncer(archiver)).start();
        }

    }

    static Gson gson=new GsonBuilder().registerTypeAdapter(Date.class, new MyDateTypeAdapter()).create();
    static JsonParser parser=new JsonParser();
    static SimpleDateFormat sdf=new SimpleDateFormat("yyyy-MM-dd HH:mm");

    private static TemplateViewRoute viewPage(final MysqlArchiver archiver) {
        return new TemplateViewRoute() {
            @Override
            public ModelAndView handle(Request request, Response response) throws Exception {

                String id = request.queryParams("id");
                List<Integer> idList=new ArrayList<>(1);
                idList.add(Integer.valueOf(id));
                List<WebPage> pages=archiver.getWebPages(idList);
                Map<String, Object> model=new HashMap<>();
                if(pages.size()==1){
                    WebPage page=pages.get(0);
                    String content=page.getContent();
                    if(content==null) content="";
                    content=content.replace("\n", "<br/>");
                    model.put("content", content);
                    model.put("title", page.getTitle());
                    if(page.getPubTime()!=null){
                        model.put("pubDate", sdf.format(page.getPubTime()));
                    }else{
                        model.put("pubDate", "未知");
                    }
                    model.put("pubName", page.getPubName());
                }
                return new ModelAndView(model, "viewPage"); // located in resources/templates
            }

        };
    }

    private static TemplateViewRoute searchView(final MysqlArchiver archiver) {
        return new TemplateViewRoute() {
            int pageWindow=3;
            private Map<String, Object> doSearch(String wechatName, String startDate, String endDate, int page, int numPage) throws Exception {
                log.info("searchView wechatName={}, page={}, start={}, end={}", wechatName, page, startDate, endDate);
                WebPageSearchResult sr=archiver.search(wechatName, startDate, endDate, (page-1)*numPage, page*numPage);
                List<WebPageSearchItem> items=sr.getItems();
                if(items==null) items=new ArrayList<>(0);
                int totalPage = (Math.min(10000, (int)sr.getTotal()) - 1) / numPage + 1;
                Map<String, Object> model=new HashMap<>();
                model.put("totalCount", sr.getTotal());
                model.put("wechatName", wechatName);
                model.put("items", items);
                model.put("curPage", page);
                model.put("totalPage", totalPage);
                model.put("startDate", startDate);
                model.put("endDate", endDate);
                List<Integer> pageNumbers = new ArrayList<>();
                int minPage = Math.max(1, page - pageWindow);
                int maxPage = Math.min(totalPage, page + pageWindow);
                for (int i = minPage; i <= maxPage; i++) {
                    pageNumbers.add(i);
                }
                model.put("pageNumbers", pageNumbers);
                return model;
            }
            @Override
            public ModelAndView handle(Request request, Response response) throws Exception {

                String wechatName = request.queryParams("wechatName");
                if (wechatName == null) {
                    wechatName = "";
                }
                wechatName = wechatName.trim();
                String startDate = request.queryParams("startDate");
                if(startDate==null){
                    startDate = "";
                }
                startDate = startDate.trim();
                String endDate = request.queryParams("endDate");
                if(endDate==null){
                    endDate = "";
                }
                endDate = endDate.trim();
                String pageStr = request.queryParams("page");
                int page = 1;
                try {
                    page = Integer.valueOf(pageStr);
                } catch (Exception e) {
                }



                Map<String, Object> model = doSearch(wechatName,startDate, endDate, page, 10);
                return new ModelAndView(model, "search"); // located in resources/templates
            }

        };
    }

    private static Route addUrl(final MysqlArchiver archiver){
        return (request, response) -> {
            String body=request.body();
            Map<String,Object> result=new HashMap<>();

            try {
                WebPage page=gson.fromJson(body, WebPage.class);
                if(Tool.isEmpty(page.getCrawlWechatId())){
                    result.put("success", false);
                    result.put("msg", "crawlWeichatId不能空");
                    return result;
                }
                if(Tool.isEmpty(page.getUrl())){
                    result.put("success", false);
                    result.put("msg", "url不能空");
                    return result;
                }
                if(Tool.isEmpty(page.getTitle())){
                    result.put("success", false);
                    result.put("msg", "title不能空");
                    return result;
                }
                if(page.getHtml()!=null){
                    page.setContent(WebContentCrawler.extHtml(page.getHtml()));
                }
                int id = archiver.addUrlToWebPage(page);
                page.setId(id);
                result.put("id", id);
                archiver.initState(page);
                archiver.updateHeartbeat(page.getCrawlWechatId(), "add-url");
                result.put("success", true);
            }catch(Exception e){
                log.error(e.getMessage(), e);
                result.put("success", false);
                result.put("msg", e.getMessage());
            }
            return result;
        };
    }

    private static Route upsertDebugInfo(final MysqlArchiver archiver){
        return (request, response) -> {
            String body=request.body();
            Map<String,Object> result=new HashMap<>();

            try {
                String wechatId=request.queryParams("wechatId");
                if(Tool.isEmpty(wechatId)){
                    result.put("success", false);
                    result.put("msg", "wechatId不能空");
                    return result;
                }
                archiver.upsertDebugInfo(wechatId, body);
                result.put("success", true);
            }catch(Exception e){
                result.put("success", false);
                result.put("msg", e.getMessage());
            }
            return result;
        };
    }

    private static Route updateCounter(final MysqlArchiver archiver){
        return (request, response) -> {
            Map<String,Object> result=new HashMap<>();
            String body=request.body();
            try {
                JsonObject jo =parser.parse(body).getAsJsonObject();
                String state=jo.get("state").getAsString();
                String wechatId=jo.get("wechatId").getAsString();
                if(Tool.isEmpty(wechatId)){
                    result.put("success", false);
                    result.put("msg", "wechatId不能空");
                    return result;
                }
                Integer id = Tool.getInt(jo.get("id").getAsString());
                if(id == null){
                    result.put("success", false);
                    result.put("msg", "id为空或者非整数");
                    return result;
                }

                if(Tool.isEmpty(state)){
                    result.put("success", false);
                    result.put("msg", "state不能空");
                    return result;
                }
                boolean bState=false;
                if(state.equalsIgnoreCase("true")){
                    Integer readCount = Tool.getInt(jo.get("read").getAsString());
                    if(readCount==null){
                        result.put("success", false);
                        result.put("msg", "read为空或者非整数");
                        return result;
                    }
                    Integer starCount = Tool.getInt(jo.get("star").getAsString());
                    if(starCount==null){
                        result.put("success", false);
                        result.put("msg", "star为空或者非整数");
                        return result;
                    }
                    bState=true;
                    String rvs=jo.get("rvs").toString();
                    archiver.updateCounter(id, wechatId, readCount, starCount, rvs);
                }else if(state.equalsIgnoreCase("false")){
                    bState=false;
                }else{
                    result.put("success", false);
                    result.put("msg", "state in valid: "+state);
                    return result;
                }
                int updateCount = archiver.updateCounterState(id, bState);
                archiver.updateHeartbeat(wechatId, "update-counter");
                result.put("success", true);
                result.put("update", updateCount);
            }catch(Exception e){
                result.put("msg", e.getMessage());
                result.put("success", false);
            }
            return result;
        };
    }
    private static Route updateCrawlState(final MysqlArchiver archiver){
        return (request, response) -> {
            Map<String,Object> result=new HashMap<>();

            try {
                String idStr = request.queryParams("id");
                String state=request.queryParams("state");
                if(Tool.isEmpty(idStr)){
                    result.put("success", false);
                    result.put("msg", "id不能空");
                    return result;
                }
                int id;
                try{
                    id=Integer.valueOf(idStr);
                }catch(Exception e){
                    result.put("success", false);
                    result.put("msg", "id in valid: "+idStr);
                    return result;
                }

                if(Tool.isEmpty(state)){
                    result.put("success", false);
                    result.put("msg", "state不能空");
                    return result;
                }
                boolean bState=false;
                if(state.equalsIgnoreCase("true")){
                    bState=true;
                }else if(state.equalsIgnoreCase("false")){
                    bState=false;
                }else{
                    result.put("success", false);
                    result.put("msg", "state in valid: "+state);
                    return result;
                }
                int updateCount = archiver.updateCrawlState(id, bState);
                result.put("success", true);
                result.put("update", updateCount);
            }catch(Exception e){
                result.put("msg", e.getMessage());
                result.put("success", false);
            }
            return result;
        };
    }

    private static Route getState(final MysqlArchiver archiver){
        return (request, response) -> {
            String body=request.body();
            Map<String,Object> result=new HashMap<>();

            try {
                WebPage page=gson.fromJson(body, WebPage.class);
                if(Tool.isEmpty(page.getPubName())){
                    result.put("success", false);
                    result.put("msg", "pubName不能空");
                    return result;
                }

                result.put("data", archiver.getStates(page.getPubName()));
                result.put("success", true);
            }catch(Exception e){
                result.put("msg", e.getMessage());
                result.put("success", false);
                result.put("body", body);
            }
            return result;
        };
    }

    private static Route heartBeat(final MysqlArchiver archiver){
        return (request, response) -> {
            String body=request.body();
            Map<String,Object> result=new HashMap<>();

            try {
                HeartBeat hb=gson.fromJson(body, HeartBeat.class);
                if(Tool.isEmpty(hb.getWechatId())){
                    result.put("success", false);
                    result.put("msg", "wechatId不能空");
                    return result;
                }
                if(Tool.isEmpty(hb.getActivityType())){
                    result.put("success", false);
                    result.put("msg", "activityType不能空");
                    return result;
                }

                archiver.updateHeartbeat(hb);
                result.put("success", true);
            }catch(Exception e){
                //log.error(e.getMessage(), e);
                result.put("success", false);
                result.put("msg", e.getMessage());
            }
            return result;
        };
    }

}


