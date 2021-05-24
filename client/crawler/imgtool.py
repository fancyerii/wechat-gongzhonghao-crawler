from PIL import ImageGrab, Image
import numpy as np

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


def locate_content_bottom(img_array, debug_fn, bg_color=None):
    if bg_color is None:
        bg_color = [255, 255, 255]
    height, width = img_array.shape[:2]
    col = 10
    has_content = False
    for row in range(100, height-5):
        if np.all(img_array[row, col] == bg_color):
            has_content = True
        else:
            break

    if debug_fn:
        draw_bbox(img_array, (0, row, width-1, row+1), debug_fn + ".png")

    if not has_content:
        return -1



    return row

def locate_read_count(img_array, debug_fn, bottom, bg_color=None):
    if bg_color is None:
        bg_color = [255, 255, 255]

    height, width = img_array.shape[:2]

    for r in range(bottom-1, bottom-MAX_SEARCH_ROW, -1):
        # 找到第一行非全白背景的行，此行内容是
        if not np.all(img_array[r][LEFT_MOST:RIGHT_MOST] == bg_color):
            break

    for r2 in range(r-1, r-MAX_SEARCH_ROW, -1):
        if np.all(img_array[r2][LEFT_MOST:RIGHT_MOST] == bg_color):
            break

    for r3 in range(r2-1, r2-MAX_SEARCH_ROW, -1):
        if not np.all(img_array[r3][LEFT_MOST:RIGHT_MOST] == bg_color):
            break

    for r4 in range(r3-1, r3-MAX_SEARCH_ROW, -1):
        if np.all(img_array[r4][LEFT_MOST:RIGHT_MOST] == bg_color):
            break

    row = (r3 + r4)//2
    # 从右边往左的第一个非白色像素就是阅读数的最后一个数字的最右侧
    for col_end in range(width//2, LEFT_MOST, -1):
        if not np.all(img_array[row, col_end] == bg_color):
            break

    for col_start in range(col_end-1, LEFT_MOST, -1):
        if np.all(img_array[row, col_start] == bg_color):
            break
    if debug_fn:
        draw_bbox(img_array, (col_start, r4, col_end, r3), debug_fn + "-2.png")
    return (col_start + col_end)//2, row

if __name__ == '__main__':
    locate_read_count("tmp2.png", "debug")