# -*- coding: utf-8 -*-
# 永久入口.py created by MoMingLog on 25/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-25
【功能描述】
"""
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List
from urllib.parse import urlparse

import httpx


class EntryUrl:
    """永久入口获取"""
    COMMON_URL_REG = re.compile(r'getCode.*?url.*?"(.*?)",', re.S)

    def __init__(
            self,
            *item_args: dict | List[dict],
    ):
        """
        初始化
        :param data: 提交数据
        :param page_type: 页面类型
        类型0：表示还需要通过接口获取
        类型1：页面会自动显示接口链接，这时直接提取即可

        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.142.86 Safari/537.36",
        }
        self._client = httpx.Client(headers=headers)
        self._result = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for _item in item_args:
                data_list = _item if isinstance(_item, list) else [_item]
                for d in data_list:
                    future = executor.submit(self.run, d)
                    futures.append((future, d))

            for future, d in futures:
                result = future.result()
                if result:
                    self._result[d.get("name")] = result

    def __dict__(self):
        return self._result

    def __str__(self):
        msg_list = []
        for name, value in self._result.items():
            msg_list.append(f"【平台名称】\n> {name}")
            msg_list.append(f"【获取结果】")
            if isinstance(value, str):
                msg_list.append(f"> {value}")
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, tuple):
                        msg_list.append(f"> {v[0]} -> {v[1]}")
                    else:
                        msg_list.append(f"> {v}")
            msg_list.append("")
        return "\n".join(msg_list)

    def __repr__(self):
        return self.__str__()

    def run(self, data: dict):
        task_name = data.get("name")
        # print(f"{task_name} 的永久入口为：{self.get_en_url(data)}")
        # self._result[task_name] = self.get_en_url(data)
        res = self.__get_en_url(data)
        return res

    def __get_en_url(self, data: dict):
        page_url = data.get("url")
        reg_str = data.get("reg")
        if reg_str is not None:
            page_compile = re.compile(reg_str, re.S)
        else:
            page_compile = EntryUrl.COMMON_URL_REG
        result = self.__fetch_fun(page_url, page_compile)
        page_type = data.get("type", 0)
        if page_type == 0:
            url = result[0]
            res_json = self.__request_json(url)
            if res_json["code"] == 0:
                r = res_json["data"]["luodi"]
                parse_url = urlparse(r)
                invite_url = data.get("invite_url")
                parse_invite_url = urlparse(invite_url)
                if invite_url:
                    return invite_url.replace(parse_invite_url.netloc, parse_url.netloc)
                return r
        elif page_type == 1:
            return result

    def __fetch_fun(self, page_url, page_compile):
        html = self.__request_homepage(page_url)
        if html:
            return page_compile.findall(html)

    def __request_json(self, url):
        response = self._client.get(url)
        try:
            res_json = response.json()
            return res_json
        except:
            print(f"解析失败：{url}")

    def __request_homepage(self, url):
        try:
            return self._client.get(url).text
        except:
            print(f"请求失败：{url}")

    @classmethod
    def get_mmkk_entry_url(cls, url: str = None, invite_url: str = None) -> str:
        """
        获取猫猫看看阅读的入口链接
        :param url: 永久入口主页链接
        :param invite_url: 个人邀请链接
        :param ret_type: 返回值类型
        :return:
        """
        if url is None:
            url = "https://code.sywjmlou.com.cn/"

        if invite_url is None:
            invite_url = "http://o1up.ieazq.shop/haobaobao/auth/c5aab76cbaa0d0c80ec1ade47b3ce520"

        return EntryUrl({
            "name": "猫猫看看",
            "url": url,
            "invite_url": invite_url
        }).all_entry_url

    @classmethod
    def get_xyy_entry_url(cls, url: str = None, invite_url: str = None) -> str:
        if url is None:
            url = "https://www.filesmej.cn/"

        if invite_url is None:
            invite_url = "http://9bk2.lvk72.shop/yunonline/v1/auth/5729acffb4b05596aef08e18eaf8a7cd?codeurl=9bk2.lvk72.shop&codeuserid=2&time=1711531311"

        return EntryUrl({
            "name": "小阅阅",
            "url": url,
            "invite_url": invite_url
        }).all_entry_url

    @classmethod
    def get_klrd_entry_url(cls, url: str = None, invite_url: str = None) -> str:
        if url is None:
            url = "http://m.fbjcoru.cn/entry?upuid=1316875"
        return EntryUrl({
            "name": "可乐读书",
            "url": url,
            "reg": r"(入口\d+).*?(http\S+?(?=\s|;|`))",
            "type": 1
        }).all_entry_url

    @classmethod
    def get_yryd_entry_url(cls, url: str = None, invite_url: str = None) -> str:
        if url is None:
            url = "http://h5.eqlrqqt.cn/entry/index5?upuid=2068422"

        return EntryUrl({
            "name": "鱼儿阅读",
            "url": url,
            "reg": r"url_h51[.\s=']*(http\S+)'",
            "type": 1
        }).all_entry_url

    @classmethod
    def get_all_entry_url(cls, *data: dict | List[dict], is_flag: bool = False) -> list | dict:
        if not data:
            data = [{
                "name": "小阅阅",
                "url": "https://www.filesmej.cn/",
                "invite_url": "http://9bk2.lvk72.shop/yunonline/v1/auth/5729acffb4b05596aef08e18eaf8a7cd?codeurl=9bk2.lvk72.shop&codeuserid=2&time=1711531311"
            }, {
                "name": "猫猫看看",
                "url": "https://code.sywjmlou.com.cn/",
                "invite_url": "http://o1up.ieazq.shop/haobaobao/auth/c5aab76cbaa0d0c80ec1ade47b3ce520"
            }, {
                "name": "可乐读书",
                "url": "http://m.fbjcoru.cn/entry?upuid=1316875",
                "reg": r"(入口\d+).*?(http\S+?(?=\s|;|`))",
                "type": 1
            }, {
                "name": "鱼儿阅读",
                "url": "http://h5.eqlrqqt.cn/entry/index5?upuid=2068422",
                "reg": r"url_h51[.\s=']*(http\S+)'",
                "type": 1
            }]
        if is_flag:
            return EntryUrl(data)._result

        return EntryUrl(data).all_entry_url

    @property
    def all_entry_url(self) -> str | list:
        url_list = []
        for value in self._result.values():
            if isinstance(value, list):
                if len(value) == 1:
                    url_list.append(value[0])
                else:
                    temp_tuple = ()
                    for n_v in value:
                        temp_tuple += (n_v[1],)

                    url_list.append(temp_tuple)
            else:
                url_list.append(value)
        if len(url_list) == 1:
            return url_list[0]
        return url_list


if __name__ == "__main__":
    print(EntryUrl.get_yryd_entry_url())
