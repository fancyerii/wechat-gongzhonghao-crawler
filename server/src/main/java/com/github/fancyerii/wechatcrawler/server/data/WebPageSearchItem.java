package com.github.fancyerii.wechatcrawler.server.data;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class WebPageSearchItem {
    private int id;
    private String wechatName;
    private String pubDate;
    private String title;
    private String url;
}
