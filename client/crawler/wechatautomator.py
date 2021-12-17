import pywinauto
from pywinauto.application import *
from pywinauto import clipboard
import requests
import logging
from datetime import datetime
import time
import traceback
import re
from PIL import Image
import numpy as np
from pywinauto.timings import Timings

import crawler.imgtool as imgtool

logger = logging.getLogger(__name__)

class WechatAutomator:
    def init_window(self, exe_path=r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
                    turn_page_interval=3,
                    click_url_interval=1,
                    counter_interval=48 * 3600,
                    read_count_init_pg_down=5,
                    win_width=1000,
                    win_height=600,
                    find_window_timeout=30):
        app = Application(backend="uia").connect(path=exe_path)
        self.main_win = app.window(title=u"微信", class_name="WeChatMainWndForPC")
        self.main_win.set_focus()
        self.app = app
        self.visible_top = 70
        self.turn_page_interval = turn_page_interval
        self.click_url_interval = click_url_interval
        self.counter_interval = counter_interval
        self.read_count_init_pg_down = read_count_init_pg_down
        self.browser = None
        self.template = None
        try:
            self.template = np.asarray(Image.open("template.png"))
        except:
            print("no template.png")

        self.win_width = win_width
        self.win_height = win_height
        # 为了让移动窗口，同时使用非uia的backend，这是pywinauto的uia的一个bug
        self.app2 = Application().connect(path=exe_path)
        self.move_window()

        Timings.window_find_timeout = find_window_timeout

    def move_window(self):
        self.app2.window(title=u"微信", class_name="WeChatMainWndForPC").move_window(0, 0, width=self.win_width,
                                                                                   height=self.win_height)

    def get_wechat_id(self):
        try:
            text = self.main_win.child_window(title="聊天", control_type="Button")
            btn = text.parent().children()[0]
            self.click_center(btn)

            label = self.main_win.child_window(title="微信号：")
            p = label.parent().children()[1]
            wechat_id = p.element_info.name
            self.click_center(btn)
        except:
            pass

        return wechat_id

    def click_left(self, win=None):
        if win is None:
            rect = self.main_win.rectangle()
        else:
            rect = win.rectangle()
        center = (rect.top + rect.bottom) // 2
        right = rect.left + 10
        self.click((right, center))

    def click_right(self, win=None):
        if win is None:
            rect = self.main_win.rectangle()
        else:
            rect = win.rectangle()
        center = (rect.top + rect.bottom) // 2
        right = rect.right - 10
        self.click((right, center))

    def turn_page_up(self, n, win=None, click=True):
        if click:
            self.click_right(win)
        for i in range(n):
            self.main_win.type_keys("{PGUP}")

    @staticmethod
    def add_to_detail(s, detail):
        detail.append(time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(s))


    @staticmethod
    def get_title(html):
        res = re.search('<h1([^>]+)>(.*)</h1>', html, re.DOTALL|re.MULTILINE)
        if res:
            title = res.group(2)
            title = title.replace("\n", " ").strip()
            return title
        return None

    @staticmethod
    def get_pubdate(html):
        res = re.search('var [^;]*n="([0-9]+)"[^;]*;', html)
        if res:
            timestamp = int(res.group(1))
            dt_object = datetime.fromtimestamp(timestamp)
            return dt_object.strftime("%Y-%m-%d %H:%M:%S")
        else:
            print("can't extract pubdate")
            return None

    @staticmethod
    def url_in_states(url, states):
        for state in states:
            if url == state['url']:
                return True
        return False

    def crawl_fuwuhao_read_count(self, account_name, results, states, detail,
                                    max_pages=12, no_item_retry=3, debug_ocr=False,
                                    locate_user=False):
        if locate_user and not self.locate_user(account_name):
            return False

        need_counter_states = []

        for state in states:
            if state["counterState"] != 0:
                pub_date_epochs = state.get("firstAdd")
                if pub_date_epochs and self.need_crawl_counter(pub_date_epochs):
                    need_counter_states.append(state)
                    s = "need counter state {} {}".format(state["url"], state["title"])
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
        if len(need_counter_states) == 0:
            return True

        browser_win = self.init_fuwuhao_window(max_pages)

        states = need_counter_states
        last_visited_titles = set()
        visited_urls = set()

        pagedown_retry = 0
        last_visited_titles = []

        for page in range(0, max_pages):
            items = []
            date_list = self._analysis_list(browser_win, page, debug_ocr)
            try:
                last_visited_titles = self.process_fwh_page(page, browser_win, date_list, account_name, items, last_visited_titles, states,
                                                    visited_urls, detail, True,
                                                    debug_ocr, counter_only=True)
            except:
                traceback.print_exc()
                s = "counter process_page {} fail".format(page)
                print(s)
                WechatAutomator.add_to_detail(s, detail)

            results.extend(items)

            if len(items) == 0:
                pagedown_retry += 1
                if pagedown_retry >= no_item_retry:
                    s = "break because of retry {}".format(pagedown_retry)
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    break
            else:
                pagedown_retry = 0

            # 判断是否可以结束，条件是states里所有的counter_state为1的都处理过了
            need_continue = False
            for state in states:
                if state["counterState"] != 0 and state["url"] not in visited_urls:
                    need_continue = True
                    break

            if not need_continue:
                s = "break because all states ok"
                logger.debug(s)
                WechatAutomator.add_to_detail(s, detail)
                break

            self.click_left(win=browser_win)
            browser_win.type_keys("{PGDN}")
            time.sleep(self.turn_page_interval)

        browser_win.close()

        return True


    def crawl_dingyuehao_read_count(self, account_name, results, states, detail,
                                    max_pages=12, no_item_retry=3, debug_ocr=False,
                                    locate_user=False):
        if locate_user and not self.locate_user(account_name):
            return False

        need_counter_states = []

        for state in states:
            if state["counterState"] != 0:
                pub_date_epochs = state.get("firstAdd")
                if pub_date_epochs and self.need_crawl_counter(pub_date_epochs):
                    need_counter_states.append(state)
                    s = "need counter state {} {}".format(state["url"], state["title"])
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
        if len(need_counter_states) == 0:
            return True
        states = need_counter_states
        last_visited_titles = set()
        visited_urls = set()
        self.turn_page_up(min(20, max_pages * 2))

        pagedown_retry = 0
        last_visited_titles = []

        for page in range(0, max_pages):
            items = []
            try:
                last_visited_titles = self.process_page(account_name, items, last_visited_titles, states,
                                                    visited_urls, detail, True,
                                                    debug_ocr, counter_only=True)
            except:
                traceback.print_exc()
                s = "counter process_page {} fail".format(page)
                print(s)
                WechatAutomator.add_to_detail(s, detail)

            results.extend(items)

            if len(items) == 0:
                pagedown_retry += 1
                if pagedown_retry >= no_item_retry:
                    s = "break because of retry {}".format(pagedown_retry)
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    break
            else:
                pagedown_retry = 0

            # 判断是否可以结束，条件是states里所有的counter_state为1的都处理过了
            need_continue = False
            for state in states:
                if state["counterState"] != 0 and state["url"] not in visited_urls:
                    need_continue = True
                    break

            if not need_continue:
                s = "break because all states ok"
                logger.debug(s)
                WechatAutomator.add_to_detail(s, detail)
                break

            self.click_right()
            self.main_win.type_keys("{PGDN}")
            time.sleep(self.turn_page_interval)

        self.turn_page_up(page * 2)

        return True

    def _analysis_list(self, browser_win, page, debug_ocr=False):
        if debug_ocr:
            imgtool.snap_shot_to_file(browser_win.rectangle(), "debug_fwh_list_{}.png".format(page))
        date_list = []
        for _ in range(3):
            img_arr = imgtool.snap_shot(browser_win.rectangle())
            debug_file = None
            if debug_ocr:
                debug_file = "debug_fwh_list_{}_locate.png".format(page)
            date_list = imgtool.locate_articles(img_arr, debug_file=debug_file)
            if len(date_list) > 0:
                break
            time.sleep(3)
        return date_list

    def is_fuwuhao(self, account_name):
        old_timeout = Timings.window_find_timeout
        Timings.window_find_timeout = 3
        try:
            if not self.locate_user(account_name, retry=3):
                return None
            btn = self.main_win.child_window(title="聊天信息", control_type="Button")
            btn.rectangle()
            return True
        except:
            return False
        finally:
            Timings.window_find_timeout = old_timeout

    def init_fuwuhao_window(self, max_pages):
        btn = self.main_win.child_window(title="聊天信息", control_type="Button")
        self.click_center(btn)
        sub_win = self.main_win.child_window(title="微信", class_name="ContactProfileWnd")
        btn = sub_win.child_window(title="查看历史消息", control_type="Button")
        WechatAutomator.click_control(btn)

        browser_win = self.app.window(title="微信", class_name="CefWebViewWnd")
        #tree = self.build_tree(browser_win, goto_root=False)
        #self.print_tree(tree)
        time.sleep(3)

        self.click_left(win=browser_win)
        for _ in range(min(20, max_pages * 2)):
            browser_win.type_keys("{PGUP}")

        return browser_win

    def crawl_fuwuhao(self, account_name, articles, states, detail,
                      max_pages=6, latest_date=None, no_item_retry=3,
                      crawl_counter=False, debug_ocr=False):

        if not self.locate_user(account_name):
            return False

        browser_win = self.init_fuwuhao_window(max_pages)

        visited_urls = set()
        pagedown_retry = 0
        last_visited_titles = []
        crawl_read_count = crawl_counter and latest_date is not None

        for page in range(0, max_pages):
            date_list = self._analysis_list(browser_win, page, debug_ocr=debug_ocr)
            items = []
            try:
                last_visited_titles = self.process_fwh_page(page, browser_win, date_list, account_name, items, last_visited_titles, states,
                                                        visited_urls, detail, crawl_read_count,
                                                        debug_ocr, stop_on_url_exist=True)

            except:
                s = "process_page {} fail".format(page)
                print(s)
                WechatAutomator.add_to_detail(s, detail)

            articles.extend(items)

            if len(items) == 0:
                pagedown_retry += 1
                if pagedown_retry >= no_item_retry:
                    s = "break because of retry {}".format(pagedown_retry)
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    break
            else:
                pagedown_retry = 0

            if len(items) > 0 and latest_date is not None:
                pub_date = items[-1][4]
                if pub_date and pub_date < latest_date:
                    s = "stop because {} < {}".format(pub_date, latest_date)
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    break

            # TODO process_page通过stop_on_url_exist已经检查过了，应该增加返回值
            # 这里有重复检查，以后可以优化
            url_exist = False
            for item in items:
                if WechatAutomator.url_in_states(item[0], states):
                    s = "stop because url exist {}".format(item[0])
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    url_exist = True
                    break
            if url_exist:
                break

            self.click_left(win=browser_win)
            browser_win.type_keys("{PGDN}")
            time.sleep(self.turn_page_interval)

        browser_win.close()
        return True

    def crawl_dingyuehao(self, account_name, articles, states, detail,
                         max_pages=6, latest_date=None, no_item_retry=3,
                         crawl_counter=False, debug_ocr=False):
        '''
        抓取一个微信订阅号
        :param account_name:
        :param articles: 抓取的公众号文章 (url, rect, elem.element_info.name, html, pub_date, read_count)
        :param states:
        :param detail:
        :param max_pages:
        :param latest_date: 如果非None表示首次抓取的最老的时间；否则表示非首次抓取
        :param no_item_retry:
        :param crawl_counter: 是否抓取阅读数
        :return:
        '''
        logger.debug(account_name)
        if not self.locate_user(account_name):
            return False
        last_visited_titles = set()
        visited_urls = set()
        self.turn_page_up(min(20, max_pages * 2))

        pagedown_retry = 0
        last_visited_titles = []
        crawl_read_count = crawl_counter and latest_date is not None
        for page in range(0, max_pages):
            items = []
            try:
                last_visited_titles = self.process_page(account_name, items, last_visited_titles, states,
                                                    visited_urls, detail, crawl_read_count,
                                                    debug_ocr, stop_on_url_exist=True)
            except:
                s = "process_page {} fail".format(page)
                print(s)
                WechatAutomator.add_to_detail(s, detail)

            articles.extend(items)

            if len(items) == 0:
                pagedown_retry += 1
                if pagedown_retry >= no_item_retry:
                    s = "break because of retry {}".format(pagedown_retry)
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    break
            else:
                pagedown_retry = 0

            if len(items) > 0 and latest_date is not None:
                pub_date = items[-1][4]
                if pub_date and pub_date < latest_date:
                    s = "stop because {} < {}".format(pub_date, latest_date)
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    break

            # TODO process_page通过stop_on_url_exist已经检查过了，应该增加返回值
            # 这里有重复检查，以后可以优化
            url_exist = False
            for item in items:
                if WechatAutomator.url_in_states(item[0], states):
                    s = "stop because url exist {}".format(item[0])
                    logger.debug(s)
                    WechatAutomator.add_to_detail(s, detail)
                    url_exist = True
                    break
            if url_exist:
                break

            self.click_right()
            self.main_win.type_keys("{PGDN}")
            time.sleep(self.turn_page_interval)

        self.turn_page_up(page * 2)

        return True

    def click_url(self, rect, win_rect, click_up):
        x = (rect.left + rect.right) // 2 - win_rect.left
        if click_up:
            y = rect.top + 5
        else:
            y = rect.bottom - 10

        self.click(coords=(x, y))
        time.sleep(1)
        self.browser = self.app.window(title="微信", class_name="CefWebViewWnd")

    def is_bad_elem(self, elem):
        if elem.element_info.control_type == "Edit":
            return True
        for child in elem.children():
            res = self.is_bad_elem(child)
            if res:
                return True
        return False

    def need_crawl_counter(self, pub_date_epochs):
        current_time = int(time.time())
        return current_time - pub_date_epochs >= self.counter_interval

    def search_state(self, states, url):
        for state in states:
            if state["url"] == url:
                return state
        return None

    def need_click_when_counter(self, title, need_counter_states):
        if title == '图片':
            return True
        for state in need_counter_states:
            if title == state['title']:
                return True
        return False

    def process_fwh_page(self, page, win, date_list, account_name, items, lastpage_clicked_titles, states,
                     visited_urls, detail, need_counter, debug_ocr=False,
                     counter_only=False, stop_on_url_exist=False):
        clicked_titles = set()
        cc = 0
        win_rect = win.rectangle()
        rects = [(rect[0] + win_rect.left, rect[1] + win_rect.top, rect[2], rect[3])
                 for rect in date_list]

        for rect in rects:
            cc += 1
            back_btn_pos = None
            try:
                WechatAutomator.click_rect(rect)
                copy_btn = win.child_window(title="复制链接地址")
                refresh_btn = win.child_window(title="刷新")
                fontsize_btn = win.child_window(title="字体大小")
                r_rect = refresh_btn.rectangle()
                r_center_x = (r_rect.left + r_rect.right) // 2
                r_center_y = (r_rect.top + r_rect.bottom) // 2
                f_rect = fontsize_btn.rectangle()
                f_center_x = (f_rect.left + f_rect.right) // 2
                f_center_y = (f_rect.top + f_rect.bottom) // 2
                back_btn_pos = (2 * r_center_x - f_center_x,
                                2 * r_center_y - f_center_y)

                #win.print_control_identifiers()
                self.click_control(copy_btn)
                url = clipboard.GetData()
                self.browser = win
                elem_title = None
                if url and not url in visited_urls:
                    visited_urls.add(url)
                    html = None
                    pub_date_epochs = None
                    pub_date = None
                    if not counter_only:
                        try:
                            html = requests.get(url).text
                            pub_date = WechatAutomator.get_pubdate(html)
                            elem_title = WechatAutomator.get_title(html)
                            date = datetime.strptime(pub_date, '%Y-%m-%d %H:%M:%S')
                            pub_date_epochs = datetime.timestamp(date)
                        except:
                            s = "fail get {}".format(url)
                            logger.debug(s)
                            WechatAutomator.add_to_detail(s, detail)
                    else:
                        state = self.search_state(states, url)
                        if not state:
                            continue
                        pub_date_epochs = state.get("firstAdd")

                    read_count = None
                    if need_counter and pub_date_epochs and self.need_crawl_counter(pub_date_epochs):
                        if debug_ocr:
                            read_count = self.extract_read_count(True, "debug-"+str(page)+"-"+str(cc))
                        else:
                            read_count = self.extract_read_count(True)

                    if debug_ocr:
                        s = "{} readcount={}".format(elem_title, read_count)
                        print(s)
                        WechatAutomator.add_to_detail(s, detail)

                    items.append((url, rect, elem_title, html, pub_date, read_count))

                if url and stop_on_url_exist:
                    if self.url_in_states(url, states):
                        s = "stop on url {} exist".format(url)
                        logger.debug(s)
                        WechatAutomator.add_to_detail(s, detail)
                        break
            except:
                traceback.print_exc()
            finally:
                self.browser = None
                if back_btn_pos:
                    self.click(coords=back_btn_pos)

        return clicked_titles

    def process_page(self, account_name, items, lastpage_clicked_titles, states,
                     visited_urls, detail, need_counter, debug_ocr=False,
                     counter_only=False, stop_on_url_exist=False):
        '''
        :param account_name: 微信公众名
        :param items: 当前页抓取的list，(url, rect, elem.element_info.name, html, pub_date, read_count)
        :param lastpage_clicked_titles: 上一页点击过的文章名称，避免重复点击
        :param states:
        :param visited_urls: 抓取过的url
        :param detail: debug信息
        :param need_counter: 是否需要抓取阅读数
        :param counter_only: 是否只抓取阅读数
        :return: 返回本页抓取的标题
        '''
        clicked_titles = set()
        text = self.main_win.child_window(title=account_name, control_type="Text", found_index=0)
        parent = text
        while parent:
            parent = parent.parent()
            if '会话列表' == parent.element_info.name:
                break
        paths = [0, 2, 0, 0, 0, 1, 0]
        for idx in paths:
            parent = parent.children()[idx]

        elems = []
        self.recursive_get(parent, elems)
        win_rect = self.main_win.rectangle()
        cc = 0
        for elem in elems:
            cc += 1
            rect = elem.rectangle()
            elem_title = elem.element_info.name
            if elem_title in lastpage_clicked_titles:
                continue

            if rect.top >= win_rect.bottom or rect.bottom <= self.visible_top:
                continue

            visible_height = min(rect.bottom, win_rect.bottom) - max(rect.top, win_rect.top+self.visible_top)
            if visible_height < 10:
                continue

            if rect.bottom - rect.top >= win_rect.bottom - self.visible_top:
                raise RuntimeError("{}-{}>={}-{}".format(rect.bottom, rect.top,
                                                         win_rect.bottom, self.visible_top))


            if rect.bottom >= win_rect.bottom:
                click_up = True
            else:
                click_up = False
            if self.is_bad_elem(elem):
                s = "not good elem {}".format(elem_title[0:10])
                logger.debug(s)
                WechatAutomator.add_to_detail(s, detail)
                continue

            if counter_only and not self.need_click_when_counter(elem_title, states):
                print("counter skip {}".format(elem_title))
                continue

            try:
                self.click_url(rect, win_rect, click_up)
                copy_btn = self.browser.child_window(title="复制链接地址")
                for _ in range(3):
                    try:
                        self.click_center(copy_btn, click_main=False)
                        url = clipboard.GetData()
                        break
                    except:
                        print("retry get url")
                        time.sleep(1)

                if elem.element_info.name != '图片':
                    clicked_titles.add(elem.element_info.name)

                if url and not url in visited_urls:
                    visited_urls.add(url)
                    html = None
                    pub_date_epochs = None
                    pub_date = None
                    if not counter_only:
                        try:
                            html = requests.get(url).text
                            pub_date = WechatAutomator.get_pubdate(html)

                            date = datetime.strptime(pub_date, '%Y-%m-%d %H:%M:%S')
                            pub_date_epochs = datetime.timestamp(date)
                        except:
                            s = "fail get {}".format(url)
                            logger.debug(s)
                            WechatAutomator.add_to_detail(s, detail)
                    else:
                        state = self.search_state(states, url)
                        if not state:
                            continue
                        pub_date_epochs = state.get("firstAdd")

                    read_count = None
                    if need_counter and pub_date_epochs and self.need_crawl_counter(pub_date_epochs):
                        if debug_ocr:
                            read_count = self.extract_read_count(False, "debug-"+str(cc))
                        else:
                            read_count = self.extract_read_count(False)

                    if debug_ocr:
                        s = "{} readcount={}".format(elem_title, read_count)
                        print(s)
                        WechatAutomator.add_to_detail(s, detail)

                    items.append((url, rect, elem_title, html, pub_date, read_count))

                if url and stop_on_url_exist:
                    if self.url_in_states(url, states):
                        s = "stop on url {} exist".format(url)
                        logger.debug(s)
                        WechatAutomator.add_to_detail(s, detail)
                        break

            except:
                traceback.print_exc()
                pass
            finally:
                if self.browser:
                    try:
                        self.browser.close()
                    except:
                        pass
                    self.browser = None

            time.sleep(self.click_url_interval)

        return clicked_titles

    def extract_read_count(self, is_fuwuhao, fn=None):
        self.browser_page_down(50)
        start_row = None
        comment_bg = None
        # 初步定位
        for i in range(30):
            img_array = imgtool.snap_shot(self.browser.rectangle())
            if start_row is None:
                start_row = imgtool.locate_start_row(img_array, fn)
            if comment_bg is None:
                comment_bg = imgtool.get_comment_bg(img_array)
                if fn:
                    print("comment bg color: {}".format(comment_bg))

            if fn:
                bottom = imgtool.locate_content_bottom(img_array, start_row, fn+"_coarse_"+str(i),
                                                       bg_color2=comment_bg)
            else:
                bottom = imgtool.locate_content_bottom(img_array, start_row,
                                                       bg_color2=comment_bg)
            if bottom == -1:
                self.browser_key(1, "{PGUP}")
            else:
                break
        # 没找到
        if bottom == -1:
            s = "无法定位背景"
            print(s)
            return -1, -1, -1

        height, width = img_array.shape[:2]
        content_height = height - self.visible_top
        # 精确定位
        found = False
        for i in range(20):
            # 太靠上，使用UP键往下一点
            # UP键的作用是往下
            if bottom - self.visible_top < 120:
                self.browser_key(1, "{UP}")
                img_array = imgtool.snap_shot(self.browser.rectangle())
                if fn:
                    bottom = imgtool.locate_content_bottom(img_array, start_row, fn+"_fine_"+str(i),
                                                           bg_color2=comment_bg)
                else:
                    bottom = imgtool.locate_content_bottom(img_array, start_row,
                                                           bg_color2=comment_bg)
            elif bottom > height - 10:
                self.browser_key(1, "{DOWN}")
                img_array = imgtool.snap_shot(self.browser.rectangle())
                if fn:
                    bottom = imgtool.locate_content_bottom(img_array, start_row, fn + "_fine_" + str(i),
                                                           bg_color2=comment_bg)
                else:
                    bottom = imgtool.locate_content_bottom(img_array, start_row,
                                                           bg_color2=comment_bg)
            else:
                found = True
                break

        if not found:
            return -1, -1, -1
        if fn:
            count, template = imgtool.extract_counts(is_fuwuhao, img_array, bottom, fn + "_locate",
                                           template_img=self.template)
        else:
            count, template = imgtool.extract_counts(is_fuwuhao, img_array, bottom,
                                                     template_img=self.template)
        if self.template is None and template is not None:
            self.template = template
            Image.fromarray(template).save("template.png")

        return count

    def print_tree(self, tree, level=0):
        print(" "*level, end="")
        print(tree["name"])
        for child in tree["children"]:
            self.print_tree(child, level + 1)

    def build_tree(self, win, goto_root=True):
        if goto_root:
            text = win
            parent = text
            root = parent
            while parent:
                root = parent
                parent = parent.parent()
        else:
            root = win

        return self.recur_build_tree(root)

    def recur_build_tree(self, node):
        root = {"name": node.element_info.name,
                "type": node.element_info.control_type,
                "rect": node.element_info.rectangle,
                "children": []}
        for child in node.children():
            root["children"].append(self.recur_build_tree(child))
        return root

    def recursive_get(self, elem, results):
        if elem.element_info.name:
            if str(elem.element_info.control_type) == 'Pane' \
                    and elem.element_info.name != '会话列表':
                results.append(elem)
        idx = 0
        for child in elem.children():
            self.recursive_get(child, results)
            idx += 1

    def click(self, coords):
        pywinauto.mouse.move((coords[0], coords[1]))
        pywinauto.mouse.click(coords=(coords[0], coords[1]))

    def double_click(self, coords):
        pywinauto.mouse.move((coords[0], coords[1]))
        pywinauto.mouse.double_click(coords=(coords[0], coords[1]))

    @staticmethod
    def click_rect(rect):
        x, y, w, h = rect
        xx = x + w // 2
        yy = y + h // 2
        pywinauto.mouse.move((xx, yy))
        pywinauto.mouse.click(coords=(xx, yy))

    @staticmethod
    def click_control(control):
        coords = control.rectangle()
        x = (coords.left + coords.right) // 2
        y = (coords.top + coords.bottom) // 2
        pywinauto.mouse.move((x, y))
        pywinauto.mouse.click(coords=(x, y))

    def click_center(self, control, click_main=True):
        coords = control.rectangle()
        if click_main:
            win_rect = self.main_win.rectangle()
            x = (coords.left + coords.right) // 2 - win_rect.left
            y = (coords.top + coords.bottom) // 2 - win_rect.top
            self.main_win.click_input(coords=(x, y))
        else:
            win_rect = self.browser.rectangle()
            self.browser.click_input(coords=((coords.left + coords.right) // 2 - win_rect.left,
                                             (coords.top + coords.bottom) // 2 - win_rect.top))

    def browser_page_down(self, pages, sleep_time=0):
        rect = self.browser.rectangle()
        x = rect.left + 10
        y = (rect.top + rect.bottom) // 2

        pywinauto.mouse.move((x, y))
        pywinauto.mouse.click(coords=(x, y))
        for _ in range(pages):
            self.browser.type_keys("{PGDN}")
            if sleep_time > 0:
                time.sleep(sleep_time)


    def browser_key(self, pages, key, sleep_time=0):
        rect = self.browser.rectangle()
        x = rect.left + 10
        y = (rect.top + rect.bottom) //2

        pywinauto.mouse.move((x, y))
        pywinauto.mouse.click(coords=(x, y))
        for _ in range(pages):
            self.browser.type_keys(key)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def locate_user(self, user, retry=5):
        if not self.main_win:
            raise RuntimeError("you should call init_window first")

        search_btn = self.main_win.child_window(title="搜索", control_type="Edit")
        self.click_center(search_btn)

        self.main_win.type_keys("^a")
        self.main_win.type_keys("{BACKSPACE}")
        self.main_win.type_keys(user)
        for i in range(retry):
            time.sleep(1)
            try:
                search_list = self.main_win.child_window(title="搜索结果")
                match_result = search_list.child_window(title=user, control_type="ListItem")
                self.click_center(match_result)
                return True
            except:
                pass

        return False


if __name__ == '__main__':
    automator = WechatAutomator()
    automator.init_window(counter_interval=1)
    msgs = []
    articles = []
    #states = [{'url': 'https://mp.weixin.qq.com/s/e7EJ2URIvuEXkLweRMNKLg'}]
    states = []
    #result = automator.crawl_fuwuhao("法物流通处", articles, max_pages=2, states=states,
    #                                   detail=[], latest_date="2021-01-01", crawl_counter=True,
    #                                   debug_ocr=True)
    #print(result)
    result = automator.crawl_dingyuehao("新智元", articles, max_pages=3, states=states,
                                         detail=[], latest_date="2021-05-04", crawl_counter=True,
                                         debug_ocr=False)
    # print(result)
    for article in articles:
        url, _, title, html, pub_date, read_count = article
        print(title, pub_date, read_count)


    # accounts = ["华为终端客户服务", "法物流通处", "北京动物园", "中国农业博物馆", "足球联赛"]
    # for acc in accounts:
    #     res = automator.is_fuwuhao(acc)
    #     print("{} 是否服务号: {}", acc, res)