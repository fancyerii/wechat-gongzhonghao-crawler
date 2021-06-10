import pywinauto
from pywinauto.application import *
from pywinauto import clipboard
import requests
import logging
from datetime import datetime
import time
import traceback
import re

import crawler.imgtool as imgtool

logger = logging.getLogger(__name__)

class WechatAutomator:
    def init_window(self, exe_path=r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
                    turn_page_interval=3,
                    click_url_interval=1,
                    counter_interval=48 * 3600,
                    read_count_init_pg_down=5,
                    win_width=1000,
                    win_height=600):
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
        self.win_width = win_width
        self.win_height = win_height
        # 为了让移动窗口，同时使用非uia的backend，这是pywinauto的uia的一个bug
        self.app2 = Application().connect(path=exe_path)
        self.move_window()

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

    def click_right(self, win=None):
        if win is None:
            rect = self.main_win.rectangle()
        else:
            rect = win.rectangle()
        center = (rect.top + rect.bottom) // 2
        right = rect.right - 10
        self.click((right, center))

    def turn_page_up(self, n):
        self.click_right()
        for i in range(n):
            self.main_win.type_keys("{PGUP}")

    @staticmethod
    def add_to_detail(s, detail):
        detail.append(time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(s))

    @staticmethod
    def get_pubdate(html):
        res = re.search('var t="([0-9]+)",n="([0-9]+)",i="[^;]+";', html)
        if res:
            timestamp = int(res.group(2))
            dt_object = datetime.fromtimestamp(timestamp)
            return dt_object.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return None

    @staticmethod
    def url_in_states(url, states):
        for state in states:
            if url == state['url']:
                return True
        return False

    def crawl_read_count(self, account_name, results, states, detail,
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
            last_visited_titles = self.process_page(account_name, items, last_visited_titles, states,
                                                    visited_urls, detail, True,
                                                    debug_ocr, counter_only=True)
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


    def crawl_gongzhonghao(self, account_name, articles, states, detail,
                           max_pages=6, latest_date=None, no_item_retry=3,
                           crawl_counter=False, debug_ocr=False):
        '''
        抓取一个微信公众号
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
            last_visited_titles = self.process_page(account_name, items, last_visited_titles, states,
                                                    visited_urls, detail, crawl_read_count,
                                                    debug_ocr, stop_on_url_exist=True)
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
                self.click_center(copy_btn, click_main=False)
                url = clipboard.GetData()
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
                            read_count = self.extract_read_count("debug-"+str(cc))
                        else:
                            read_count = self.extract_read_count()

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

    def extract_read_count(self, fn=None):
        self.browser_page_down(30)
        # 初步定位
        for i in range(20):
            img_array = imgtool.snap_shot(self.browser.rectangle())
            if fn:
                bottom = imgtool.locate_content_bottom(img_array, fn+"_coarse_"+str(i))
            else:
                bottom = imgtool.locate_content_bottom(img_array)
            if bottom == -1:
                self.browser_key(1, "{PGUP}")
            else:
                break
        # 没找到
        if bottom == -1:
            return None

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
                    bottom = imgtool.locate_content_bottom(img_array, fn+"_fine_"+str(i))
                else:
                    bottom = imgtool.locate_content_bottom(img_array)
            elif bottom > height - 50:
                self.browser_key(1, "{DOWN}")
                img_array = imgtool.snap_shot(self.browser.rectangle())
                if fn:
                    bottom = imgtool.locate_content_bottom(img_array, fn + "_fine_" + str(i))
                else:
                    bottom = imgtool.locate_content_bottom(img_array)
            else:
                found = True
                break

        if not found:
            return -1
        if fn:
            count = imgtool.extract_read_count(img_array, bottom, fn+"_locate")
        else:
            count = imgtool.extract_read_count(img_array, bottom)
        return count


    def build_tree(self, win):
        text = win
        parent = text
        root = parent
        while parent:
            root = parent
            parent = parent.parent()

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
        y = (rect.top + rect.bottom) //2

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
    result = automator.crawl_gongzhonghao("新智元", articles, max_pages=5, states=states,
                                          detail=[], latest_date="2021-05-04", crawl_counter=True,
                                          debug_ocr=True)
    print(result)
    for article in articles:
        url, _, title, html, pub_date, read_count = article
        print(title, pub_date, read_count)

