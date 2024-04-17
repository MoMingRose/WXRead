# -*- coding: utf-8 -*-
# common.py created by MoMingLog on 2/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-02
【功能描述】
"""
import re


class CommonException(Exception):
    def __init__(self, msg: str, graphics: str):
        super().__init__(f"{graphics} {msg}")


class PauseReadingAndCheckWait(CommonException):
    def __init__(self, msg: str):
        super().__init__(f"暂停阅读, {msg}", "🟢🔶")


class PauseReadingTurnNext(CommonException):
    def __init__(self, msg: str, graphics: str = None):
        if graphics is None:
            graphics = "🟡"
        else:
            graphics = "🟢🔶"
        super().__init__(f"暂停阅读, {msg}", graphics)


class StopReadingNotExit(CommonException):
    def __init__(self, msg: str):
        super().__init__(f"停止阅读, {msg}", "🟡")


class CookieExpired(CommonException):
    def __init__(self):
        super().__init__("Cookie已过期，请更新!", "🔴")


class RspAPIChanged(CommonException):
    def __init__(self, api: str):
        super().__init__(f"{api} 接口返回数据变化，请更新!", "🔴")


class ExitWithCodeChange(CommonException):
    def __init__(self, prefix=""):
        super().__init__(f"{prefix} 官方貌似更新了源代码，脚本已停止运行!", "🔴")


class Exit(CommonException):
    def __init__(self, msg=None):
        s = f", 原因： {msg}" if msg is not None else ""
        super().__init__(f"出现不可挽回异常{s}, 退出脚本", "🔴")


class FailedPushTooManyTimes(CommonException):
    def __init__(self):
        super().__init__("超过最大推送失败次数，请配置好相关数据!", "🔴")


class NoSuchArticle(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class RegExpError(Exception):
    def __init__(self, reg: str | re.Pattern):
        if isinstance(reg, re.Pattern):
            reg = reg.pattern.__str__()
        super().__init__(f"提取失败! 请通知作者更新下方正则\n> {reg}")
