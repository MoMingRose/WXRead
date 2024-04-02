# -*- coding: utf-8 -*-
# base.py created by MoMingLog on 1/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-01
【功能描述】
"""
import random
import re
import sys
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.cookies import SimpleCookie
from json import JSONDecodeError
from queue import Queue
from typing import Type

import httpx
from httpx import URL
from pydantic import BaseModel, ValidationError

from exception.common import PauseReadingWaitNext, Exit, StopReadingNotExit, ExitWithCodeChange, CookieExpired, \
    RspAPIChanged
from schema.klyd import KLYDAccount, KLYDConfig
from utils.logger_utils import ThreadLogger, NestedLogColors
from utils.push_utils import WxPusher


class WxReadTaskBase(ABC):
    """阅读任务"""
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "1.0.0"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-04-01"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-01"
    # 当前任务名称
    CURRENT_TASK_NAME = "微信阅读任务"
    # 缓存
    _cache = {}

    def __init__(self, config_data, logger_name: str):
        self.config_data = config_data
        self.lock = threading.Lock()
        self.accounts = config_data.account_data
        self.source = config_data.source
        # 入口链接
        self.entry_url = self.get_entry_url()
        # 基本链接（初始链接）
        self.base_url: URL | None = None
        # 构建基本请求头
        self.base_headers = self.build_base_headers()
        # 构建主线程客户端
        self.main_client = httpx.Client(headers=self.base_headers, timeout=30)
        # # 构建基本客户端
        # self.base_client = httpx.Client(headers=self.base_headers, timeout=30)

        self.thread2name = {}
        self.logger = ThreadLogger(logger_name, thread2name=self.thread2name)

        self.init_fields()

        max_thread_count = config_data.max_thread_count
        if max_thread_count > 0:
            thread_count = min(max_thread_count, len(self.accounts))
        else:
            thread_count = len(self.accounts)

        self.logger.info(NestedLogColors.white(
            "\n".join([
                "【脚本信息】",
                f"> 作者：{self.CURRENT_SCRIPT_AUTHOR}",
                f"> 版本号：{self.CURRENT_SCRIPT_VERSION}",
                f"> 任务名称：{self.CURRENT_TASK_NAME}",
                f"> 创建时间：{self.CURRENT_SCRIPT_CREATED}",
                f"> 更新时间：{self.CURRENT_SCRIPT_UPDATED}",
            ])
        ))

        self.logger.info(NestedLogColors.white(
            "\n".join([
                f"【任务配置信息】",
                f"> 账号数量：{len(self.accounts)}",
                f"> 账号队列: {[name for name in self.accounts.keys()]}",
                f"> 最大线程数：{thread_count}",
                f"> 配置来源: {self.source}",
                f"> 入口链接（实时更新）: {self.entry_url}"
            ])
        ))

        self.wait_queue = Queue()

        with ThreadPoolExecutor(max_workers=thread_count, thread_name_prefix="klyd") as executor:
            self.futures = [executor.submit(self._base_run, name) for name in self.accounts.keys()]
            for future in as_completed(self.futures):
                # 接下来的程序都是在主线程中执行
                executor.submit(self.start_queue)

        self.wait_queue.join()

    @abstractmethod
    def init_fields(self):
        pass

    @abstractmethod
    def run(self, name):
        pass

    @abstractmethod
    def get_entry_url(self):
        pass

    def _base_run(self, name):
        # 接下来的程序都是在线程中执行
        # 将用户名存入字典中（用于设置logger的prefix）
        self.thread2name[self.ident] = name
        try:
            self.run(name)
        except StopReadingNotExit as e:
            self.logger.info(f"🔘 {e}")
        except (RspAPIChanged, ExitWithCodeChange) as e:
            self.logger.error(e)
            sys.exit(0)
        except CookieExpired as e:
            self.logger.war(e)
            return
        except PauseReadingWaitNext as e:
            self.lock.acquire()
            self.logger.info(f"🟢🔶 {e}")
            if self.is_wait_next_read:
                self.logger.info("✳️ 检测到开启了【等待下次阅读】的功能")
                # 提取数字
                wait_minute = int(re.search(r"(\d+)", str(e)).group(1))
                self.wait_queue.put(wait_minute)
                self.wait_queue.put(name)
                # self.__start_wait_next_read(wait_minute, name)
            else:
                self.logger.war(
                    "✴️ 未开启【等待下次阅读】功能，停止当前用户任务! \n> Tips: 开启则配置 'wait_next_read' 为 'true'（可以单账号单独配置）")
            self.lock.release()
        except Exception as e:
            self.is_need_withdraw = False
            self.logger.exception(e)
            sys.exit(0)
        finally:
            self.base_client.close()
            self.read_client.close()
            self.article_client.close()

    def start_queue(self):
        while not self.wait_queue.empty():
            wait_time = self.wait_queue.get()
            name = self.wait_queue.get()
            self.__start_wait_next_read(wait_time, name)
            self.wait_queue.task_done()

    def __start_wait_next_read(self, wait_minute, name):
        self.thread2name[self.ident] = name
        self.logger.error("等待下次阅读")
        random_sleep_min = random.randint(1, 5)
        self.logger.info(f"随机延迟【{random_sleep_min}】分钟")
        self.logger.info(f"💤 程序将自动睡眠【{wait_minute + random_sleep_min}】分钟后开始阅读")
        # 获取将来运行的日期
        # 先获取时间戳
        future_timestamp = int(time.time()) + int(wait_minute + random_sleep_min) * 60
        from datetime import datetime
        future_date = datetime.fromtimestamp(future_timestamp)
        self.logger.info(f"🟢 预计将在【{future_date}】阅读下一批文章")
        # 睡眠
        self.logger.info(f"💤 💤 💤 睡眠中...")
        time.sleep(wait_minute * 60)
        self.logger.info(f"🟡 程序即将开始运行，剩余时间 {random_sleep_min} 分钟")
        time.sleep(random_sleep_min * 60)
        self.logger.info(f"🟢 程序已睡眠结束")
        self.run(name)

    def wx_pusher_link(self, link) -> bool:
        return WxPusher.push_by_uid(self.app_token, self.wx_pusher_uid, f"{self.CURRENT_TASK_NAME}过检测", link)

    def request_for_json(self, method: str, url: str | URL, prefix: str, *args, client: httpx.Client = None,
                         model: Type[BaseModel] = None,
                         **kwargs) -> dict | BaseModel | str:
        """获取json数据"""

        update_headers = kwargs.pop("update_headers", {})
        ret_types = kwargs.pop("ret_types", [])
        if isinstance(ret_types, str):
            ret_types = [ret_types]
        ret = self._request(method, url, prefix, *args, client=client, update_headers={
            "Accept": "application/json, text/plain, */*",
            **update_headers,
        }, ret_types=[RetTypes.JSON, *ret_types], **kwargs)
        if model is not None:
            ret = self.__to_model(model, ret)
        return ret

    def __to_model(self, model: Type[BaseModel], data: dict) -> BaseModel | dict:
        """
        将dict转换为 model
        :param model:
        :param data:
        :return:
        """
        try:
            return model.model_validate(data)
        except ValidationError as e:
            self.logger.error(f"数据校验失败, 原因: {e}\n> 请通知作者更新 原始响应数据：{data}")
            return data

    def request_for_page(self, url: str | URL, prefix: str, *args, client: httpx.Client = None, **kwargs) -> str:
        """获取网页源代码"""
        update_headers = kwargs.pop("update_headers", {})
        ret_types = kwargs.pop("ret_types", [])
        if isinstance(ret_types, str):
            ret_types = [ret_types]

        return self._request("GET", url, prefix, *args, client=client, update_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            **update_headers,
        }, ret_types=[RetTypes.HTML, *ret_types], **kwargs)

    def request_for_redirect(self, url: str | URL, prefix: str, *args, client: httpx.Client = None, **kwargs) -> URL:
        """获取重定向链接"""
        update_headers = kwargs.pop("update_headers", {})
        return self._request("GET", url, prefix, *args, client=client, update_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            **update_headers,
        }, ret_types=RetTypes.REDIRECT, **kwargs)

    def _request(self, method: str, url: str | URL, prefix: str, *args, client: httpx.Client = None,
                 update_headers: dict = None,
                 ret_types: str | list = None,
                 **kwargs) -> any:
        """
        发起请求
        :param method: 请求方法
        :param url: 请求链接
        :param prefix: logger的前缀
        :param args: 扩展参数，会传入 httpx.Client.request
        :param client: 请求客户端，默认为None，会自动创建
        :param update_headers: 更新请求头
        :param ret_types: 返回类型
        :param kwargs: 扩展参数，会传入 httpx.Client.request
        :return:
        """
        if isinstance(ret_types, str):
            ret_types = [ret_types]
        flag = False
        if url is None:
            raise Exit()

        response = None
        ignore_json_error = kwargs.pop("ignore_json_error", False)
        try:
            self.lock.acquire()
            if client is None:
                client = httpx.Client(headers=self.build_base_headers(self.account_config), timeout=30)
                flag = True
            else:
                client = client

            if update_headers:
                client.headers.update(update_headers)

            if isinstance(url, str):
                url = URL(url)

            if url.is_absolute_url:
                client.headers.update({
                    "Host": url.host
                })
            else:
                client.headers.update({
                    "Host": client.base_url.host
                })

            response = client.request(method, url, *args, **kwargs)
            self.logger.response(prefix, response)

            ret_data = []
            for ret_type in ret_types:
                if ret_type == RetTypes.RESPONSE:
                    ret_data.append(response)
                elif ret_type in [RetTypes.TEXT, RetTypes.HTML]:
                    ret_data.append(response.text)
                elif ret_type == RetTypes.JSON:
                    ret_data.append(response.json())
                elif ret_type == RetTypes.CONTENT:
                    ret_data.append(response.content)
                elif ret_type in [RetTypes.LOCATION, RetTypes.REDIRECT]:
                    ret_data.append(response.next_request.url)
                elif ret_type == RetTypes.STATUS:
                    ret_data.append(response.status_code)

            if len(ret_data) == 1:
                return ret_data[0]
            return ret_data
        except JSONDecodeError as e:
            if not ignore_json_error:
                self.logger.exception(f"请求失败 JSONDecodeError：{e}")
            else:
                if RetTypes.TEXT in ret_types:
                    return response.text
        except Exception as e:
            self.logger.exception(f"请求失败：{e}")
        finally:
            if flag:
                client.close()
            self.lock.release()

    @property
    def is_wait_next_read(self):
        """是否等待下次读取"""
        ret = self.account_config.wait_next_read
        if ret is None:
            ret = self.config_data.wait_next_read
        return ret if ret is not None else False

    @property
    def is_need_withdraw(self):
        return self._cache.get(f"is_need_withdraw_{self.ident}", False)

    @is_need_withdraw.setter
    def is_need_withdraw(self, value):
        self._cache[f"is_need_withdraw_{self.ident}"] = value

    @property
    def base_client(self):
        return self._get_client("base")

    @property
    def read_client(self):
        return self._get_client("read")

    @property
    def article_client(self):
        return self._get_client("article", verify=False)

    def _get_client(self, client_name: str, headers: dict = None, verify: bool = True) -> httpx.Client:
        """
        获取客户端
        :param client_name: 客户端名称
        :param headers: 请求头
        :param verify: 验证
        :return:
        """
        client_name = f"{client_name}_client_{self.ident}"
        client = self._cache.get(client_name)
        if client is None:
            if headers is None:
                headers = self.build_base_headers(self.account_config)
            client = httpx.Client(headers=headers, timeout=30, verify=verify)
            self._cache[client_name] = client
        return client

    @property
    def app_token(self):
        ret = self.account_config.appToken
        if ret is None:
            ret = self.config_data.appToken
        return ret

    @property
    def wx_pusher_uid(self):
        return self.account_config.uid

    @property
    def read_delay(self):
        delay = self.account_config.delay
        ret = delay.read_delay if delay is not None else self.config_data.delay.read_delay
        return ret

    @property
    def push_delay(self):
        delay = self.account_config.delay
        ret = delay.push_delay if delay is not None else self.config_data.delay.push_delay
        return ret

    @property
    def withdraw(self):
        ret = self.account_config.withdraw
        if ret == 0:
            ret = self.config_data.withdraw
        return ret

    @property
    def withdraw_way(self):
        if self.aliName and self.aliAccount:
            return f"支付宝\n> > 支付宝姓名: {self.aliName}\n> > 支付宝账号: {self.aliAccount}"
        return "微信"

    @property
    def aliAccount(self):
        ret = self.account_config.aliAccount
        if not ret:
            ret = self.config_data.aliAccount
        return ret

    @property
    def aliName(self):
        ret = self.account_config.aliName
        if not ret:
            ret = self.config_data.aliName
        return ret

    @property
    def ident(self):
        return threading.current_thread().ident

    @property
    def account_config(self) -> KLYDAccount:
        return self.accounts[self.logger.name]

    @property
    def origin_cookie(self):
        return self.account_config.cookie

    @property
    def cookie_dict(self) -> dict:
        return {key: value.value for key, value in SimpleCookie(self.origin_cookie).items()}

    def build_base_headers(self, account_config: KLYDConfig = None):
        if account_config is not None:
            ua = account_config.ua
        else:
            ua = self.config_data.ua
        return {
            "User-Agent": ua if ua else "Mozilla/5.0 (Linux; Android 14; M2012K11AC Build/UKQ1.230804.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160083 MMWEBSDK/20231202 MMWEBID/4194 MicroMessenger/8.0.47.2560(0x28002F51) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "com.tencent.mm",
            "Upgrade-Insecure-Requests": "1"
        }


class RetTypes:
    TEXT = "text"
    HTML = "text"
    JSON = "json"
    RESPONSE = "response"
    CONTENT = "content"
    LOCATION = "location"
    REDIRECT = "location"
    STATUS = "status"
