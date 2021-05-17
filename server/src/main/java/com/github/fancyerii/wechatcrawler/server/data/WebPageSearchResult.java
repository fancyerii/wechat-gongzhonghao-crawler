package com.github.fancyerii.wechatcrawler.server.data;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class WebPageSearchResult {
    private List<WebPageSearchItem> items;
    private long total;
}
