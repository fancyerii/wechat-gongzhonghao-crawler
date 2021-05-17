package com.github.fancyerii.wechatcrawler.server.service;

import com.antbrains.httpclientfetcher.HttpClientFetcher;
import com.antbrains.nekohtmlparser.NekoHtmlParser;
import com.antbrains.nekohtmlparser.XmlParser;
import com.github.fancyerii.wechatcrawler.server.data.MysqlArchiver;
import com.github.fancyerii.wechatcrawler.server.data.State;
import lombok.extern.slf4j.Slf4j;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.sql.SQLException;
import java.util.Date;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
public class WebContentCrawler implements Runnable {
    private MysqlArchiver archiver;
    private int size = 100;
    private HttpClientFetcher fetcher;
    private long crawlInterval = 3000;
    private long emptySleep = 60 * 1000L;

    public WebContentCrawler(MysqlArchiver archiver) {
        this.archiver = archiver;
        fetcher = new HttpClientFetcher(WebContentCrawler.class.getName());
        fetcher.init();
    }

    static Pattern timePtn = Pattern.compile("var t=\"(\\d+)\",n=\"(\\d+)\",i=\"[^;]+\";");

    public static Date extPubDate(String html) {
        if (html == null) return null;
        Matcher m = timePtn.matcher(html);
        if (m.find()) {
            long pubTime = Integer.valueOf(m.group(2)) * 1000L;
            return new Date(pubTime);
        }
        return null;
    }

    public static String extHtml(String html) {
        if (html == null) return null;
        NekoHtmlParser parser = new NekoHtmlParser();
        try {
            parser.load(html, "UTF8");
        } catch (Exception e) {
            return "ext error";
        }
        NodeList paras = parser.selectNodes("//DIV[@id='js_content']/P | //DIV[@id='js_content']/SECTION/P");
        StringBuilder sb = new StringBuilder("");
        for (int i = 0; i < paras.getLength(); i++) {
            Node p = paras.item(i);
            String s = p.getTextContent();
            sb.append(s).append("\n");

        }
        return sb.toString();
    }

    private void processState(State state) throws Exception {
        String url = state.getUrl();
        String html = null;
        try {
            html = fetcher.httpGet(url, 3);
        } catch (Exception e) {
            log.error(e.getMessage(), e);
        }
        if (html == null) {
            archiver.updateCrawlState(state.getId(), false);
        } else {
            Date pubDate = extPubDate(html);
            archiver.updateWebPageContent(state.getId(), html, extHtml(html), pubDate);
            archiver.updateCrawlState(state.getId(), true);
        }
    }

    @Override
    public void run() {
        while (true) {
            List<State> states = null;
            try {
                states = archiver.getUnCrawledUrls(100);
            } catch (SQLException e) {
                log.error(e.getMessage(), e);
                break;
            }
            for (State state : states) {
                try {
                    this.processState(state);
                } catch (Exception e) {
                    log.error(e.getMessage(), e);
                }
                try {
                    Thread.sleep(crawlInterval);
                } catch (InterruptedException e) {

                }
            }
            if (states.isEmpty()) {
                try {
                    Thread.sleep(emptySleep);
                } catch (InterruptedException e) {

                }
            }
        }
    }


    public static void main(String[] args) throws Exception {
        HttpClientFetcher fetcher = new HttpClientFetcher(WebContentCrawler.class.getName());
        fetcher.init();
        String html = fetcher.httpGet("https://mp.weixin.qq.com/s/bxpHV5EkJaYOA62bz1miNQ", 3);

        String content = extHtml(html);
        System.out.println(content);
        fetcher.close();
    }
}
