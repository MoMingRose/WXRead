# -*- coding: utf-8 -*-
# push_utils.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
import time

import httpx


class WxPusher:

    @classmethod
    def push_article(cls, appToken: str, title: str, link: str, uids: str | list = None, topicIds: str | list = None):
        if isinstance(uids, str):
            uids = [uids]
        if isinstance(topicIds, str):
            topicIds = [topicIds]
        data = {
            "appToken": appToken,
            "content": f"""<body onload="window.location.href='{link}'"><p><b>{title}文章检测</b></p></body>""",
            "summary": title,
            "contentType": 2,
            "uids": uids or [],
            "topicIds": topicIds or [],
            "url": link,
        }
        print(f"文章推送中: {title}, {link}")
        url = "http://wxpusher.zjiecode.com/api/send/message"
        max_retry = 3
        while max_retry > 0:
            try:
                response = httpx.post(url, json=data, verify=False)
                if response.json().get("code") == 1000:
                    print("> 🟢🟡 检测文章已推送! 请尽快点击!")
                    return True
                time.sleep(1)
            except Exception as e:
                print(f"Error occurred: {e}")
                time.sleep(1)
            max_retry -= 1
        print("> 🔴❌️ 文章推送失败! ")
        return False


if __name__ == '__main__':
    WxPusher.push_article(
        "",
        "测试",
        "www.baidu.com",
        # uids="", # 可行
        uids=[],
        # topicIds="", # 可行
        topicIds=[],
    )
