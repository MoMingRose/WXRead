# -*- coding: utf-8 -*-
# read_lt_info.py created by MoMingLog on 6/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-06
【功能描述】
new Env("力天微盟阅读信息及提现");

此任务只会打印力天微盟用户信息及其阅读情况，并且进行提现操作

配置【!!参考文件!!】在 config\ltwm_example.yaml中

提现相关配置在ltwm.yaml中，（第一次没有，请创建或将上方的参考文件重命名）
"""

from script.v2.ltwm_v2 import LTWMV2

if __name__ == '__main__':
    LTWMV2(run_read_task=False)
