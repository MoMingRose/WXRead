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
    for entry_name, entry_url in all_entry_url.items():
        if isinstance(entry_url, list):
            print(f"【{entry_name}】")
            for url in entry_url:
                if isinstance(url, tuple):
                    print(f"> {url[0]} >> {url[1]}")
                else:
                    print(f"> {url}")
        else:
            print(f"【{entry_name}】\n> {entry_url}")
