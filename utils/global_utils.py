# -*- coding: utf-8 -*-
# global_utils.py created by MoMingLog on 28/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-28
【功能描述】
"""
import hashlib
import time


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
