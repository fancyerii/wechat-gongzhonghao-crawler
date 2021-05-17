package com.github.fancyerii.wechatcrawler.server.service;

import com.antbrains.mysqltool.PoolManager;
import com.github.fancyerii.wechatcrawler.server.data.MysqlArchiver;

public class TestUtf8 {
    public static void main(String[] args) throws Exception {
        PoolManager.StartPool("conf","wechat");
        MysqlArchiver archiver=new MysqlArchiver();
        archiver.insertTest("id", "你好\uD83D\uDC69\uD83C\uDFFB\u200D\uD83E\uDDB1");
    }
}
