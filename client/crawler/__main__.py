import os
import configparser
from pathlib import Path
import time
from datetime import datetime
import requests
import json
import traceback
import re
import ctypes

from .wechatautomator import WechatAutomator

def url_in_states(url, states):
    for state in states:
        if url == state['url']:
            return True
    return False


def send_heart_beat(wechat_id, type, java_server):
    try:
        page = {"wechatId": wechat_id,
                "activityType": type
                }
        print("heart-beat: {}".format(page))
        s = requests.post(java_server + "/heartbeat", json=page)
        res = json.loads(s.text)
        if not res["success"]:
            print("heartbeat失败：{}".format(res))
    except:
        print("heartbeat失败")

def send_debug_info(wechat_id, debug_info, java_server):
    try:
        print("heart-beat: {}".format(debug_info))
        s = requests.post(java_server + "/debuginfo?wechatId="+wechat_id, json=debug_info)
        res = json.loads(s.text)
        if not res["success"]:
            print("send-debug-info失败：{}".format(res))
    except:
        print("send-debug-info失败")

def add_to_detail(s, detail):
    detail.append(time.strftime("%Y-%m-%d %H:%M:%S")+" "+str(s))

def main(parser):
    debug_info = {}
    wechat_path = parser.get('basic', 'wechat_path', fallback=None)
    if wechat_path is not None and wechat_path.strip() == '':
        wechat_path = None
    java_server = parser.get('basic', 'java_server', fallback=None)
    if java_server is not None and java_server.strip() == '':
        java_server = None
    if java_server is None:
        java_server = "http://localhost:4567"

    win_width = int(parser.get('basic', 'win_width', fallback=1000))
    win_height = int(parser.get('basic', 'win_height', fallback=600))
    crawl_interval = int(parser.get('basic', 'crawl_interval', fallback=1))
    crawl_pages = int(parser.get('basic', 'crawl_pages', fallback=3))
    max_crawl_pages = int(parser.get('basic', 'max_crawl_pages', fallback=6))

    debug_count = int(parser.get('basic', "debug_count", fallback="10"))
    latest_date = parser.get('basic', 'latest_date', fallback=None)
    first_pages = int(parser.get('basic', 'first_pages', fallback="1"))

    first_max_crawl_time = int(parser.get('basic', 'first_max_crawl_time', fallback="86400"))
    switch_gongzhonghao = parser.get('basic', 'switch_gongzhonghao', fallback=None)



    print("max_crawl_pages: {}, crawl_pages: {}".format(max_crawl_pages, crawl_pages))
    print("width: {}, height: {}".format(win_width, win_height))
    print("java_server: {}".format(java_server))
    print("wechat_path: {}".format(wechat_path))
    print("crawl_interval: {} hours".format(crawl_interval))
    print("latest_date: {}".format(latest_date))
    print("first_max_crawl_time: {}".format(first_max_crawl_time))
    print("switch_gongzhonghao: {}".format(switch_gongzhonghao))
    print("first_pages: {}".format(first_pages))

    cwd = os.getcwd()
    print("current directory {}".format(cwd))
    debug_info["max_crawl_pages"] = max_crawl_pages
    debug_info["crawl_pages"] = crawl_pages
    debug_info["win_width"] = win_width
    debug_info["win_height"] = win_height
    debug_info["java_server"] = java_server
    debug_info["wechat_path"] = wechat_path
    debug_info["crawl_interval"] = crawl_interval
    debug_info["cwd"] = cwd
    debug_info["debug_count"] = debug_count
    debug_info["latest_date"] = latest_date
    debug_info["first_max_crawl_time"] = first_max_crawl_time
    debug_info["switch_gongzhonghao"] = switch_gongzhonghao
    debug_info["first_pages"] = first_pages

    automator = WechatAutomator()
    try:
        automator.init_window()
    except:
        print("微信未启动或未登陆，请启动微信并扫码登陆后再运行本程序。")
        return
    wechat_id = automator.get_wechat_id()
    print("wechat id {}".format(wechat_id))
    debug_info["wechat_id"] = wechat_id
    debug_info["details"] = []

    while True:
        automator.move_window()
        start_time = int(time.time())
        my_file = Path("gongzhonghao.txt")
        if not my_file.is_file():
            s = "gongzhonghao.txt文件不存在，请创建后再运行"
            debug_info["error_msg"] = s
            print(s)
            time.sleep(60)
            continue
        with open('gongzhonghao.txt', encoding="UTF-8") as f:
            lines = f.read().splitlines()
        print("抓取的公众号列表：")
        for line in lines:
            print("\t{}".format(line))

        if len(lines) == 1 and switch_gongzhonghao is None:
            s = "只有一个公众号要抓取，需要配置 switch_gongzhonghao"
            ctypes.windll.user32.MessageBoxW(0, "请在config.ini配置switch_gongzhonghao或者增加公众号数量", "没有switch_gongzhonghao", 0)
            return
        if len(lines) == 1:
            try:
                automator.locate_user(switch_gongzhonghao)
            except:
                pass
        for line in lines:
            line = line.strip()
            if line == '':
                continue
            details = debug_info["details"]
            detail = []
            details.append(detail)
            # 只保留
            if len(details) > debug_count:
                details = details[-debug_count:]
                debug_info["details"] = details

            try:
                s = "开始抓取: {}".format(line)
                print(s)
                add_to_detail(s, detail)
                send_heart_beat(wechat_id, "start-"+line, java_server)

                articles = []
                # get states from java server
                page = {"pubName": line}
                s = requests.post(java_server + "/getstate", json=page)
                rsp = json.loads(s.text)
                if not rsp["success"]:
                    s = "获取states失败：{}".format(rsp["msg"])
                    add_to_detail(s, detail)
                    print(s)
                    continue
                states = rsp["data"]
                i = 0
                for state in states:
                    i += 1
                    if i < 50:
                        add_to_detail("state: {}".format(state), detail)
                    print(state)
                force_counter = False
                curr_crawl_pages = crawl_pages
                curr_max_pages = max_crawl_pages
                curr_latest_date = None

                if len(states) == 0:
                    s = "首次抓取 {}".format(line)
                    add_to_detail(s, detail)
                    print(s)
                    curr_time = int(time.time())
                    if curr_time - start_time >= first_max_crawl_time:
                        s = "时间太长，跳过首次抓取 {}-{}".format(start_time, curr_time)
                        print(s)
                        add_to_detail(s, detail)
                        try:
                           automator.locate_user(line)
                        except:
                            pass
                        continue

                    curr_max_pages = max(max_crawl_pages, first_pages)
                    curr_latest_date = latest_date

                s = "curr_max: {}, curr_pages: {}".format(curr_max_pages, curr_crawl_pages)
                print(s)
                add_to_detail(s, detail)
                result = automator.crawl_gongzhonghao(line, articles,
                                                      states=states, max_pages=curr_max_pages,
                                                      detail=detail, latest_date=curr_latest_date)
                s = "抓取 {} 成功: {}".format(line, result)
                add_to_detail(s, detail)
                print(s)
                if result:
                    for article in articles:
                        url, _, title, html, _, read_count = article
                        if not url_in_states(url, states):
                            page = {"url": url,
                                    "crawlWechatId": wechat_id,
                                    "title": title,
                                    "pubName": line,
                                    "html": html}
                            s = "addurl: {}".format(page["url"])
                            add_to_detail(s, detail)
                            print(s)
                            s = requests.post(java_server + "/addurl", json=page)
                            res = json.loads(s.text)
                            if not res["success"]:
                                s = "addurl失败：{}".format(res)
                                add_to_detail(s, detail)
                                print(s)
                                continue


            except:
                traceback.print_exc()
            finally:
                send_debug_info(wechat_id, debug_info, java_server)

        while True:
            current_time = int(time.time())
            time_sleep = 3600 * crawl_interval + start_time - current_time
            if time_sleep > 0:
                time.sleep(min(5*60, time_sleep))
                test_id = automator.get_wechat_id()
                succ = test_id == wechat_id
                send_heart_beat(wechat_id, "heart-beat-{}".format(succ), java_server)
            else:
                break




