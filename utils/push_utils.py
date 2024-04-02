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
    def push_by_uid(cls, appToken: str, uid: str, title: str, link: str):
        data = {
            "appToken": appToken,
            "content": f"""<body onload="window.location.href='{link}'"><p><b>{title}文章检测</b></p></body>""",
            "summary": title,
            "contentType": 2,
            "uids": [uid],
            "url": link,
        }
        print(f"文章推送中: {title}, {link}")
        url = "http://wxpusher.zjiecode.com/api/send/message"
        max_retry = 3
        while True:
            if max_retry == 0:
                print("> 🔴❌️ 文章推送失败! ")
                return False
            max_retry -= 1
            try:
                p = httpx.post(url, json=data, verify=False)
                if p.json()["code"] == 1000:
                    print("> 🟢🟡 检测文章已推送! 请尽快点击!")
                    return True
                time.sleep(1)
                continue
            except:
                time.sleep(1)
                continue


if __name__ == '__main__':
    WxPusher.push_by_uid("AT_eYk8SDwHbwiqrcSdl68L3JEkAI9aQmTA", "UID_daV3Y29gVgDCUpV5LywBvZe4jIpU", "ceshi ", "https://mp.weixin.qq.com/s?__biz=Mzk0MTI5NzcxMQ==&mid=2247557235&idx=1&sn=964271999e9cb1bf7e2eef5a2cbe3f81&scene=0#wechat_redirect")
