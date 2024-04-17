# -*- coding: utf-8 -*-
# global_utils.py created by MoMingLog on 28/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-28
【功能描述】
"""
import hashlib
import re
import time
from datetime import datetime


def timestamp(length=10):
    """
    获取时间戳（13位）
    :param length: 长度，默认为13
    :return: 13位时间戳
    """
    return int(time.time() * 10 ** (length - 10))


def md5(content):
    m = hashlib.md5()
    m.update(content.encode("utf-8"))
    return m.hexdigest()


def get_date(is_fill_chinese=False):
    if is_fill_chinese:
        return time.strftime("%Y年%m月%d日 %H时%M分%S秒", time.localtime())
    return time.strftime("%Y-%m-%d", time.localtime())


def is_date_after_today(date_str):
    """判断传进来的时间是否比今天要靠后"""
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.today().date()
        return parsed_date > today
    except ValueError:
        return False


def hide_dynamic_middle(s, visible_ratio=0.7, mask_char='*'):
    n = len(s)
    # 根据可见比例计算可见字符的总数量
    visible_count = int(n * visible_ratio)

    # 确保至少显示一些字符
    if visible_count < 2:
        visible_count = 2

    # 计算每边显示的字符数
    show_each_side = visible_count // 2

    # 如果可见字符数量是奇数，增加末尾的显示数量
    if visible_count % 2 != 0:
        show_end = show_each_side + 1
    else:
        show_end = show_each_side

    show_start = show_each_side

    # 构建隐藏后的字符串
    if n > visible_count:
        return s[:show_start] + (mask_char * (n - visible_count)) + s[-show_end:]
    else:
        return s


def extract_urls(text):
    # 定义一个正则表达式模式来匹配大部分URL
    url_pattern = r'https?://[\w\-\.]+[\w\-]+[\w\-\./\?\=\&\%]*'
    # 使用findall方法查找所有匹配的URL
    urls = re.findall(url_pattern, text)
    if len(urls) == 1:
        return urls[0]
    else:
        return urls


if __name__ == '__main__':
    print(md5("/index/mob/get_zan_qr.html"))
