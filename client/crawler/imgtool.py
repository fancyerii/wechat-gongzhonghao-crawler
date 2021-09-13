from PIL import ImageGrab, Image
from collections import Counter
import numpy as np
import re
import pytesseract
import cv2
from imutils.contours import sort_contours
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract"


def snap_shot_to_file(rect, file):
    pic = ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom))
    pic.save(file)

def snap_shot(rect):
    return np.asarray(ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom)))


def draw_bbox(img_array, bbox, out_img):
    #img_array = np.asarray(Image.open(img))
    height, width = img_array.shape[:2]
    left, top, right, bottom = bbox
    right = min(right, width - 1)
    bottom = min(bottom, height - 1)
    region_img = np.zeros((height, width, 3), dtype="uint8")
    for row in range(height):
        for col in range(width):
            region_img[row][col] = img_array[row][col]
    # 画线
    for col in range(left, right):
        region_img[top][col] = (255, 0, 0)
        region_img[bottom][col] = (255, 0, 0)
    for row in range(top, bottom):
        region_img[row][left] = (255, 0, 0)
        region_img[row][right] = (255, 0, 0)

    Image.fromarray(region_img).save(out_img)

LEFT_MOST = 20
RIGHT_MOST = -20
MAX_SEARCH_ROW = 100

def _is_possible_bg(pixel):
    return pixel[0] == pixel[1] and pixel[1] == pixel[2] and pixel[0] > 200\
           and pixel[0] != 255

def get_comment_bg(img_array):
    height, width = img_array.shape[:2]
    col = 10
    counter = Counter()
    for row in range(height-50, height-5):
        if _is_possible_bg(img_array[row][col]):
            counter[tuple(img_array[row][col])] += 1

    top = counter.most_common(1)
    if top:
        return top[0][0]
    else:
        return None

def locate_start_row(img_array, debug_fn=None, bg_color=None):
    if bg_color is None:
        bg_color = [255, 255, 255]
    height, width = img_array.shape[:2]
    col = 10
    found = False
    for row in range(5, height-5):
        if not np.all(img_array[row, col] == bg_color):
            found = True
            break
    if not found:
        return 200

    row += 5

    if debug_fn:
        draw_bbox(img_array, (0, row, width-1, row+1), debug_fn + "-start-row.png")
    return row

def locate_content_bottom(img_array, start_row, debug_fn=None, bg_color=None, bg_color2=None):
    if bg_color is None:
        bg_color = [255, 255, 255]
    if bg_color2 is None:
        bg_color2 = [242, 242, 242]
    height, width = img_array.shape[:2]
    col = 10
    has_content = False
    for row in range(start_row, height-5):
        if np.all(img_array[row, col] == bg_color):
            has_content = True
        elif np.all(img_array[row, col] == bg_color2):
            break

    if debug_fn:
        draw_bbox(img_array, (0, row, width-1, row+1), debug_fn + ".png")

    if not has_content:
        return -1

    return row

def ocr(img):
    options = "-l {} --psm {}".format("chi_sim", "7")
    text = pytesseract.image_to_string(img, config=options)
    return text

