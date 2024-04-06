# -*- coding: utf-8 -*-
# klyd.py created by MoMingLog on 30/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-30
【功能描述】
"""

from exception.common import CommonException


class FailedPassDetect(Exception):
    def __init__(self, message: str = "检测未通过，此账号停止运行!"):
        super().__init__(f"{message}")


class WithdrawFailed(CommonException):
    def __init__(self, msg: str):
        super().__init__(f"提现失败, {msg}", "🟡")
