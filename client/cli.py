import ctypes
import configparser
from crawler.__main__ import main
from crawler.imgtool import ocr
from PIL import Image
import os

def has_admin():
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    return is_admin

if __name__ == '__main__':
    if not os.path.isfile("config.ini"):
        ctypes.windll.user32.MessageBoxW(0, "当前目录下没有config.ini", "配置文件不存在", 0)
        exit(-1)

    parser = configparser.ConfigParser()
    parser.read('config.ini', encoding="UTF-8")

    test_ocr = parser.get('basic', 'test_ocr', fallback='False')
    test_ocr = test_ocr.lower() == 'true'
    if test_ocr:
        if not os.path.isfile("test.png"):
            ctypes.windll.user32.MessageBoxW(0, "当前目录下没有test.png", "测试文件不存在", 0)
            exit(-1)
        text = ocr(Image.open("test.png"))
        ctypes.windll.user32.MessageBoxW(0, text, "识别结果", 0)
        exit(0)

    lock_input = parser.get('basic', 'lock_input', fallback='False')
    print("lock input {}".format(lock_input))
    is_admin = has_admin()
    print("is_admin {}".format(is_admin))
    if lock_input.lower() == 'true':
        if not is_admin:
            ctypes.windll.user32.MessageBoxW(0, "请以管理员运行程序或者关掉lock_input", "没有权限", 0)
        else:
            BlockInput = ctypes.windll.user32.BlockInput
            BlockInput.argtypes = [ctypes.wintypes.BOOL]
            BlockInput.restype = ctypes.wintypes.BOOL

            blocked = BlockInput(True)
            if blocked:
                try:
                    main(parser)
                except:
                    print("except")
                finally:
                    unblocked = BlockInput(False)  # unblock in any case
            else:
                ctypes.windll.user32.MessageBoxW(0, "请联系开发人员处理", "锁定输入失败", 0)
    else:
        main(parser)

