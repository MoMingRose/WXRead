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
from urllib.parse import ParseResult

import httpx
from httpx import URL
from pydantic import BaseModel, ValidationError

from config import load_detected_data, store_detected_data
from exception.common import PauseReadingAndCheckWait, Exit, StopReadingNotExit, ExitWithCodeChange, \
    CookieExpired, \
    RspAPIChanged, PauseReadingTurnNext
from exception.klyd import WithdrawFailed
from schema.common import ArticleInfo
from utils import md5
from utils.logger_utils import ThreadLogger, NestedLogColors
from utils.push_utils import WxPusher, WxBusinessPusher


class WxReadTaskBase(ABC):
    """阅读任务"""
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "1.0.0"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-04-01"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-03"
    # 当前任务名称
    CURRENT_TASK_NAME = "微信阅读任务"
    # 缓存
    _cache = {}

    # 文章标题
    ARTICLE_TITLE_COMPILE = re.compile(r'meta.*?og:title"\scontent="(.*?)"\s*/>', re.S)
    # 文章作者
    ARTICLE_AUTHOR_COMPILE = re.compile(r'meta.*?og:article:author"\scontent="(.*?)"\s*/>', re.S)
    # 文章描述
    ARTICLE_DESC_COMPILE = re.compile(r'meta.*?og:description"\scontent="(.*?)"\s*/>', re.S)
    # 文章Biz
    ARTICLE_BIZ_COMPILE = re.compile(r"og:url.*?__biz=(.*?)&", re.S)

    # 普通链接Biz提取
    NORMAL_LINK_BIZ_COMPILE = re.compile(r"__biz=(.*?)&", re.S)

    # 检测有效阅读链接
    ARTICLE_LINK_VALID_COMPILE = re.compile(
        r"^https?://mp.weixin.qq.com/s\?__biz=[^&]*&mid=[^&]*&idx=\d*&(?!.*?chksm).*?&scene=\d*#wechat_redirect$")

    def __init__(self, config_data, logger_name: str, *args, **kwargs):
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
        self.global_kwargs = kwargs
        # 构建主线程客户端
        self.main_client = httpx.Client(headers=self.base_headers, timeout=10, verify=False)
        # # 构建基本客户端
        # self.base_client = httpx.Client(headers=self.base_headers, timeout=10)

        self.thread2name = {
            "is_log_response": self.is_log_response,
        }
        self.logger = ThreadLogger(logger_name, thread2name=self.thread2name,
                                   is_init_colorama=self.config_data.init_colorama)

        self.init_fields()

        max_thread_count = config_data.max_thread_count
        if max_thread_count > 0:
            thread_count = min(max_thread_count, len(self.accounts))
        else:
            thread_count = len(self.accounts)

        self.max_thread_count = thread_count

        self.logger.info(NestedLogColors.blue(
            "\n".join([
                f"{NestedLogColors.black('【脚本信息】', 'blue')}",
                f"> 作者：{self.CURRENT_SCRIPT_AUTHOR}",
                f"> 版本号：{self.CURRENT_SCRIPT_VERSION}",
                f"> 任务名称：{self.CURRENT_TASK_NAME}",
                f"> 创建时间：{self.CURRENT_SCRIPT_CREATED}",
                f"> 更新时间：{self.CURRENT_SCRIPT_UPDATED}",
            ])
        ))

        self.logger.info(NestedLogColors.blue(
            "\n".join([
                f"{NestedLogColors.black('【任务配置信息】', 'blue')}",
                f"> 账号数量：{len(self.accounts)}",
                f"> 账号队列: {[name for name in self.accounts.keys()]}",
                f"> 最大线程数：{thread_count}",
                f"> 配置来源: {self.source}",
                f"> 入口链接（实时更新）: {self.entry_url}"
            ])
        ))

        if kwargs.pop("load_detected", False):
            self.logger.info("")
            self.logger.war("> > 🟡 正在加载本地文章检测数据...")
            self.logger.war("> > 🟡 [Tips] 此数据会在程序运行过程中自动收集检测未通过时的文章链接")
            self.detected_data = load_detected_data()
            if self.detected_data is not None:
                self.logger.info(f"> > 🟢 加载成功! 当前已自动收集检测文章个数: {len(self.detected_data)}")
            else:
                self.logger.war("> > 🟡 本地暂无检测文章数据")
            self.logger.info("")
        else:
            self.detected_data = set()
        self.new_detected_data = set()

        self.cacahe_queue = Queue()
        self.wait_queue = Queue()

        with ThreadPoolExecutor(max_workers=thread_count, thread_name_prefix="MoMingLog") as executor:
            self.futures = [executor.submit(self._base_run, name, executor) for name in self.accounts.keys()]
            for future in as_completed(self.futures):
                # 接下来的程序都是在主线程中执行
                executor.submit(self.start_queue)

        if not self.wait_queue.empty():
            self.wait_queue.join()

    @abstractmethod
    def init_fields(self, retry_count: int = 3):
        """这个方法执行在主线程中，可以用来进行账号运行前的初始化操作
        :param retry_count:
        """
        pass

    @abstractmethod
    def run(self, name, *args, **kwargs):
        """账号运行的主入口
        :param *args:
        :param **kwargs:
        """
        pass

    @abstractmethod
    def get_entry_url(self) -> str:
        """返回入口链接"""
        pass

    def _base_run(self, name, executor):
        # 接下来的程序都是在线程中执行
        # 将用户名存入字典中（用于设置logger的prefix）
        self.thread2name[self.ident] = name
        try:
            self.run(name, executor=executor)
        except (StopReadingNotExit, WithdrawFailed, CookieExpired) as e:
            self.logger.war(e)
            return
        except (RspAPIChanged, ExitWithCodeChange) as e:
            self.logger.error(e)
            sys.exit(0)
        except PauseReadingTurnNext as e:
            self.logger.info(e)
            return
        except PauseReadingAndCheckWait as e:
            self.lock.acquire()
            self.logger.info(e)
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
            if self.new_detected_data:
                self.logger.war(f"🟡 正在存储新的检测数据...")
                if store_detected_data(self.new_detected_data, old_data=self.detected_data):
                    self.logger.info(f"🟢 存储成功，此次自动收集检测文章个数: {len(self.new_detected_data)}")
            if self.lock.locked():
                self.lock.release()
            # 如果是单线程，并且账号数大于1
            if self.max_thread_count == 1 and len(self.accounts) > 1:
                # 则重置所有的client，避免出现client资源污染的现象
                self.base_client = None
                self.read_client = None
                self.article_client = None

    def start_queue(self):
        while not self.wait_queue.empty():
            wait_time = self.wait_queue.get()
            name = self.wait_queue.get()
            self.__start_wait_next_read(wait_time, name)
            self.wait_queue.task_done()

    def __start_wait_next_read(self, wait_minute, name, last_wait_minute: int = None):
        self.thread2name[self.ident] = name
        # 判断上一次等待时间是否不为空
        if last_wait_minute is not None:
            # 求差值，如果上一次等待时间大于此次等待时间，并且线程数为 1，则直接开始运行
            if wait_minute - last_wait_minute <= 0 and self.max_thread_count == 1:
                self.logger.info("🟢 程序已睡眠结束")
        else:
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

    def parse_wx_article(self, article_url):
        try:
            # 获取文章源代码
            article_page = self.__request_article_page(article_url)
        except:
            article_page = ""

        if article_page is None:
            self.logger.war(f"🟡 文章页面解析失败，原始文章链接为：{article_url}")
            article_page = ""

        if r := self.ARTICLE_BIZ_COMPILE.search(article_page):
            article_biz = r.group(1)
        else:
            article_biz = ""
        if r := self.ARTICLE_TITLE_COMPILE.search(article_page):
            article_title = r.group(1)
        else:
            article_title = ""
        if r := self.ARTICLE_AUTHOR_COMPILE.search(article_page):
            article_author = r.group(1)
        else:
            article_author = ""
        if r := self.ARTICLE_DESC_COMPILE.search(article_page):
            article_desc = r.group(1)
        else:
            article_desc = ""
        article_info = ArticleInfo(
            article_url=article_url,
            article_biz=article_biz,
            article_title=article_title,
            article_author=article_author,
            article_desc=article_desc
        )
        return article_info

    def wx_pusher(self, link, detecting_count: int = None) -> bool:
        """
        通过WxPusher推送
        :param link:
        :param detecting_count:
        :return:
        """
        if detecting_count is None:
            s = f"{self.CURRENT_TASK_NAME}过检测"
        else:
            s = f"{self.CURRENT_TASK_NAME}-{detecting_count}过检测"
        return WxPusher.push_article(
            appToken=self.wx_pusher_token,
            title=s,
            link=link,
            uids=self.wx_pusher_uid,
            topicIds=self.wx_pusher_topicIds
        )

    def wx_business_pusher(self, link, detecting_count: int = None, **kwargs) -> bool:
        """
        通过企业微信推送
        :param link:
        :param detecting_count:
        :param kwargs:
        :return:
        """
        if detecting_count is None:
            s = f"{self.CURRENT_TASK_NAME}过检测"
        else:
            s = f"{self.CURRENT_TASK_NAME}-{detecting_count}过检测"
        if self.wx_business_use_robot:
            return WxBusinessPusher.push_article_by_robot(
                self.wx_business_webhook_url,
                s,
                link,
                is_markdown=self.wx_business_is_push_markdown,
                **kwargs)
        else:
            return WxBusinessPusher.push_article_by_agent(
                self.wx_business_corp_id,
                self.wx_business_corp_secret,
                self.wx_business_agent_id,
                title=s,
                link=link,
                **kwargs
            )

    def __request_article_page(self, article_url: str):
        return self.request_for_page(article_url, "请求文章信息 article_client", client=self.article_client)

    def request_for_json(self, method: str, url: str | URL, prefix: str, *args, client: httpx.Client = None,
                         model: Type[BaseModel] = None,
                         **kwargs) -> dict | BaseModel | str | None:
        """获取json数据"""

        update_headers = kwargs.pop("update_headers", {})
        ret_types = kwargs.pop("ret_types", [])
        if isinstance(ret_types, str):
            ret_types = [ret_types]
        ret = self._request(method, url, prefix, *args, client=client, update_headers={
            "Accept": "application/json, text/plain, */*",
            **update_headers,
        }, ret_types=[RetTypes.JSON, *ret_types], **kwargs)
        if model is not None and ret is not None:
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
            return model.parse_obj(data)
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
                 retry_count: int = 3,
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
                client = httpx.Client(headers=self.build_base_headers(self.account_config), timeout=10)
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
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            self.logger.error(f"请求超时, 剩余重试次数：{retry_count - 1}")
            if retry_count > 0:
                if flag:
                    client.close()
                if self.lock.locked():
                    self.lock.release()
                return self._request(method, url, prefix, *args, client=client, update_headers=update_headers,
                                     ret_types=ret_types, retry_count=retry_count - 1, **kwargs)
            else:
                raise StopReadingNotExit("超时重试次数过多!")
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
            if self.lock.locked():
                self.lock.release()

    @property
    def wx_business_is_push_markdown(self):
        ret = self.account_config.is_push_markdown
        if ret is None:
            ret = self.config_data.is_push_markdown
        return ret if ret is not None else False

    @property
    def wx_business_use_robot(self):
        ret = self.account_config.use_robot
        if ret is None:
            ret = self.config_data.use_robot
        return ret if ret is not None else True

    @property
    def wx_business_webhook_url(self):
        ret = self.account_config.webhook_url
        if ret is None:
            ret = self.config_data.webhook_url
        return ret

    @property
    def wx_business_corp_id(self):
        ret = self.account_config.corp_id
        if ret is None:
            ret = self.config_data.corp_id
        return ret

    @property
    def wx_business_agent_id(self):
        ret = self.account_config.agent_id
        if ret is None:
            ret = self.config_data.agent_id
        return ret

    @property
    def wx_business_corp_secret(self):
        ret = self.account_config.corp_secret
        if ret is None:
            ret = self.config_data.corp_secret
        return ret

    @property
    def push_types(self):
        ret = self.account_config.push_types
        if ret is None:
            ret = self.config_data.push_types
        return ret if ret is not None else [1]

    @property
    def is_wait_next_read(self):
        """是否等待下次读取"""
        ret = self.account_config.wait_next_read
        if ret is None:
            ret = self.config_data.wait_next_read
        return ret if ret is not None else False

    @property
    def is_withdraw(self):
        """是否需要提现"""
        ret = self.account_config.is_withdraw
        if ret is None:
            ret = self.config_data.is_withdraw
        return ret if ret is not None else True

    @property
    def is_need_withdraw(self):
        return self._cache.get(f"is_need_withdraw_{self.ident}", False)

    @is_need_withdraw.setter
    def is_need_withdraw(self, value):
        self._cache[f"is_need_withdraw_{self.ident}"] = value

    @property
    def current_read_count(self):
        return self._cache.get(f"current_read_count_{self.ident}")

    @current_read_count.setter
    def current_read_count(self, value):
        self._cache[f"current_read_count_{self.ident}"] = value

    @property
    def base_client(self):
        return self._get_client("base")

    @base_client.setter
    def base_client(self, value):
        if value is None:
            self.base_client.close()
            self._cache.pop(f"base_client_{self.ident}", None)
        else:
            self._cache[f"base_client_{self.ident}"] = value

    def parse_base_url(self, url: str | URL | ParseResult, client: httpx.Client):
        """
        提取出用于设置 base_url的数据，并完成配置
        :param url:
        :param client:
        :return:
        """
        if isinstance(url, str):
            url = URL(url)

        protocol = url.scheme

        if isinstance(url, URL):
            host = url.host
        else:
            host = url.hostname
        client.base_url = f"{protocol}://{host}"
        return protocol, host

    @property
    def read_client(self):
        return self._get_client("read")

    @read_client.setter
    def read_client(self, value):
        if value is None:
            self.read_client.close()
            self._cache.pop(f"read_client_{self.ident}", None)
        else:
            self._cache[f"read_client_{self.ident}"] = value

    @property
    def article_client(self):
        return self._get_client("article", verify=False)

    @article_client.setter
    def article_client(self, value):
        if value is None:
            self.article_client.close()
            self._cache.pop(f"article_client_{self.ident}", None)
        else:
            self._cache[f"article_client_{self.ident}"] = value

    def _get_client(self, client_name: str, *args, headers: dict = None, verify: bool = True, **kwargs) -> httpx.Client:
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
                try:
                    headers = self.build_base_headers(self.account_config)
                except KeyError:
                    headers = self.build_base_headers()
            client = httpx.Client(*args, base_url=kwargs.pop("base_url", ""), headers=headers, timeout=10,
                                  verify=verify, **kwargs)
            self._cache[client_name] = client
        return client

    def sleep_fun(self, is_pushed: bool = False, prefix: str = "") -> int:
        """
        睡眠随机时间
        :param is_pushed: 是否推送
        :param prefix: 阅读文章标签，例如 [1 - 1] 表示第1轮第1篇
        :return: 返回睡眠的时间
        """
        t = self.push_delay[0] if is_pushed else random.randint(self.read_delay[0], self.read_delay[1])
        self.logger.info(f"等待检测{prefix}完成, 💤 睡眠{t}秒" if is_pushed else f"💤 {prefix}随机睡眠{t}秒")
        # 睡眠随机时间
        time.sleep(t)
        return t

    @property
    def custom_detected_count(self):
        ret = self.account_config.custom_detected_count
        if ret is None:
            ret = self.config_data.custom_detected_count
        return ret if ret is not None else []

    @property
    def wx_pusher_token(self):
        ret = self.account_config.appToken
        if ret is None:
            ret = self.config_data.appToken
        return ret

    @property
    def wx_pusher_uid(self):
        ret = self.account_config.uid
        return ret if ret is not None else []

    @property
    def wx_pusher_topicIds(self):
        ret = self.config_data.topicIds
        if ret is None:
            ret = self.account_config.topicIds
        return ret if ret is not None else []

    @property
    def read_delay(self):
        ret = [10, 20]
        delay = self.account_config.delay
        if delay is None:
            delay = self.config_data.delay
        _read_delay = delay.read_delay
        if _read_delay is not None:
            _len = len(_read_delay)
            if _len == 2:
                _min = min(_read_delay)
                _max = max(_read_delay)
                ret = [_min, _max]
            else:
                _max = max(ret)
                ret = [10, _max]
        return ret

    @property
    def push_delay(self):
        ret = [19]

        delay = self.account_config.delay
        if delay is None:
            delay = self.config_data.delay

        _push_delay = delay.push_delay

        if _push_delay is not None:
            _len = len(_push_delay)
            if _len != 1:
                _max = max(_push_delay)
                ret = [_max] if _max > 19 else [19]
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
    def account_config(self):
        return self.accounts[self.logger.name]

    @property
    def origin_cookie(self):
        return self.account_config.cookie

    @property
    def cookie_dict(self) -> dict:
        return {key: value.value for key, value in SimpleCookie(self.origin_cookie).items()}

    @property
    def is_log_response(self):
        ret = self.config_data.is_log_response
        return ret if ret is not None else False

    def build_base_headers(self, account_config=None):
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
