package com.github.fancyerii.wechatcrawler.server.data;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

@Data
@NoArgsConstructor
public class Counter {
    private String url;
    private int readCount;
    private int starCount;
    private String crawlWechatId;
    private String rvs;
}
