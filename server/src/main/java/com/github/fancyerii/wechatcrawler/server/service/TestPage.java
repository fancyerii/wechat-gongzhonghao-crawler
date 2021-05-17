package com.github.fancyerii.wechatcrawler.server.service;

import com.antbrains.mysqltool.PoolManager;
import com.github.fancyerii.wechatcrawler.server.data.MysqlArchiver;
import com.github.fancyerii.wechatcrawler.server.data.WebPage;

public class TestPage {
    public static void main(String[] args){
        PoolManager.StartPool("conf","wechat");
        MysqlArchiver archiver=new MysqlArchiver();
        WebPage wp=archiver.getAllPage("https://mp.weixin.qq.com/s/-SQglSX-HL107xruus9FGw");
        System.out.println(wp.getTitle());
    }
}
