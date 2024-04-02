# -*- coding: utf-8 -*-
# common.py created by MoMingLog on 2/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-02
【功能描述】
"""


class PauseReadingWaitNext(Exception):
    def __init__(self, msg: str):
        super().__init__(f"暂停阅读, {msg}")


class StopReadingNotExit(Exception):
    def __init__(self, msg: str):
        super().__init__(f"停止阅读, {msg}")


class CookieExpired(Exception):
    def __init__(self):
        super().__init__("🔴 Cookie已过期，请更新!")


class RspAPIChanged(Exception):
    def __init__(self, api: str):
        super().__init__(f"🔴 {api} 接口返回数据变化，请更新!")


class ExitWithCodeChange(Exception):
    def __init__(self, prefix=""):
        super().__init__(f"🔴 {prefix} 官方貌似更新了源代码，脚本已停止运行!")


class Exit(Exception):
    def __init__(self):
        super().__init__("🔴 出现不可挽回异常，退出脚本")
