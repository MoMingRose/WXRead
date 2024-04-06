# -*- coding: utf-8 -*-
# klyd.py created by MoMingLog on 30/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-30
【功能描述】 当前版本已不维护，请使用v2版本
"""
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.cookies import SimpleCookie
from json import JSONDecodeError
from typing import Type, Tuple

import httpx
from httpx import URL
from pydantic import BaseModel, ValidationError

from config import load_klyd_config
from exception.common import PauseReadingTurnNextAndCheckWait, CookieExpired, RspAPIChanged, ExitWithCodeChange, Exit, \
    RegExpError
from exception.klyd import FailedPassDetect
from schema.klyd import KLYDConfig, KLYDAccount, RspRecommend, RspReadUrl, RspDoRead, RspWithdrawal, \
    RspWithdrawalUser
from schema.common import ArticleInfo
from utils import EntryUrl, md5
from utils.logger_utils import ThreadLogger
from utils.push_utils import WxPusher

logger: ThreadLogger | None = None


class APIS:
    # 获取推荐信息
    RECOMMEND = "/tuijian"
    # 获取阅读链接
    GET_READ_URL = "/new/get_read_url"
    # 获取提现用户信息
    WITHDRAWAL = "/withdrawal"
    # 开始进行提现
    DO_WITHDRAWAL = "/withdrawal/doWithdraw"


class RetTypes:
    TEXT = "text"
    HTML = "text"
    JSON = "json"
    RESPONSE = "response"
    CONTENT = "content"
    LOCATION = "location"
    REDIRECT = "location"
    STATUS = "status"


class KLYD:
    """可乐阅读"""
    # 当前脚本版本号
    CURRENT_SCRIPT_VERSION = "0.1"
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-03-30"

    CURRENT_R_JS_VERSION = "5"

    R_JS_CODE_MD5 = "726fd4cbecf02fb665a489882a7721b2"

    # 提取正在加载页面源代码中的内容
    # 当前提取的是forstr、zs、iu、url(部分)、r.js
    READ_LOAD_PAGE_COMPILE = re.compile(
        r"script.*?forstr\s*=\s*['\"](.*?)['\"];.*?zs\s*=\s*['\"](.*?)['\"];.*?iu\s*=\s*['\"](.*?)['\"];.*?\s*=\s*['\"](https?.*?)['\"].*?['\"](.*?)['\"].*?src=['\"](.*?\?v=(\d+))['\"]",
        re.S)
    R_JS_CODE_COMPILE = re.compile(
        r"var\s*url\s=\s['\"](.*?)['\"].*?['\"](.*?)['\"]",
        re.S
    )
    # 检测有效阅读链接
    ARTICLE_LINK_VALID_COMPILE = re.compile(
        r"^https?://mp.weixin.qq.com/s\?__biz=[^&]*&mid=[^&]*&idx=\d*&(?!.*?chksm).*?&scene=\d*#wechat_redirect$")
    # 文章标题
    ARTICLE_TITLE_COMPILE = re.compile(r'meta.*?og:title"\scontent="(.*?)"\s*/>', re.S)
    # 文章作者
    ARTICLE_AUTHOR_COMPILE = re.compile(r'meta.*?og:article:author"\scontent="(.*?)"\s*/>', re.S)
    # 文章描述
    ARTICLE_DESC_COMPILE = re.compile(r'meta.*?og:description"\scontent="(.*?)"\s*/>', re.S)
    # 文章Biz
    ARTICLE_BIZ_COMPILE = re.compile(r"og:url.*?__biz=(.*?)&", re.S)

    _cache = {}

    def __init__(self, config_data: KLYDConfig = load_klyd_config()):
        self.klyd_config_data = config_data
        self.lock = threading.Lock()
        self.accounts = config_data.account_data
        self.source = config_data.source
        # 入口链接
        self.entry_url = ""
        # 基本链接（初始链接）
        self.base_url: URL | None = None
        # 构建基本请求头
        self.base_headers = self.__build_base_headers()
        # 构建主线程客户端
        self.main_client = httpx.Client(headers=self.base_headers, timeout=30)
        # # 构建基本客户端
        # self.base_client = httpx.Client(headers=self.base_headers, timeout=30)

        self.thread2name = {}
        global logger
        logger = ThreadLogger("🥤阅读", thread2name=self.thread2name)

        self.__init_fields()

        max_thread_count = config_data.max_thread_count
        if max_thread_count > 0:
            thread_count = min(max_thread_count, len(self.accounts))
        else:
            thread_count = len(self.accounts)

        logger.info(f"【脚本信息】\n> 作者：{self.CURRENT_SCRIPT_AUTHOR}\n> 版本号：{self.CURRENT_SCRIPT_VERSION}\n")
        logger.info(
            f"【任务配置信息】\n> 账号数量：{len(self.accounts)}\n> 账号队列: {[name for name in self.accounts.keys()]}\n> 最大线程数：{thread_count}\n> 配置来源: {self.source}\n> 入口链接: {self.entry_url}")

        with ThreadPoolExecutor(max_workers=thread_count, thread_name_prefix="klyd") as executor:
            futures = [executor.submit(self.run, name) for name in self.accounts.keys()]
            for future in as_completed(futures):
                # 接下来的程序都是在主线程中执行
                pass

    def __init_fields(self):
        entry_url_tuple = EntryUrl.get_klrd_entry_url()
        self.entry_url = entry_url_tuple[0]
        first_redirect_url: URL = self.__request_entry_for_redirect()
        self.base_url = f"{first_redirect_url.scheme}://{first_redirect_url.host}"
        self.base_full_url = first_redirect_url

    def run(self, name):
        # 接下来的程序都是在线程中执行
        # 将用户名存入字典中（用于设置logger的prefix）
        self.thread2name[self.ident] = name
        self.base_client.base_url = self.base_url
        logger.info(f"开始执行{name}的任务")
        homepage_url: URL = self.__request_redirect_for_redirect()
        logger.debug(f"homepage_url：{homepage_url}")
        try:
            # 观看抓包数据流，貌似下方的请求可有可无，无所谓，判断一下也好
            homepage_html, status = self.__request_for_page(
                homepage_url,
                "请求首页源代码 base_client",
                client=self.base_client,
                ret_types=RetTypes.STATUS
            )
            if status == 302:
                # 如果是重定向的响应，则有可能是cookie过期了
                # 为了避免不必要的请求, 这里直接抛出异常，从而停止当前这个用户的执行线程
                raise CookieExpired()
            # 再多一层判断，以防万一
            if 'f9839ced92845cbf6166b0cf577035d3' != md5(homepage_html):
                raise ExitWithCodeChange("homepage_html")
        except ExitWithCodeChange as e:
            logger.error(e)
            sys.exit(0)
        except CookieExpired as e:
            logger.war(e)
            return
        is_withdraw = False
        try:
            # 获取推荐数据（里面包含当前阅读的信息）
            recommend_data = self.__request_recommend_json(homepage_url)
            self.__print_recommend_data(recommend_data)
            logger.debug(f"recommend_json：{recommend_data}")
            # 获取阅读链接
            self.read_url: URL = self.__request_for_read_url()
            # 获取加载页面源代码
            read_load_page_html: str = self.__request_for_read_load_page(self.read_url)
            forstr, zs, r_js_path, r_js_version = self.__parse_read_load_page(read_load_page_html)
            logger.debug(f"r_js_path：{r_js_path}")
            logger.debug(f"r_js_version：{r_js_version}")
            if self.CURRENT_R_JS_VERSION != r_js_version:
                raise ExitWithCodeChange("r_js_version")

            # 设置read_client的base_url
            self.read_client.base_url = f"{self.read_url.scheme}://{self.read_url.host}"
            r_js_code = self.__request_r_js_code(r_js_path)
            if self.R_JS_CODE_MD5 != md5(r_js_code):
                raise ExitWithCodeChange("r_js_code")
            # 解析完成阅读的链接
            do_read_url_part_path = self.__parse_r_js_code(r_js_code, forstr, zs)
            do_read_url_full_path = self.__build_do_read_url_path(do_read_url_part_path)
            # 尝试通过检测并且开始阅读
            self.__pass_detect_and_read(do_read_url_part_path, do_read_url_full_path)
            # 尝试进行提现操作
            self.__request_withdraw()
            is_withdraw = True
        except PauseReadingTurnNextAndCheckWait as e:
            logger.info(e)
            if self.is_wait_next_read:
                logger.info("✳️ 检测到开启了【等待下次阅读】的功能")
                # 提取数字
                wait_minute = int(re.search(r"(\d+)", str(e)).group(1))
                self.__start_wait_next_read(wait_minute, name)
            else:
                logger.info(
                    "✴️ 未开启【等待下次阅读】功能，停止当前用户任务! \n> Tips: 开启则配置 'wait_next_read' 为 'true'（可以单账号单独配置）")
        except FailedPassDetect as e:
            logger.war(e)
        except (RspAPIChanged, ExitWithCodeChange) as e:
            logger.exception(e)
            sys.exit(0)
        except Exception as e:
            logger.exception(e)
            sys.exit(0)
        finally:
            if not is_withdraw:
                self.__request_withdraw()

    def __start_wait_next_read(self, wait_minute, name):
        random_sleep_min = random.randint(1, 5)
        logger.info(f"随机延迟【{random_sleep_min}】分钟")
        logger.info(f"💤 程序将自动睡眠【{wait_minute + random_sleep_min}】分钟后开始阅读")
        # 获取将来运行的日期
        # 先获取时间戳
        future_timestamp = int(time.time()) + int(wait_minute + random_sleep_min) * 60
        future_date = datetime.fromtimestamp(future_timestamp)
        logger.info(f"🟢 预计将在【{future_date}】阅读下一批文章")
        # 睡眠
        logger.info("💤 💤 💤 睡眠中...")
        time.sleep(wait_minute * 60)
        logger.info(f"🟡 程序即将开始运行，剩余时间 {random_sleep_min} 分钟")
        time.sleep(random_sleep_min * 60)
        logger.info(f"🟢 程序已睡眠结束")
        self.run(name)

    def __request_withdraw(self):
        """
        发起提现请求
        :return:
        """

        # 先获取要进行提现的用户信息
        withdrawal_model: RspWithdrawal | dict = self.__request_withdrawal_for_userinfo()
        # 判断数据模型是否验证成功
        if isinstance(withdrawal_model, RspWithdrawal):
            # 获取用户信息
            withdrawal_user_info: RspWithdrawalUser = withdrawal_model.data.user
            # 打印用户信息
            logger.info(withdrawal_user_info)
            amount = withdrawal_user_info.amount
            u_ali_account = withdrawal_user_info.u_ali_account
            u_ali_real_name = withdrawal_user_info.u_ali_real_name
        else:
            user_info = withdrawal_model.get("data", {}).get("user")
            if user_info is None:
                raise RspAPIChanged(APIS.WITHDRAWAL)
            logger.info(user_info)
            amount = user_info.get("amount", 0)
            u_ali_account = user_info.get("u_ali_account")
            u_ali_real_name = user_info.get("u_ali_real_name")

        if amount < 30 or amount // 100 < self.withdraw:
            raise Exception("🔴 提现失败, 当前账户余额达不到提现要求!")

        if self.withdraw_type == "wx":
            logger.info("开始进行微信提现操作...")
            self.__request_do_withdraw(amount, "wx")
        elif self.withdraw_type == "ali":
            logger.info("开始进行支付宝提现操作...")
            if u_ali_account is None or u_ali_real_name is None:
                u_ali_account = self.aliAccount
                u_ali_real_name = self.aliName

            if u_ali_account is None or u_ali_real_name is None:
                raise Exception("🟡 请先配置支付宝账号信息，再进行提现操作!")

            self.__request_do_withdraw(
                amount,
                "ali",
                u_ali_account,
                u_ali_real_name
            )
        else:
            raise Exception(f"🟡 作者目前暂未适配此【{self.withdraw_type}】提现方式!")

    def __request_do_withdraw(self, amount, _type, u_ali_account=None, u_ali_real_name=None):
        """
        发起提现请求
        :return:
        """
        if u_ali_account is not None:
            data = {
                "amount": amount,
                "type": _type,
                "u_ali_account": u_ali_account,
                "u_ali_real_name": u_ali_real_name
            }

        else:
            data = {
                "amount": amount,
                "type": _type
            }

        withdraw_result: Tuple[dict, str] | str = self.__request_for_json(
            "POST",
            APIS.DO_WITHDRAWAL,
            "提现 base_client",
            client=self.base_client,
            data=data,
            # 忽略json解析错误
            ignore_json_error=True,
            ret_types=RetTypes.TEXT
        )

        try:
            if isinstance(withdraw_result, Tuple):
                withdraw_result: dict = withdraw_result[0]
            elif isinstance(withdraw_result, str):
                withdraw_result: str = re.sub(r"<pre>.*?</pre>", "", withdraw_result, flags=re.S)
                withdraw_result: dict = json.loads(withdraw_result)
            else:
                raise RspAPIChanged(APIS.DO_WITHDRAWAL)

            if withdraw_result['code'] == 0:
                logger.info(f"🟢 提现成功! 预计到账 {amount / 100} 元")
            else:
                logger.info(f"🟡 提现失败，原因：{withdraw_result['msg']}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.exception(f"🟡 提现失败，原因：{e}，原始数据: {withdraw_result}")

    def __request_withdrawal_for_userinfo(self) -> RspWithdrawal | dict:
        """
        发起提款请求，从而获取提款用户信息
        :return:
        """
        return self.__request_for_json(
            "GET",
            APIS.WITHDRAWAL,
            "获取提款用户信息 base_client",
            client=self.base_client,
            model=RspWithdrawal
        )

    def __pass_detect_and_read(self, part_api_path, full_api_path, *args, **kwargs):
        """
        尝试通过检测并且开始阅读
        :param part_api_path: 部分api路径
        :param full_api_path: 初始完整api路径（后面会随着阅读文章链接的不同改变）
        :return:
        """
        is_sleep = False
        is_need_push = False
        is_pushed = False
        while True:
            res_model = self.__request_for_do_read_json(full_api_path, is_sleep=is_sleep, is_pushed=is_pushed)
            ret_count = res_model.ret_count
            if ret_count == 3 and res_model.jkey is None:
                # 如果是3个，且没有jkey返回，则大概率就是未通过检测
                if res_model.is_pass_failed:
                    raise FailedPassDetect()
                else:
                    raise FailedPassDetect("🔴 貌似检测失败了，具体请查看上方报错原因")
            # 判断此次请求后返回的键值对数量是多少
            if ret_count == 2:
                # 如果是两个，可能有以下几种情况：
                if "本轮阅读已完成" == res_model.success_msg:
                    logger.info(f"🟢✔️ {res_model.success_msg}")
                    return
                elif res_model.is_pass_failed:
                    raise FailedPassDetect("🔴⭕️ 此账号今日已被标记，请明天再试!")
                is_need_push = True
            elif ret_count == 4:
                # 表示正处于检测中
                logger.info(f"🟡 此次检测结果为：{res_model.success_msg}")
                is_sleep = False
                is_need_push = True
            elif ret_count == 3 and res_model.jkey is not None:
                # 如果是3个，且有jkey返回，则表示已经通过检测
                if "成功" in res_model.success_msg:
                    logger.info(f"🟢✅️ {res_model.success_msg}")
                else:
                    logger.info(f"🟢❌️ {res_model.success_msg}")
                is_sleep = True
                # 没有看到要用什么，但是每次do_read都会请求2遍，故这里也添加调用
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
            else:
                raise Exception(f"🔴 do_read 出现未知错误，ret_count={ret_count}")

            if res_model.url is None:
                raise ValueError(f"🔴 返回的阅读文章链接为None, 或许API关键字更新啦, 响应模型为：{res_model}")
            else:
                # 打印文章内容
                self.__print_article_info(res_model.url)

            if is_need_push or self.ARTICLE_LINK_VALID_COMPILE.match(res_model.url) is None:
                logger.war(f"🟡🔺 阅读文章链接不是期待值，走推送通道!")
                is_pushed = self.wx_pusher_link(res_model.url)
                is_need_push = False
                is_sleep = True
            else:
                is_pushed = False

            # 重新构建 full_api_path
            full_api_path = self.__build_do_read_url_path(
                part_api_path,
                jkey=res_model.jkey
            )

    def wx_pusher_link(self, link) -> bool:
        return WxPusher.push_by_uid(self.app_token, self.wx_pusher_uid, "可乐阅读过检测", link)

    def __print_article_info(self, article_url):
        """
        解析文章信息
        :param article_url: 文章链接
        :return:
        """
        try:
            # 获取文章源代码
            article_page = self.__request_article_page(article_url)
        except:
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
        logger.info(ArticleInfo(
            article_url=article_url,
            article_biz=article_biz,
            article_title=article_title,
            article_author=article_author,
            article_desc=article_desc
        ))

    def __request_article_page(self, article_url: str):
        return self.__request_for_page(article_url, "请求文章信息 article_client", client=self.article_client)

    def __request_for_do_read_json(self, do_read_full_path: str, is_pushed: bool = False,
                                   is_sleep: bool = True) -> RspDoRead | dict:

        if is_sleep:
            t = self.push_delay[0] if is_pushed else random.randint(self.read_delay[0], self.read_delay[1])
            logger.info(f"等待检测完成, 💤 睡眠{t}秒" if is_pushed else f"💤 随机睡眠{t}秒")
            # 睡眠随机时间
            time.sleep(t)
        else:
            time.sleep(1)

        ret = self.__request_for_json(
            "GET",
            do_read_full_path,
            "请求do_read read_client",
            client=self.read_client,
            model=RspDoRead
        )
        # # 只要接口响应数据不改变，那么返回的格式就一定会是RspDoRead
        # if isinstance(ret, dict):
        #     # 以防万一，这里还是尽量做一下转换
        #     ret = RspDoRead(jkey=ret["jkey"], url=ret["url"])
        return ret

    def __build_do_read_url_path(self, do_read_url_part_path: str, **params) -> str:
        """构建完成阅读的完整路径（包括参数）"""
        ret = [do_read_url_part_path, "pageshow", f"r={random.random()}", f"iu={self.iu}"]
        for k, v in params.items():
            ret.append(f"{k}={v}")
        return "&".join(ret)

    def __parse_r_js_code(self, r_js_code: str, *params) -> str:
        """
        解析r.js代码
        :param r_js_code: r.js代码
        :return: 下一阶段的请求链接路径
        """
        if r := self.R_JS_CODE_COMPILE.search(r_js_code):
            return f"{r.group(1)}{params[0]}{r.group(2)}{params[1]}"
        else:
            raise RegExpError(self.R_JS_CODE_COMPILE)

    def __request_r_js_code(self, r_js_path: str) -> str:
        """请求r.js文件代码"""
        return self.__request_for_page(
            r_js_path,
            "请求r.js源代码, read_client",
            client=self.read_client,
            update_headers={
                "Referer": self.read_url.__str__(),
            }
        )

    def __parse_read_load_page(self, read_load_page_html: str) -> tuple:
        """
        解析正在加载页面源代码，提取需要的数据
        :param read_load_page_html:
        :return:
        """
        if r := self.READ_LOAD_PAGE_COMPILE.search(read_load_page_html):
            # 好像白写那么长的正则了，这个源代码中的内容再其他数据包中用的不多...
            # 算了懒得改了
            forstr = r.group(1)
            zs = r.group(2)
            # url = f"{r.group(4)}{forstr}{r.group(5)}{zs}"
            self.iu = r.group(3)
            r_js_path = r.group(6)
            r_js_version = r.group(7)
            return forstr, zs, r_js_path, r_js_version
        else:
            raise RegExpError(self.READ_LOAD_PAGE_COMPILE)

    def __request_for_read_load_page(self, read_url: URL) -> str:
        """
        请求正在加载页面
        :param read_url:
        :return:
        """
        return self.__request_for_page(
            read_url,
            "请求阅读加载页面 base_client",
            client=self.read_client
        )

    def __print_recommend_data(self, recommend_data: RspRecommend | dict):
        """
        打印推荐数据
        :param recommend_data:
        :return:
        """
        # 判断是否是预期模型
        if isinstance(recommend_data, RspRecommend):
            logger.info(recommend_data.data.user)
            infoView = recommend_data.data.infoView
            logger.info(infoView)
            if msg := infoView.msg:
                if "下一批" in msg or "微信限制" in msg:
                    raise PauseReadingTurnNextAndCheckWait(msg)

    def __request_for_read_url(self) -> URL:
        """
        获取阅读链接
        :return:
        """
        data: RspReadUrl | dict = self.__request_for_json(
            "GET",
            APIS.GET_READ_URL,
            "请求阅读链接 base_client",
            model=RspReadUrl,
            client=self.base_client
        )
        if isinstance(data, RspReadUrl):
            return data.link
        try:
            # 有时会返回这个 { "reload": 1 }，大概率Cookie是从PC微信上抓取的
            if data.get('reload') == 1:
                raise CookieExpired()
            return data['jump']
        except KeyError:
            raise RspAPIChanged(APIS.GET_READ_URL)

    def __request_recommend_json(self, referer: URL) -> RspRecommend | dict:
        """
        获取推荐数据
        :return:
        """
        recommend_data = self.__request_for_json("GET", APIS.RECOMMEND, "请求推荐数据 base_client", update_headers={
            "Referer": referer.__str__()
        }, model=RspRecommend, client=self.base_client)

        return recommend_data

    def __request_redirect_for_redirect(self) -> URL:
        """
        请求入口链接返回的重定向链接（这个链接用来获取首页源代码）
        :return:
        """
        self.base_client.cookies = self.cookie_dict
        return self.__request_for_redirect(self.base_full_url, "请求入口链接返回的重定向链接", client=self.base_client)

    def __request_entry_for_redirect(self) -> URL:
        """
        请求入口链接，从而获取重定向链接
        :return:
        """
        return self.__request_for_redirect(self.entry_url, "请求入口链接， main_client", client=self.main_client)

    def __request_for_json(self, method: str, url: str | URL, prefix: str, *args, client: httpx.Client = None,
                           model: Type[BaseModel] = None,
                           **kwargs) -> dict | BaseModel | str:
        """获取json数据"""

        update_headers = kwargs.pop("update_headers", {})
        ret_types = kwargs.pop("ret_types", [])
        if isinstance(ret_types, str):
            ret_types = [ret_types]
        ret = self.__request(method, url, prefix, *args, client=client, update_headers={
            "Accept": "application/json, text/plain, */*",
            **update_headers,
        }, ret_types=[RetTypes.JSON, *ret_types], **kwargs)
        if model is not None:
            ret = self.__to_model(model, ret)
        return ret

    @staticmethod
    def __to_model(model: Type[BaseModel], data: dict) -> BaseModel | dict:
        """
        将dict转换为 model
        :param model:
        :param data:
        :return:
        """
        try:
            return model.parse_obj(data)
        except ValidationError as e:
            logger.error(f"数据校验失败, 原因: {e}\n> 请通知作者更新 原始响应数据：{data}")
            return data

    def __request_for_page(self, url: str | URL, prefix: str, *args, client: httpx.Client = None, **kwargs) -> str:
        """获取网页源代码"""
        update_headers = kwargs.pop("update_headers", {})
        ret_types = kwargs.pop("ret_types", [])
        if isinstance(ret_types, str):
            ret_types = [ret_types]

        return self.__request("GET", url, prefix, *args, client=client, update_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            **update_headers,
        }, ret_types=[RetTypes.HTML, *ret_types], **kwargs)

    def __request_for_redirect(self, url: str | URL, prefix: str, *args, client: httpx.Client = None, **kwargs) -> URL:
        """获取重定向链接"""
        update_headers = kwargs.pop("update_headers", {})
        return self.__request("GET", url, prefix, *args, client=client, update_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            **update_headers,
        }, ret_types=RetTypes.REDIRECT, **kwargs)

    def __request(self, method: str, url: str | URL, prefix: str, *args, client: httpx.Client = None,
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
                client = httpx.Client(headers=self.__build_base_headers(self.account_config), timeout=30)
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
            logger.response(prefix, response)

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
                logger.exception(f"请求失败 JSONDecodeError：{e}")
            else:
                if RetTypes.TEXT in ret_types:
                    return response.text
        except Exception as e:
            logger.exception(f"请求失败：{e}")
        finally:
            if flag:
                client.close()
            self.lock.release()

    @property
    def is_wait_next_read(self):
        """是否等待下次读取"""
        ret = self.account_config.wait_next_read
        if ret is None:
            ret = self.klyd_config_data.wait_next_read
        return ret if ret is not None else False

    @property
    def read_url(self):
        return self._cache.get(f"read_url_{self.ident}")

    @read_url.setter
    def read_url(self, value):
        self._cache[f"read_url_{self.ident}"] = value

    @property
    def iu(self):
        return self._cache.get(f"iu_{self.ident}")

    @iu.setter
    def iu(self, value):
        self._cache[f"iu_{self.ident}"] = value

    @property
    def base_client(self):
        return self.__get_client("base")

    @property
    def read_client(self):
        return self.__get_client("read")

    @property
    def article_client(self):
        return self.__get_client("article", verify=False)

    def __get_client(self, client_name: str, headers: dict = None, verify: bool = True) -> httpx.Client:
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
                headers = self.__build_base_headers(self.account_config)
            client = httpx.Client(headers=headers, timeout=30, verify=verify)
            self._cache[client_name] = client
        return client

    @property
    def app_token(self):
        ret = self.account_config.appToken
        if ret is None:
            ret = self.klyd_config_data.appToken
        return ret

    @property
    def wx_pusher_uid(self):
        return self.account_config.uid

    @property
    def read_delay(self):
        delay = self.account_config.delay
        ret = delay.read_delay if delay is not None else self.klyd_config_data.delay.read_delay
        return ret

    @property
    def push_delay(self):
        delay = self.account_config.delay
        ret = delay.push_delay if delay is not None else self.klyd_config_data.delay.push_delay
        return ret

    @property
    def withdraw(self):
        ret = self.account_config.withdraw
        if ret == 0:
            ret = self.klyd_config_data.withdraw
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
            ret = self.klyd_config_data.aliAccount
        return ret

    @property
    def withdraw_type(self):
        """
        提现方式 默认微信提现
        :return:
        """
        ret = self.account_config.withdraw_type
        if ret is None:
            ret = self.klyd_config_data.withdraw_type
        return ret if ret is not None else "wx"

    @property
    def aliName(self):
        ret = self.account_config.aliName
        if not ret:
            ret = self.klyd_config_data.aliName
        return ret

    @property
    def ident(self):
        return threading.current_thread().ident

    @property
    def account_config(self) -> KLYDAccount:
        return self.accounts[logger.name]

    @property
    def origin_cookie(self):
        return self.account_config.cookie

    @property
    def cookie_dict(self) -> dict:
        return {key: value.value for key, value in SimpleCookie(self.origin_cookie).items()}

    def __build_base_headers(self, account_config: KLYDConfig = None):
        if account_config is not None:
            ua = account_config.ua
        else:
            ua = self.klyd_config_data.ua
        return {
            "User-Agent": ua if ua else "Mozilla/5.0 (Linux; Android 14; M2012K11AC Build/UKQ1.230804.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160083 MMWEBSDK/20231202 MMWEBID/4194 MicroMessenger/8.0.47.2560(0x28002F51) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "com.tencent.mm",
            "Upgrade-Insecure-Requests": "1"
        }


if __name__ == '__main__':
    KLYD()
