package com.github.fancyerii.wechatcrawler.server.data;

import com.antbrains.mysqltool.DBUtils;
import com.antbrains.mysqltool.PoolManager;
import com.github.fancyerii.wechatcrawler.server.service.WebContentCrawler;
import com.google.gson.Gson;
import lombok.extern.slf4j.Slf4j;

import java.io.*;
import java.sql.*;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.Date;
import java.util.regex.Pattern;
import java.util.zip.GZIPInputStream;
import java.util.zip.GZIPOutputStream;

@Slf4j
public class MysqlArchiver {

    public void insertTest(String id, String text) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();

            pstmt = conn.prepareStatement(
                    "insert into test(id, content) values(?,?)");

            pstmt.setString(1, id);
            pstmt.setString(2, text);
            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public void initState(WebPage page) throws Exception{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();

            pstmt = conn.prepareStatement(
                    "insert into state(id, crawl_state, counter_state, first_add, last_update, title, url, pub_name, " +
                            "sync_page, sync_counter)" +
                            " values(?,?,1,now(),now(),?,?,?,0,0)");
            if(page.getHtml()!=null){
                pstmt.setInt(2, 0);
            }else{
                pstmt.setInt(2, 1);
            }
            pstmt.setInt(1, page.getId());
            pstmt.setString(3, page.getTitle());
            pstmt.setString(4, page.getUrl());
            pstmt.setString(5, page.getPubName());
            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public List<State> getUnCrawledUrls(int size) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<State> states=new ArrayList<>();
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from state where crawl_state != 0 and crawl_state < 10 limit "+size);

            rs = pstmt.executeQuery();
            while(rs.next()){
                states.add(this.populateState(rs));
            }

        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return states;
    }

    public String getWechatPass(String wechatId) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from wechat_pass where wechat_id=?");
            pstmt.setString(1, wechatId);
            rs = pstmt.executeQuery();
            if(rs.next()){
                return rs.getString("pass");
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return null;
    }

    private State populateState(ResultSet rs) throws SQLException {
        int id=rs.getInt("id");
        String url=rs.getString("url");
        String pub_name=rs.getString("pub_name");
        String title=rs.getString("title");
        int crawl_state=rs.getInt("crawl_state");
        int counter_state=rs.getInt("counter_state");
        State state=new State();

        state.setId(id);
        state.setCounterState(counter_state);
        state.setCrawlState(crawl_state);
        state.setPubName(pub_name);
        state.setUrl(url);
        state.setTitle(title);
        state.setFirstAdd(DBUtils.timestamp2Date(rs.getTimestamp("first_add")));
        state.setLastUpdate(DBUtils.timestamp2Date(rs.getTimestamp("last_update")));
        return state;
    }

    public List<State> getNeedSyncCounters(int size) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<State> states=new ArrayList<>();
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from state where sync_counter=0 and counter_state=0 limit "+size);
            rs = pstmt.executeQuery();
            while(rs.next()){
                states.add(this.populateState(rs));
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return states;
    }

    public void updateSyncedCounters(List<Integer> ids) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            StringBuilder sb = new StringBuilder("update state set sync_counter=1 where id in (");
            for(int id:ids) {
                sb.append(id+",");
            }
            String sql=sb.substring(0, sb.length()-1)+")";
            pstmt = conn.prepareStatement(sql);
            pstmt.executeUpdate();
        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public void updateSyncedPages(List<Integer> ids) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            StringBuilder sb = new StringBuilder("update state set sync_page=1 where id in (");
            for(int id:ids) {
                sb.append(id+",");
            }
            String sql=sb.substring(0, sb.length()-1)+")";
            pstmt = conn.prepareStatement(sql);
            pstmt.executeUpdate();
        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public String getDebugInfo(String wechatId) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from debuginfo where crawl_wechat_id =? ");
            pstmt.setString(1, wechatId);
            rs = pstmt.executeQuery();
            if(rs.next()){
                return rs.getString("content");
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return null;
    }

    public List<State> getNeedSyncPages(int size) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<State> states=new ArrayList<>();
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from state where sync_page=0 and crawl_state=0 limit "+size);
            rs = pstmt.executeQuery();
            while(rs.next()){
                states.add(this.populateState(rs));
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return states;
    }

    public List<State> getStates(String pubName) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<State> states=new ArrayList<>();
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from state where pub_name=? order by id desc limit 1000");
            pstmt.setString(1, pubName);
            rs = pstmt.executeQuery();
            while(rs.next()){
                states.add(this.populateState(rs));
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return states;
    }

