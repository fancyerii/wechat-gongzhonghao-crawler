package com.github.fancyerii.wechatcrawler.server.tool;

import lombok.extern.slf4j.Slf4j;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;

@Slf4j
public class ConfigReader {
    private static Properties props;

    static {

        try {
            props = new Properties();
            props.load(new FileInputStream("conf/cfg.txt"));
        } catch (Exception e) {
            log.error(e.getMessage(), e);
        }
    }

    public static String getProp(String key) {
        return props.getProperty(key);
    }
}
