# -*- coding: utf-8 -*-
# read_ymz_info.py created by MoMingLog on 18/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-18
【功能描述】
new Env("有米赚");
0 30 7,10,13 * * * read_ymz.py

统一入口链接: http://i3n0nzg2wcvnhzu6opsu.xoa8m3pb4.zhijianzzmm.cn/ttz/wechat/ttzScanCode?userShowId=5332

请确认完整拉库，此脚本的配置不依赖环境变量（为了后序账号数据添加、修改、删除方便一点）

配置【!!参考文件!!】在 config\ ymz_example.yaml中，请先阅读其中的注释内容，把【必填】都填上就可以运行了

实际生效的【配置文件名】为：ymz.yaml（第一次没有，请创建或将上方的参考文件重命名）

参考文件每次拉库都会拉取，注意里面可能会添加新的内容

如果需要其他额外的配置，请详细的阅读对应的注释内容并配置
"""

from script.v2.ymz_v2 import YMZV2

if __name__ == '__main__':
    YMZV2()
