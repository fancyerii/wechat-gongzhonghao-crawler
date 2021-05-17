package com.github.fancyerii.wechatcrawler.server.data;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

@Data
@NoArgsConstructor
public class HeartBeat {
    private String wechatId;
    private String activityType;
    private Date lastUpdate;
}
