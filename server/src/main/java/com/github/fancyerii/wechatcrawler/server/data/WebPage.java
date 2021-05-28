package com.github.fancyerii.wechatcrawler.server.data;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

@Data
@NoArgsConstructor
public class WebPage {
    private int id;
    private String url;
    private String title;
    private String pubName;
    private Date pubTime;
    private String html;
    private String content;
    private Date lastUpdate;
    private String crawlWechatId;
    private int readCount;
}
