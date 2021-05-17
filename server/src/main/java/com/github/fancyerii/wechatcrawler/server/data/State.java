package com.github.fancyerii.wechatcrawler.server.data;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

@Data
@NoArgsConstructor
public class State {
    private int id;
    private String url;
    private String title;
    private String pubName;
    private int crawlState;
    private int counterState;
    private Date firstAdd;
    private Date lastUpdate;
}
