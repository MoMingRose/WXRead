# -*- coding: utf-8 -*-
# read_lt.py created by MoMingLog on 5/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-05
【功能描述】

new Env("力天微盟");
0 0 7-23 * * * read_lt.py

统一入口链接：http://e9adf325c38844188a2f0aefaabb5e0d.op20skd.toptomo.cn/?fid=12286

或者可以在TG通知群里扫我的邀请二维码犒劳一下作者

请确认完整拉库，此脚本的配置不依赖环境变量（为了后序账号cookie添加、修改、删除方便一点）

配置【!!参考文件!!】在 config\ltwm_example.yaml中，请先阅读其中的注释内容，把【必填】都填上就可以运行了

实际生效的【配置文件名】为：ltwm.yaml（第一次没有，请创建或将上方的参考文件重命名）

参考文件每次拉库都会拉取，注意里面可能会添加新的内容（我也会尽量在已有的ltwm.yaml自动化添加）

如果需要其他额外的配置，请详细的阅读对应的注释内容并配置

！！！不熟练的先拿小号测试！！！

"""

from script.v2.ltwm_v2 import LTWMV2

if __name__ == '__main__':
    LTWMV2()
