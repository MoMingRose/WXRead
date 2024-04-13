# -*- coding: utf-8 -*-
# read_xyy_info.py created by MoMingLog on 13/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-13
【功能描述】
new Env("小阅阅阅读信息及提现");

此任务只会打印小阅阅用户信息及其阅读情况，并且进行提现操作

配置【!!参考文件!!】在 config\ xyy_example.yaml中

提现相关配置在xyy.yaml中，（第一次没有，请创建或将上方的参考文件重命名）

"""

from script.v2.xyy_v2 import XYYV2

if __name__ == '__main__':
    XYYV2(run_read_task=False)