def _extract_template(img, thrshold=200, kernel=12, debug_fn=None):
    bgr_img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    ret, thresh1 = cv2.threshold(gray, thrshold, 255, cv2.THRESH_BINARY_INV)
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel, kernel))

    # Appplying dilation on the threshold image
    dilation = cv2.dilate(thresh1, rect_kernel, iterations=1)

    # Finding contours
    contours, hierarchy = cv2.findContours(dilation, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_NONE)
    contours = sort_contours(contours, method="left-to-right")[0]
    template = None
    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)
        if debug_fn:
            cv2.rectangle(bgr_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
        region = img[y:y+h, x:x+w]
        text = _clear_text(ocr(region))
        if debug_fn:
            print(text)
        if '分享' in text:
            if i > 0:
                prev_region = contours[i - 1]
            else:
                prev_region = contours[i]
            x_prev, y_prev, w_prev, h_prev = cv2.boundingRect(prev_region)
            y_min = min(y, y_prev)
            y_max = max(y + h, y_prev + h_prev)
            x_min = x_prev
            x_max = x + w
            template = img[y_min:y_max, x_min:x_max]
            print("x, {}:{}; y, {}:{}".format(x_min, x_max, y_min, y_max))
            loc_x, loc_y = find_img(img, template, reverse=True)
            print("loc_x={}, loc_y={}".format(loc_x, loc_y))
            break
    if debug_fn:
        cv2.imwrite(debug_fn+"-template.png", bgr_img)
    return template

def find_img(large_array, small_array, reverse=False,
             start_x=None, end_x=None, start_y=None, end_y=None):
    """
    在大图(large_array)中搜索小图(small_array)的位置，精确的像素级匹配
    :param large_array: 待搜索的大图的numpyarray
    :param small_array: 被搜索的小图的numpyarray
    :param reverse: 是否从后(右下往左上)往前搜索
    :param start_x: 搜索大图的x(width)坐标的起点(包括)
    :param end_x: 搜索大图的x坐标的终点(不包含)
    :param start_y: 搜索大图的y坐标的起点(包括)
    :param end_y: 搜索大图的y坐标的终点(不包含)
    :return: (x, y) tuple，找到的坐标(width, height)。如果找不到
    返回(-1, -1)
    """
    small_height, small_width = small_array.shape[:2]
    large_height, large_width = large_array.shape[:2]
    search_end_x = large_width - small_width + 1
    search_end_y = large_height - small_height + 1
    if end_x is not None and end_x <= large_width:
        search_end_x = end_x - small_width + 1
    if end_y is not None and end_y <= large_height:
        search_end_y = end_y - small_height + 1

    search_start_x = 0 if start_x is None else start_x
    search_start_y = 0 if start_y is None else start_y

    if reverse:
        for x in range(search_end_x - 1, search_start_x - 1, -1):
            for y in range(search_end_y - 1, search_start_y - 1, -1):
                x2 = x + small_width
                y2 = y + small_height
                pic = large_array[y:y2, x:x2]
                test = (pic == small_array)
                if test.all():
                    return x, y
    else:
        for x in range(search_start_x, search_end_x):
            for y in range(search_start_y, search_end_y):
                x2 = x + small_width
                y2 = y + small_height
                pic = large_array[y:y2, x:x2]
                test = (pic == small_array)
                if test.all():
                    return x, y
    return -1, -1

def _process_share_template(img_array, template_img, bottom, debug_fn):
    if debug_fn:
        print("模板抽取服务号")
    try:
        x, y = find_img(img_array, template_img, reverse=False)
    except:
        Image.fromarray(img_array).save("err1.png")
        Image.fromarray(template_img).save("err2.png")
        x, y = -1, -1
    if x == -1:
        if debug_fn:
            Image.fromarray(img_array).save(debug_fn+"-large.png")
            Image.fromarray(template_img).save(debug_fn + "-small.png")
        return -1, None
    h, _ = template_img.shape[:2]
    _, w = img_array.shape[:2]
    if debug_fn:
        draw_bbox(img_array, (x, y, x+w, y+h), debug_fn + "-1-1.png")
    return y, img_array[y:y+h, x:x+w]

def _process_share_without_template(img_array, bottom, bg_color, debug_fn, width,
                                    ext_template):
    if debug_fn:
        print("无模板抽取分享")
    for r in range(bottom - 1, bottom - MAX_SEARCH_ROW, -1):
        # 找到第一行非全白背景的行，此行内容是分享
        if not np.all(img_array[r][LEFT_MOST:RIGHT_MOST] == bg_color):
            break
    if debug_fn:
        draw_bbox(img_array, (0, r, width - 1, r + 1), debug_fn + "-1.png")

    for r2 in range(r - 1, r - MAX_SEARCH_ROW, -1):
        if np.all(img_array[r2][LEFT_MOST:RIGHT_MOST] == bg_color):
            break
    if debug_fn:
        draw_bbox(img_array, (0, r2, width - 1, r2 + 1), debug_fn + "-2.png")

    # r2-r是分享行
    share_arr = img_array[r2:r, :]
    share_img = Image.fromarray(share_arr)
    if ext_template:
        template_img = _extract_template(share_arr, debug_fn=debug_fn)
    else:
        template_img = None
    if debug_fn and template_img is not None:
        share_img.save(debug_fn + "-2-2.png")
        x, y = find_img(img_array, template_img, reverse=True)
        print("x={}, y={}".format(x, y))

    return r2, template_img, share_img

def extract_counts(is_fuwuhao, img_array, bottom, debug_fn=None, bg_color=None,
                   template_img=None):
    if bg_color is None:
        bg_color = [255, 255, 255]

    height, width = img_array.shape[:2]

    if not is_fuwuhao or template_img is None:
        r2, template_img, share_img = _process_share_without_template(img_array, bottom,
                                                                      bg_color, debug_fn,
                                                                      width, is_fuwuhao)
    else:
        # 服务号并且template不为空
        r2, share_img = _process_share_template(img_array, template_img, bottom, debug_fn)

        if r2 == -1:
            if debug_fn:
                print("can't find by template!!!")
            r2, template_img, share_img = _process_share_without_template(img_array, bottom,
                                                                          bg_color, debug_fn,
                                                                          width, False)

    text = ocr(share_img)
    star, share = _extract_share(text)
    for r3 in range(r2-1, r2-MAX_SEARCH_ROW, -1):
        if not np.all(img_array[r3][LEFT_MOST:RIGHT_MOST] == bg_color):
            break
    if debug_fn:
        draw_bbox(img_array, (0, r3, width - 1, r3 + 1), debug_fn + "-3.png")

    for r4 in range(r3-1, r3-MAX_SEARCH_ROW, -1):
        if np.all(img_array[r4][LEFT_MOST:RIGHT_MOST] == bg_color):
            break
    if debug_fn:
        draw_bbox(img_array, (0, r4, width - 1, r4 + 1), debug_fn + "-4.png")

    read_count_img = Image.fromarray(img_array[r4-5:r3+5, :])
    if debug_fn:
        read_count_img.save(debug_fn + "-5.png")
    text = ocr(read_count_img)
    return (_extract_count(text), star, share), template_img

def _extract_share(s):
    if s is None:
        return -1, -1
    star, share = -1, -1
    try:
        res = re.search('赞([0-9.]+)万+', s)
        if res:
            star = int(10000 * float(res.group(1)))
        else:
            res = re.search('赞([0-9]+)', s)
            if res:
                star = int(res.group(1))

        res = re.search('在看([0-9.]+)万+', s)
        if res:
            share = int(10000 * float(res.group(1)))
        else:
            res = re.search('在看([0-9]+)', s)
            if res:
                share = int(res.group(1))
    except:
        pass

    if star == -1 or share == -1:
        res = re.search("([0-9]+万?)[^0-9万]+([0-9]+万?)", s)
        if res:
            first = res.group(1)
            second = res.group(2)
            if first[-1] == '万':
                first = int(first[:-1]) * 10000
            else:
                first = int(first)

            if second[-1] == '万':
                second = int(second[:-1]) * 10000
            else:
                second = int(second)
            # check match
            match = True
            if star != -1 and star != first:
                match = False
            if share != -1 and share != second:
                match = False
            if match:
                star = first
                share = second
    return star, share



def _extract_count(s):
    if s is None:
        return -1
    if "阅读" not in s and "观看" not in s:
        return -1
    try:
        res = re.search('([0-9.]+)万+', s)
        if res:
            return int(10000*float(res.group(1)))
        else:
            res = re.search('([0-9]+)', s)
            return int(res.group(1))
    except:
        return -1

def _is_date(text):
    res = re.match('[0-9]+年[0-9]+月[0-9]+日', text)
    return res is not None

def _clear_text(text):
    text = text.replace("\f", "").replace("\n", "")
    return text

def locate_articles(pil_img_array, kernel=12, thrshold=200, x_max=50,
                    debug_file=None):
    img = cv2.cvtColor(pil_img_array, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, thresh1 = cv2.threshold(gray, thrshold, 255, cv2.THRESH_BINARY_INV)
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel, kernel))

    # Appplying dilation on the threshold image
    dilation = cv2.dilate(thresh1, rect_kernel, iterations=1)

    # Finding contours
    contours, hierarchy = cv2.findContours(dilation, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_NONE)
    if debug_file:
        copy = img.copy()
    contours = sort_contours(contours, method="top-to-bottom")[0]
    date_list = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if x < x_max and w > 20:
            region = Image.fromarray(pil_img_array[y:y+h, x:x+w])
            text = _clear_text(ocr(region))
            if not _is_date(text):
                continue
            date_list.append((x, y, w, h))

    if debug_file:
        for (x, y, w, h) in date_list:
            cv2.rectangle(copy, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imwrite(debug_file, copy)

    return date_list


if __name__ == '__main__':
    #locate_read_count("tmp2.png", "debug")
    #_extract_template(np.asarray(Image.open("debug-1-1_locate-2-2.png")))
    #locate_articles(np.asarray(Image.open("d.png")), debug_file="debug_article.png")
    large = np.asarray(Image.open("../err1.png"))
    small = np.asarray(Image.open("../err2.png"))
    x, y = find_img(large, small, reverse=False, end_y=669)
    print(x, y)