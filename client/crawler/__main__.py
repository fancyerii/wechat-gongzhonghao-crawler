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

def find_id_in_states(url, states):
    for state in states:
        if url == state['url']:
            return state["id"]
    return None


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
    counter_interval_seconds = int(parser.get('basic', 'counter_interval_seconds', fallback=48*3600))

    crawl_pages = int(parser.get('basic', 'crawl_pages', fallback=3))
    max_crawl_pages = int(parser.get('basic', 'max_crawl_pages', fallback=6))

    debug_count = int(parser.get('basic', "debug_count", fallback="10"))
    latest_date = parser.get('basic', 'latest_date', fallback=None)
    first_pages = int(parser.get('basic', 'first_pages', fallback="1"))
    find_window_timeout = int(parser.get('basic', 'find_window_timeout', fallback='30'))

    first_max_crawl_time = int(parser.get('basic', 'first_max_crawl_time', fallback="86400"))
    switch_gongzhonghao = parser.get('basic', 'switch_gongzhonghao', fallback=None)

    crawl_read_count = parser.get('basic', 'crawl_read_count', fallback="False")
    crawl_read_count = crawl_read_count.lower() == 'true'

    debug_ocr = parser.get('basic', 'debug_ocr', fallback="False")
    debug_ocr = debug_ocr.lower() == 'true'


    print("max_crawl_pages: {}, crawl_pages: {}".format(max_crawl_pages, crawl_pages))
    print("width: {}, height: {}".format(win_width, win_height))
    print("java_server: {}".format(java_server))
    print("wechat_path: {}".format(wechat_path))
    print("crawl_interval: {} hours".format(crawl_interval))
    print("counter_interval: {} seconds".format(counter_interval_seconds))
    print("latest_date: {}".format(latest_date))
    print("first_max_crawl_time: {}".format(first_max_crawl_time))
    print("switch_gongzhonghao: {}".format(switch_gongzhonghao))
    print("first_pages: {}".format(first_pages))
    print("crawl_read_count: {}".format(crawl_read_count))
    print("debug_ocr: {}".format(debug_ocr))
    print("find_window_timeout: {}".format(find_window_timeout))

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
    debug_info["crawl_read_count"] = crawl_read_count
    debug_info["counter_interval_seconds"] = counter_interval_seconds
    debug_info["debug_ocr"] = debug_ocr
    debug_info["find_window_timeout"] = find_window_timeout

    automator = WechatAutomator()
    try:
        automator.init_window(counter_interval=counter_interval_seconds,
                              find_window_timeout=find_window_timeout)
    except:
        print("微信未启动或未登陆，请启动微信并扫码登陆后再运行本程序。")
        return
    wechat_id = automator.get_wechat_id()
    print("wechat id {}".format(wechat_id))
    debug_info["wechat_id"] = wechat_id
    debug_info["details"] = []

    account_is_fuwuhao = {}
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
            is_fuwuhao = account_is_fuwuhao.get(line)
            if is_fuwuhao is None:
                is_fuwuhao = automator.is_fuwuhao(line)
                if is_fuwuhao is None:
                    print("账号{}不能确定是否服务号，请联系开发修复bug".format(line))
                    continue
                account_is_fuwuhao[line] = is_fuwuhao
            s = "{} 是否服务号 {}".format(line, is_fuwuhao)
            print(s)
            details = debug_info["details"]
            detail = []
            detail.append(s)
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

                curr_crawl_pages = crawl_pages
                curr_max_pages = max_crawl_pages
                # 可以通过它是否为None来判断是否首次抓取
                curr_latest_date = None

                is_first_crawl = False
                if len(states) == 0:
                    is_first_crawl = True
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
                if is_fuwuhao:
                    result = automator.crawl_fuwuhao(line, articles,
                                                        states=states, max_pages=curr_max_pages,
                                                        detail=detail, latest_date=curr_latest_date,
                                                        crawl_counter=crawl_read_count,
                                                        debug_ocr=debug_ocr)
                else:
                    result = automator.crawl_dingyuehao(line, articles,
                                                    states=states, max_pages=curr_max_pages,
                                                    detail=detail, latest_date=curr_latest_date,
                                                    crawl_counter=crawl_read_count,
                                                    debug_ocr=debug_ocr)
                s = "抓取 {} 成功: {}".format(line, result)
                add_to_detail(s, detail)
                print(s)
                if result:
                    for article in articles:
                        url, _, title, html, pub_date, counts = article
                        if counts:
                            read_count, star_count, share_count = counts
                        else:
                            read_count, star_count, share_count = -1, -1, -1
                        if not url_in_states(url, states):
                            page = {"url": url,
                                    "crawlWechatId": wechat_id,
                                    "title": title,
                                    "pubName": line,
                                    "readCount": read_count,
                                    "starCount": star_count,
                                    "shareCount": share_count,
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

                if crawl_read_count and not is_first_crawl:
                    results = []
                    if is_fuwuhao:
                        res = automator.crawl_fuwuhao_read_count(line, results, states, detail,
                                                                 max_pages=curr_max_pages, debug_ocr=debug_ocr)
                    else:
                        res = automator.crawl_dingyuehao_read_count(line, results, states, detail,
                                                                max_pages=curr_max_pages, debug_ocr=debug_ocr)
                    s = "抓取 readcount {} 成功: {}".format(line, res)
                    add_to_detail(s, detail)
                    print(s)
                    if res:
                        for item in results:
                            url, _, title, html, pub_date, counts = item
                            read_count, star_count, share_count = counts
                            if read_count <= 0:
                                s = "{} {} no url".format(url, title)
                                print(s)
                                add_to_detail(s, detail)
                                continue

                            page_id = find_id_in_states(url, states)
                            if page_id is None:
                                s = "url {} not found in states".format(url)
                                print(s)
                                add_to_detail(s, detail)
                                continue

                            params = {'wechatId': wechat_id,
                                      'id': page_id,
                                      "state": True,
                                      "read": read_count,
                                      "star": star_count,
                                      "share": share_count
                                      }
                            s = "counter params: {}".format(params)
                            add_to_detail(s, detail)
                            print(s)
                            r = requests.post(java_server + '/updatecounter', json=params)

                            res = json.loads(r.text)
                            if not res["success"]:
                                s = "更新失败: {}".format(res)
                                add_to_detail(s, detail)
                                print(s)

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




