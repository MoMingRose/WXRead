# -*- coding: utf-8 -*-
# read_mm_info.py created by MoMingLog on 6/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-06
【功能描述】

new Env("猫猫阅读信息及提现");

此任务只会打印猫猫用户信息及其阅读情况，并且进行提现操作

统一入口链接：http://9pw4.dsdtew.shop/haobaobao/auth/f5097609e2ff70f696af4c1ed8b3ed4e

如果进不去，可以先运行一下 “read_entry_url.py”，如果青龙任务添加成功，应该称为 “阅读入口”

配置【!!参考文件!!】在 config\mmkk_example.yaml中

提现相关配置在mmkk.yaml中，（第一次没有，请创建或将上方的参考文件重命名）
"""

from script.v2.mmkk_v2 import MMKKV2

if __name__ == '__main__':
    MMKKV2(run_read_task=False)
