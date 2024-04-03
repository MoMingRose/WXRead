# -*- coding: utf-8 -*-
# klyd.py created by MoMingLog on 30/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-30
【功能描述】
"""
import re


class FailedPassDetect(Exception):
    def __init__(self, message: str = "检测未通过，此账号停止运行!"):
        super().__init__(f"{message}")


class RegExpError(Exception):
    def __init__(self, reg: str | re.Pattern):
        if isinstance(reg, re.Pattern):
            reg = reg.pattern.__str__()
        super().__init__(f"下方正则需改动\n> {reg}")


class WithdrawFailed(Exception):
    def __init__(self, msg: str):
        super().__init__(f"提现失败, {msg}")
