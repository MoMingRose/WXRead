# -*- coding: utf-8 -*-
# push_utils.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
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

        url = "http://wxpusher.zjiecode.com/api/send/message"
        try:
            p = httpx.post(url, json=data, verify=False)
            if p.json()["code"] == 1000:
                print("🟡 检测文章已推送! 请尽快点击!")
                return True
            else:
                print("🔴 文章推送失败! ")
                return False
        except:
            print("🔴 文章推送失败! ")
            return False