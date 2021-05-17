package com.github.fancyerii.wechatcrawler.server.service;

import com.antbrains.httpclientfetcher.FileTools;
import com.antbrains.mysqltool.PoolManager;
import com.github.fancyerii.wechatcrawler.server.data.MysqlArchiver;

public class DumpDebugInfo {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.out.println("需要输出路径");
            System.exit(-1);
        }
        PoolManager.StartPool("conf", "wechat");
        MysqlArchiver archiver = new MysqlArchiver();
        String s = archiver.getDebugInfo();
        FileTools.writeFile(args[0], s, "UTF-8");
    }
}