    public void updateCounter(int id, String crawlWechatId, int readCount, int starCount, String rvs) throws Exception{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();

            pstmt = conn.prepareStatement("insert into counter(id, read_count, star_count, crawl_wechat_id, last_update, rvs)" +
                    "values(?,?,?,?,now(),?) on duplicate key update read_count=VALUES(read_count), star_count=VALUES(star_count), " +
                    "crawl_wechat_id=VALUES(crawl_wechat_id), last_update=now(), rvs=VALUES(rvs)");
            pstmt.setInt(1, id);
            pstmt.setInt(2, readCount);
            pstmt.setInt(3, starCount);
            pstmt.setString(4, crawlWechatId);
            byte[] bytes = this.gzipHtml(rvs);
            if (bytes == null) {
                pstmt.setNull(5, java.sql.Types.BLOB);
            } else {
                pstmt.setBlob(5, new ByteArrayInputStream(bytes));
            }
            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public int updateCounterState(int id, boolean succ) throws Exception{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            if(succ) {
                pstmt = conn.prepareStatement(
                        "update state set counter_state=0, last_update=now() where id=?");
            }else{
                //如果成功了则不再允许更新
                pstmt = conn.prepareStatement("update state set counter_state=counter_state+1, last_update=now() " +
                        "where id=? and counter_state <> 0");
            }
            pstmt.setInt(1, id);
            return pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public int updateCrawlState(int id, boolean succ) throws Exception{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            if(succ) {
                pstmt = conn.prepareStatement(
                        "update state set crawl_state=0, last_update=now() where id=?");
            }else{
                //如果成功了则不再允许更新
                pstmt = conn.prepareStatement("update state set crawl_state=crawl_state+1, last_update=now() " +
                        "where id=? and crawl_state <> 0");
            }
            pstmt.setInt(1, id);
            return pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public void updateWebPageContent(int id, String html, String content, java.util.Date pubDate) throws Exception{
        Connection conn = null;

        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement("update webpage set pub_time=?, html=?, content=?, last_update=now() where id=?");
            byte[] bytes = this.gzipHtml(html);
            if (bytes == null) {
                pstmt.setNull(2, java.sql.Types.BLOB);
            } else {
                pstmt.setBlob(2, new ByteArrayInputStream(bytes));
            }
            pstmt.setString(3, content);
            pstmt.setInt(4, id);
            pstmt.setTimestamp(1, DBUtils.date2Timestamp(pubDate));
            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public HeartBeat getLastHeartBeat(String wechatId) throws SQLException {
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        HeartBeat hb=new HeartBeat();
        hb.setWechatId(wechatId);
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from heartbeat where crawl_wechat_id=?");
            pstmt.setString(1, wechatId);
            rs = pstmt.executeQuery();
            if (rs.next()) {
                hb.setActivityType(rs.getString("activity_type"));
                hb.setLastUpdate(DBUtils.timestamp2Date(rs.getTimestamp("last_update")));
            }

        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return hb;
    }

    public void updateHeartbeat(String wechatId, String type) throws SQLException {
        HeartBeat hb=new HeartBeat();
        hb.setWechatId(wechatId);
        hb.setActivityType(type);
        updateHeartbeat(hb);
    }

    public void updateHeartbeat(HeartBeat hb) throws SQLException{
        Connection conn = null;

        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement("insert into heartbeat(crawl_wechat_id, activity_type, last_update)" +
                    "values(?,?,now()) on duplicate key update activity_type=?, last_update=now()");
            pstmt.setString(1, hb.getWechatId());
            pstmt.setString(2, hb.getActivityType());
            pstmt.setString(3, hb.getActivityType());
            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public void upsertCounters(Counter counter) throws Exception{
        Connection conn = null;

        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "insert into all_counters(url, read_count, star_count, last_update, crawl_wechat_id, rvs)" +
                            " values(?,?,?,now(),?,?)" +
                            " ON DUPLICATE KEY UPDATE read_count=VALUES(read_count), star_count=VALUES(star_count), " +
                            "last_update=now(), " +
                            "crawl_wechat_id=VALUES(crawl_wechat_id), rvs=VALUES(rvs)");
            pstmt.setString(1, counter.getUrl());
            pstmt.setInt(2, counter.getReadCount());
            pstmt.setInt(3, counter.getStarCount());
            pstmt.setString(4, counter.getCrawlWechatId());
            byte[] bytes = this.gzipHtml(counter.getRvs());
            if (bytes == null) {
                pstmt.setNull(5, java.sql.Types.BLOB);
            } else {
                pstmt.setBlob(5, new ByteArrayInputStream(bytes));
            }
            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public void upsertDebugInfo(String wechatId, String json) throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "insert into debuginfo(crawl_wechat_id, content)" +
                            " values(?,?)" +
                            " ON DUPLICATE KEY UPDATE content=VALUES(content)");
            pstmt.setString(1, wechatId);
            pstmt.setString(2, json);

            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    public String getDebugInfo() throws SQLException{
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from debuginfo limit 1");

            rs = pstmt.executeQuery();
            if(rs.next()){
                String id=rs.getString("crawl_wechat_id");
                String content=rs.getString("content");
                Map<String,Object> data=new HashMap<>();
                data.put("id", id);
                data.put("info", content);
                return new Gson().toJson(data);
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return "";
    }

    public void upsertAllWebPages(WebPage page) throws Exception{
        Connection conn = null;

        PreparedStatement pstmt = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "insert into all_pages(url, title, pub_name, pub_time, html, last_update, crawl_wechat_id, content)" +
                            " values(?,?,?,?,?,now(),?,?)" +
                            " ON DUPLICATE KEY UPDATE title=VALUES(title), pub_name=VALUES(pub_name), " +
                            "pub_time=VALUES(pub_time), content=VALUES(html), last_update=now(), " +
                            "crawl_wechat_id=VALUES(crawl_wechat_id), content=VALUES(content)");
            pstmt.setString(1, page.getUrl());
            pstmt.setString(2, page.getTitle());
            pstmt.setString(3, page.getPubName());
            pstmt.setTimestamp(4, DBUtils.date2Timestamp(page.getPubTime()));
            byte[] bytes = this.gzipHtml(page.getHtml());
            if (bytes == null) {
                pstmt.setNull(5, java.sql.Types.BLOB);
            } else {
                pstmt.setBlob(5, new ByteArrayInputStream(bytes));
            }
            pstmt.setString(6, page.getCrawlWechatId());
            pstmt.setString(7, page.getContent());
            pstmt.executeUpdate();

        } finally {
            DBUtils.closeAll(conn, pstmt, null);
        }
    }

    private DateFormat sdf=new SimpleDateFormat("yyyy-MM-dd");

    private DateFormat sdf2=new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

    public void downloadJson(String wechatName, String startDate, String endDate, OutputStream os,
                             String fields) throws Exception {
        String sqlWhere=buildWhere(wechatName, startDate,endDate);
        Connection conn = null;

        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement("select * from webpage "
                            +sqlWhere, ResultSet.TYPE_FORWARD_ONLY, ResultSet.CONCUR_READ_ONLY);
            pstmt.setFetchSize(Integer.MIN_VALUE);
            if(!wechatName.isEmpty()){
                pstmt.setString(1, wechatName);
            }
            rs=pstmt.executeQuery();
            Gson gson=new Gson();
            Set<String> outputFields=null;
            if(fields!=null && !fields.trim().isEmpty()){
                fields=fields.trim();
                outputFields=new HashSet<>();
                String[] fs=fields.split(",");
                for(String field:fs){
                    outputFields.add(field);
                }
            }
            while(rs.next()){
                WebPage page = this.populateWebPage(rs);
                Map<String,Object> data=new HashMap<>();
                if(outputFields == null || outputFields.contains("title")) {
                    data.put("title", page.getTitle());
                }
                if(outputFields == null || outputFields.contains("pubName")) {
                    data.put("pubName", page.getPubName());
                }
                if(outputFields == null || outputFields.contains("pubTime")) {
                    data.put("pubTime", sdf2.format(page.getPubTime()));
                }
                if(outputFields == null || outputFields.contains("content")) {
                    data.put("content", page.getContent());
                }
                if(outputFields == null || outputFields.contains("html")) {
                    data.put("html", page.getHtml());
                }
                String s=gson.toJson(data)+"\n";
                os.write(s.getBytes("UTF-8"));
            }

        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
    }

    private String buildWhere(String wechatName, String startDate, String endDate){
        try {
            sdf.parse(startDate);
        }catch(Exception e){
            startDate="";
        }
        try{
            sdf.parse(endDate);
        }catch(Exception e){
            endDate="";
        }

        String sqlWhere = "";
        boolean hasWhere=false;
        if(!wechatName.isEmpty()){
            hasWhere=true;
            sqlWhere = " where pub_name=? ";
        }
        if(!startDate.isEmpty()){
            if(hasWhere){
                sqlWhere += " and pub_time >= '"+startDate+"' ";
            }else{
                sqlWhere += " where pub_time >= '"+startDate+"' ";
                hasWhere=true;
            }
        }
        if(!endDate.isEmpty()){
            if(hasWhere){
                sqlWhere += " and pub_time >= "+startDate+" ";
            }else{
                sqlWhere += " where pub_time <= "+endDate+" ";
            }
        }
        return sqlWhere;
    }

    public WebPageSearchResult search(String wechatName, String startDate, String endDate,
                                      int offset, int limit){
        String sqlWhere=buildWhere(wechatName, startDate, endDate);
        WebPageSearchResult sr = new WebPageSearchResult();
        try {
            sr.setTotal(getTotalCount(sqlWhere, wechatName));
            sr.setItems(getItems(sqlWhere, wechatName, offset, limit));
        } catch (SQLException e) {
            log.error(e.getMessage(), e);
        }
        return sr;
    }

    private List<WebPageSearchItem> getItems(String sqlWhere, String wechatName, int offset, int limit) throws SQLException {
        Connection conn = null;

        PreparedStatement pstmt = null;
        ResultSet rs = null;
        List<WebPageSearchItem> items=new ArrayList<>(limit);
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement("select id, pub_name, pub_time, title, url from webpage "+sqlWhere
                    +"order by id desc limit "+limit+" offset "+offset);
            if(!wechatName.isEmpty()){
                pstmt.setString(1, wechatName);
            }
            rs=pstmt.executeQuery();
            while(rs.next()){
                WebPageSearchItem item=new WebPageSearchItem();
                items.add(item);
                item.setId(rs.getInt("id"));
                item.setTitle(rs.getString("title"));
                item.setUrl(rs.getString("url"));
                item.setWechatName(rs.getString("pub_name"));
                Date d=DBUtils.timestamp2Date(rs.getTimestamp("pub_time"));

                item.setPubDate(sdf.format(d));
            }

        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return items;
    }

    private long getTotalCount(String sqlWhere, String wechatName) throws SQLException {
        Connection conn = null;

        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement("select count(*) from webpage "+sqlWhere);
            if(!wechatName.isEmpty()){
                pstmt.setString(1, wechatName);
            }
            rs=pstmt.executeQuery();
            if(rs.next()){
                return rs.getLong(1);
            }else {
                return 0;
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
    }

    public int addUrlToWebPage(WebPage page) throws Exception{
        Connection conn = null;

        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "insert into webpage(url, pub_time, crawl_wechat_id, title, pub_name, content, html, last_update)" +
                            " values(?,?,?,?,?,?,?, now())",
                    Statement.RETURN_GENERATED_KEYS);
            pstmt.setTimestamp(2, DBUtils.date2Timestamp(WebContentCrawler.extPubDate(page.getHtml())));
            pstmt.setString(1, page.getUrl());
            pstmt.setString(3, page.getCrawlWechatId());
            pstmt.setString(4, page.getTitle());
            pstmt.setString(5, page.getPubName());
            pstmt.setString(6, page.getContent());
            byte[] bytes = this.gzipHtml(page.getHtml());
            if (bytes == null) {
                pstmt.setNull(7, java.sql.Types.BLOB);
            } else {
                pstmt.setBlob(7, new ByteArrayInputStream(bytes));
            }

            pstmt.executeUpdate();
            rs = pstmt.getGeneratedKeys();
            if (rs.next()) {
                return rs.getInt(1);
            }else{
                throw new RuntimeException("bug!!!");
            }
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
    }



    private byte[] gzipHtml(String html) throws IOException {
        if (html == null || html.length() == 0)
            return null;
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        GZIPOutputStream gos = new GZIPOutputStream(baos);
        gos.write(html.getBytes("UTF8"));
        gos.close();
        return baos.toByteArray();
    }

    private String readHtml(InputStream is) throws IOException {
        if (is == null)
            return null;
        GZIPInputStream gis = new GZIPInputStream(is);
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();

        int nRead;
        byte[] data = new byte[16384];
        while ((nRead = gis.read(data, 0, data.length)) != -1) {
            buffer.write(data, 0, nRead);
        }

        buffer.flush();
        return new String(buffer.toByteArray(), "UTF8");
    }

    public WebPage getAllPage(String url){
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from all_pages where url=?");
            pstmt.setString(1, url);
            rs = pstmt.executeQuery();
            if (rs.next()) {
                WebPage page=new WebPage();
                page.setUrl(rs.getString("url"));
                page.setTitle(rs.getString("title"));
                page.setPubName(rs.getString("pub_name"));
                page.setPubTime(DBUtils.timestamp2Date(rs.getTimestamp("pub_time")));
                page.setHtml(this.readHtml(rs.getBinaryStream("html")));
                page.setContent(rs.getString("content"));
                page.setLastUpdate(DBUtils.timestamp2Date(rs.getTimestamp("last_update")));
                page.setCrawlWechatId(rs.getString("crawl_wechat_id"));
                return page;
            }

        } catch (Exception e) {
            log.error(e.getMessage(), e);
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return null;
    }

    private WebPage populateWebPage(ResultSet rs) throws Exception {
        WebPage page=new WebPage();
        page.setUrl(rs.getString("url"));
        page.setId(rs.getInt("id"));
        page.setTitle(rs.getString("title"));
        page.setPubName(rs.getString("pub_name"));
        page.setPubTime(DBUtils.timestamp2Date(rs.getTimestamp("pub_time")));
        page.setHtml(this.readHtml(rs.getBinaryStream("html")));
        page.setContent(rs.getString("content"));
        page.setLastUpdate(DBUtils.timestamp2Date(rs.getTimestamp("last_update")));
        page.setCrawlWechatId(rs.getString("crawl_wechat_id"));
        return page;
    }

    public List<Counter> getCounters(List<Integer> ids){
        if(ids==null || ids.isEmpty()) return new ArrayList<>(0);
        List<Counter> counters=new ArrayList<>(ids.size());
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            StringBuilder sb = new StringBuilder("select counter.*, webpage.url from counter join webpage " +
                    "on counter.id=webpage.id where counter.id in (");
            for(int id:ids) {
                sb.append(id+",");
            }
            String sql=sb.substring(0, sb.length()-1)+")";


            pstmt = conn.prepareStatement(sql);
            rs = pstmt.executeQuery();
            while (rs.next()) {
                Counter counter=new Counter();
                counters.add(counter);
                counter.setUrl(rs.getString("url"));
                counter.setReadCount(rs.getInt("read_count"));
                counter.setStarCount(rs.getInt("star_count"));
                counter.setCrawlWechatId(rs.getString("crawl_wechat_id"));
                counter.setRvs(this.readHtml(rs.getBinaryStream("rvs")));
            }

        } catch (Exception e) {
            log.error(e.getMessage(), e);
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }

        return counters;
    }

    public List<WebPage> getWebPages(List<Integer> ids){
        if(ids==null || ids.isEmpty()) return new ArrayList<>(0);
        List<WebPage> pages=new ArrayList<>(ids.size());
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            StringBuilder sb = new StringBuilder("select * from webpage where id in (");
            for(int id:ids) {
                sb.append(id+",");
            }
            String sql=sb.substring(0, sb.length()-1)+")";


            pstmt = conn.prepareStatement(sql);
            rs = pstmt.executeQuery();
            while (rs.next()) {
                pages.add(this.populateWebPage(rs));
            }

        } catch (Exception e) {
            log.error(e.getMessage(), e);
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }

        return pages;
    }

    public WebPage getWebPage(String url) {
        WebPage page = new WebPage();
        Connection conn = null;
        PreparedStatement pstmt = null;
        ResultSet rs = null;
        try {
            conn = PoolManager.getConnection();
            pstmt = conn.prepareStatement(
                    "select * from webpage where url=?");
            pstmt.setString(1, url);
            rs = pstmt.executeQuery();
            if (rs.next()) {
                return this.populateWebPage(rs);
            }

        } catch (Exception e) {
            log.error(e.getMessage(), e);
        } finally {
            DBUtils.closeAll(conn, pstmt, rs);
        }
        return null;
    }

    public static void main(String[] args) throws Exception {
        PoolManager.StartPool("conf","wechat");
        MysqlArchiver archiver=new MysqlArchiver();
//        WebPage page=archiver.getWebPage(3);
//        String xml=page.getContent();
//        XmlParser parser=new XmlParser();
//        parser.load(xml);
//        NodeList nodes=parser.selectNodes("//P");
//        System.out.println(page.getUrl());
//        for(int i=0;i<nodes.getLength();i++){
//            Node node=nodes.item(i);
//            String p = node.getTextContent().replace("\n", "").trim();
//            if(!p.isEmpty()) {
//                System.out.println(i + "->" + p);
//            }
//        }
        WebPage page=new WebPage();
        page.setCrawlWechatId("lili");
        page.setUrl("http://www.com");
        page.setPubName("环球2");
        page.setPubTime(Calendar.getInstance().getTime());
        page.setTitle("标题2");
        page.setContent("html12");
        archiver.upsertAllWebPages(page);
    }
}
