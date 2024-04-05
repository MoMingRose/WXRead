# -*- coding: utf-8 -*-
# push_utils.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
import re
import time

import httpx

from config import storage_cache_config, load_wx_business_access_token
from utils import global_utils, md5


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
        print(f"🚛🚛 文章推送中 ->{link}")
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


class WxBusinessPusher:
    USER_NAME_COMPILE = re.compile(r"用户.*?(.*)")
    TURN_COUNT_COMPILE = re.compile(r"轮数.*?(\d+)")
    CHAPTER_COUNT_COMPILE = re.compile(r"篇数.*?(\d+)")
    READ_CHAPTER_COUNT_COMPILE = re.compile(r"已读.*?(\d+)")
    CURRENT_CHAPTER_COUNT_COMPILE = re.compile(r"当前.*?(\d+)")

    @staticmethod
    def handle_read_situation(situation: str | tuple, is_robot: bool = False):
        """
        处理阅读情况
        :return:
        """
        msg_list = []
        if is_robot:
            msg_list.append(f"> 用户: <font color=\"info\">{situation[0]}</font>")
        else:
            if r := WxBusinessPusher.USER_NAME_COMPILE.search(situation):
                msg_list.append(f'<div class="highlight">> 用户: {r.group(1)}</div>')

        if isinstance(situation, tuple):
            msg_list.extend([
                f"> 轮数: {situation[1]}",
                f"> 篇数: {situation[2]}",
                f"> 已读: {situation[3]}",
                f"> 当前: {situation[4]}",
            ])
        elif isinstance(situation, str):
            # 尝试按照固定格式提取
            if r := WxBusinessPusher.TURN_COUNT_COMPILE.search(situation):
                msg_list.append(f"> 轮数: {r.group(1)}")
            if r := WxBusinessPusher.CHAPTER_COUNT_COMPILE.search(situation):
                msg_list.append(f"> 篇数: {r.group(1)}")
            if r := WxBusinessPusher.READ_CHAPTER_COUNT_COMPILE.search(situation):
                msg_list.append(f"> 已读: {r.group(1)}")
            if r := WxBusinessPusher.CURRENT_CHAPTER_COUNT_COMPILE.search(situation):
                msg_list.append(f"> 当前: {r.group(1)}")

        return "\n".join(msg_list)

    @staticmethod
    def push_article_by_robot(webhook: str, title: str, link: str, is_markdown: bool = False, situation: str | tuple = None, tips: str = None,
                              **kwargs):
        """
        通过企业微信机器人推送文章

        参考文章：https://developer.work.weixin.qq.com/document/path/91770

        :param key:
        :return:
        """

        if is_markdown:
            situation = WxBusinessPusher.handle_read_situation(situation, is_robot=True)
            msg_type = "markdown"
            s = f'''
# {title}

【当前阅读情况】
{situation}

【Tips】
> <font color="warning">{tips}</font>

----> [前往阅读]({link})

----> {global_utils.get_date()}'''
        else:
            s = link
            msg_type = "text"
        data = {
            "msgtype": msg_type,
            msg_type: {
                "content": s
            }
        }
        print(f"> 🚛🚛 文章推送中 ->{link}")
        max_retry = 3
        while max_retry > 0:
            try:
                response = httpx.post(webhook, json=data, verify=False)
                if response.json().get("errcode") == 0:
                    print("> 🟢🟡 检测文章已推送! 请尽快点击!")
                    return True
            finally:
                time.sleep(1)
                max_retry -= 1
        print("> 🔴❌️ 文章推送失败! ")
        return False

    @staticmethod
    def push_article_by_agent(
            corp_id: int,
            corp_secret: str,
            agent_id: int,
            title: str,
            link: str,
            situation: str | tuple,
            tips: str,
            token=None,
            recursion=0,
            **kwargs
    ):
        """
        通过企业微信中的应用来推送文章

        创建应用教程参考：https://juejin.cn/post/7235078247238680637#heading-0

        开发修改教程参考：https://developer.work.weixin.qq.com/document/path/90236#%E6%8E%A5%E5%8F%A3%E5%AE%9A%E4%B9%89

        :param corp_id: 公司ID
        :param corp_secret: 应用密钥（在创建的应用中，找到AgentId下方的Secret即可）
        :param agent_id: 应用ID
        :param title: 推送标题
        :param link: 详情链接
        :param situation: 阅读情况
        :param tips: 提示信息
        :param token: 缓存的accessToken
        :param recursion: 递归次数
        :return:
        """
        situation = WxBusinessPusher.handle_read_situation(situation)
        data = {
            "touser": '@all',
            "agentid": agent_id,
            "msgtype": "textcard",
            "textcard": {
                "title": f"{title}",
                "description": '''<div class="gray">{}</div>
                    <div class="normal">【当前阅读情况】</div>\n{}
                    <div class="highlight">{}</div>'''.format(
                    global_utils.get_date(is_fill_chinese=True), situation, tips
                ),
                "url": link,
                "btntxt": "阅读文章"
            },
        }
        if token is None:
            # 首先尝试从缓存中读取accessToken
            try:
                token = load_wx_business_access_token(corp_id, agent_id)
            except KeyError:
                # 如果报错，则进行请求获取
                token = WxBusinessPusher._get_accessToken(corp_id, corp_secret, agent_id)

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        retry = 3
        while retry > 0:
            try:
                response = httpx.post(url=url, json=data)
                res_json = response.json()
                errcode = res_json.get("errcode")
                if errcode == 0:
                    print("> 🟢🟡 检测文章已推送! 请尽快点击!")
                    return True
                elif errcode == 40014:
                    if recursion >= 3:
                        raise Exception("> 🔴❌️ 递归次数达到上限，停止重新获取accessToken")
                    else:
                        print("> 🔴🟡 accessToken不合法/已过期！")
                        token = WxBusinessPusher._get_accessToken(corp_id, corp_secret, agent_id)
                        return WxBusinessPusher.push_article_by_agent(corp_id, corp_secret, agent_id, title, link,
                                                                      situation,
                                                                      tips, token, recursion + 1)
                elif errcode == 42001:
                    raise Exception(
                        f"> 🔴🟡 请求被拒绝，请确认您的IP被放入了白名单（企业可信IP）, 具体响应如下：\n {res_json.get('errmsg')}")
                else:
                    print(f"出现其他推送失败情况，原数据：{res_json}")
            finally:
                time.sleep(1)
                retry -= 1
        print("> 🔴❌️ 文章推送失败! ")
        return False

    @staticmethod
    def _get_accessToken(corp_id, corp_secret, agent_id):
        """
        获取AccessToken
        :param corp_id: 企业ID
        :param corp_secret: 应用密钥（在创建的应用中，找到AgentId下方的Secret即可）
        :param agent_id: 应用ID
        :return:
        """
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=" + corp_id + "&corpsecret=" + corp_secret
        p = httpx.get(url=url, verify=False)
        access_token = p.json()["access_token"]
        key = md5(f"{corp_id}_{agent_id}")
        # 缓存token
        storage_cache_config({
            "wxBusiness": {
                key: {
                    "accessToken": access_token
                }
            }
        })
        return access_token

