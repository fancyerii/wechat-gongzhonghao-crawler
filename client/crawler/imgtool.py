from PIL import ImageGrab, Image
from collections import Counter
import numpy as np
import re
import pytesseract
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
    return pixel[0] == pixel[1] and pixel[1] == pixel[2] and pixel[0] > 200

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

def extract_read_count(img_array, bottom, debug_fn=None, bg_color=None):
    if bg_color is None:
        bg_color = [255, 255, 255]

    height, width = img_array.shape[:2]

    for r in range(bottom-1, bottom-MAX_SEARCH_ROW, -1):
        # 找到第一行非全白背景的行，此行内容是分享
        if not np.all(img_array[r][LEFT_MOST:RIGHT_MOST] == bg_color):
            break
    if debug_fn:
        draw_bbox(img_array, (0, r, width-1, r+1), debug_fn + "-1.png")

    for r2 in range(r-1, r-MAX_SEARCH_ROW, -1):
        if np.all(img_array[r2][LEFT_MOST:RIGHT_MOST] == bg_color):
            break
    if debug_fn:
        draw_bbox(img_array, (0, r2, width - 1, r2 + 1), debug_fn + "-2.png")

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
    return _extract_count(text)

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


if __name__ == '__main__':
    # locate_read_count("tmp2.png", "debug")
    text = ocr(Image.open("debug-6_locate-5.png"))
    print(text)