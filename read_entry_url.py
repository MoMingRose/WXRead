# -*- coding: utf-8 -*-
# read_entry_url.py created by MoMingLog on 3/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-03
【功能描述】
new Env('阅读入口');
0 0 6 * * * read_entry_url.py

用来获取所有的入口链接，目前已适配的平台如下：
- 小阅阅
- 猫猫看看
- 可乐读书
- 鱼儿阅读
"""

from utils.entry_utils import EntryUrl

if __name__ == '__main__':
    all_entry_url = EntryUrl.get_all_entry_url(is_flag=True)
    msg_list = []
    for entry_name, entry_url in all_entry_url.items():
        if isinstance(entry_url, list):
            msg_list.append(f"【{entry_name}】")
            for url in entry_url:
                if isinstance(url, tuple):
                    msg_list.append(f"> {url[0]} >> {url[1]}")
                else:
                    msg_list.append(f"> {url}")
        else:
            msg_list.append(f"【{entry_name}】\n> {entry_url}")

    try:
        # 采用青龙面板拉库成功时自动添加的notify.py文件中的方法
        from notify import send

        send("\n".join(msg_list))
    except Exception as e:
        print("\n".join(msg_list))
