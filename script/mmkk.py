# -*- coding: utf-8 -*-
# mmkk.py created by MoMingLog on 28/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-28
【功能描述】
"""
import logging
import random
import re
import sys
from http.cookies import SimpleCookie
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from config import load_mmkk_config
from exception.mmkk import ReadValid, FailedFetchUK, FailedFetchArticleJSUrl, FailedFetchArticleJSVersion, \
    ArticleJSUpdated, CodeChanged, FailedFetchReadUrl, StopRun, PauseReading, ReachedLimit
from schema.mmkk import WorkInfo, User, WTMPDomain, MKWenZhang, AddGolds, MMKKConfig, MMKKAccount
from utils import *
from utils.push_utils import WxPusher

logger = mmkk_logger


class APIS:
    # 通用前缀路径
    COMMON = "/haobaobao"

    # API: 用户信息
    USER = f"{COMMON}/user"
    # API: 今日阅读统计
    WORKINFO = f"{COMMON}/workinfo"
    # API: 二维码相关信息
    WTMPDOMAIN = f"{COMMON}/wtmpdomain2"
    # API: 获取阅读文章
    MKWENZHANGS = f"{COMMON}/mkwenzhangs"
    # API: 阅读成功后增加金币
    ADDGOLDS = f"{COMMON}/addgolds2"
    # API: 提现页面
    WITHDRAW = f"{COMMON}/withdraw"
    # API: 将金币兑换为人民币
    GETGOLD = f"{COMMON}/getgold"
    # API: 将人民币进行提现
    GETWITHDRAW = f"{COMMON}/getwithdraw"


class MMKK:
    """猫猫看看阅读"""
    # 当前脚本版本号
    CURRENT_SCRIPT_VERSION = "0.1"
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"

    # 当前脚本适配的版本号
    CURRENT_ARTICLE_JS_VERSION = "10.0"
    # 当前脚本适配的基本链接
    ARTICLE_JS_DOMAIN = "https://nsr.zsf2023e458.cloud"
    # 当前脚本适配的V
    ARTICLE_JS_V = "6.0"
    # 当前脚本适配的js文件md5值
    ARTICLE_JS_CODE_MD5 = "3e29318b3ad6de1481ec03e57fa0e27c"
    # 固定的加密拼接的字符串
    ARTICLE_MD5_FIX_STR = "Lj*?Q3#pOviW"

    # 获取ejectCode的正则
    EJECTCODE_COMPILE = re.compile(r"setCookie.*?ejectCode.*?(\d+)'", re.S)
    # 获取 request_id
    WITHDRAW_REQ_ID_COMPILE = re.compile(r"request_id\s*=\s*['\"](.*?)['\"]")
    # 获取版本号的正则
    ARTICLE_JS_COMPILE = re.compile(r"<script(?!.*?(?:jquery|md5)).*?v(\d+\.\d+).*?script>", re.S)
    # 获取script的src属性链接
    ARTICLE_JS_SRC_COMPILE = re.compile(r"src\s*=\s*['\"](.*?)['\"]", re.S)
    # 获取article.js中的 schema + domain
    ARTICLE_JS_DOMAIN_COMPILE = re.compile(r"function\sread_jump_read.*?url['\"]:['\"](https?://.*?)/", re.S)
    # 获取article.js中的v参数
    ARTICLE_JS_V_COMPILE = re.compile(r"v=(\d+\.\d+)&uk", re.S)
    # 检测有效阅读链接
    ARTICLE_LINK_VALID_COMPILE = re.compile(
        r"^https://mp.weixin.qq.com/s\?__biz=.*?&mid=.*?&idx=\d*&sn=.*?&scene=\d*#wechat_redirect$")
    # 提取阅读文章链接的__biz值
    ARTICLE_LINK_BIZ_COMPILE = re.compile(r"__biz=(.*?)&")

    def __init__(self, config_data: MMKKConfig = load_mmkk_config()):
        self.mmkk_config_data = config_data

        if config_data.debug:
            logger.set_console_level(logging.DEBUG)

        self.accounts = config_data.account_data

        logger.info(f"【脚本信息】\n> 作者：{self.CURRENT_SCRIPT_AUTHOR}\n> 版本号：{self.CURRENT_SCRIPT_VERSION}\n")
        logger.info(
            f"【配置信息】\n> 账号数量：{len(self.accounts)}\n> 账号队列: {[name for name in self.accounts.keys()]}\n")
        time.sleep(1.5)
        # 入口链接
        self.entry_url = None
        # # 基本链接（schema://netloc）不包含路径
        # self.base_url = None
        # 构建基本请求头
        self.base_headers = self.__build_base_headers()
        # 初始客户端（不包括base_url）
        self.empty_client = httpx.Client(headers=self.base_headers, timeout=30)
        # 构建基本客户端
        self.base_client = httpx.Client(headers=self.base_headers, timeout=30)
        # 构建阅读客户端
        self.read_client = httpx.Client(headers=self.base_headers, timeout=30)
        # 构建提现客户端
        self.withdraw_client = httpx.Client(timeout=30)
        # 目前默认为1，不知道作用，生效时间10分钟，与后续的cookie绑定在一起
        self.ejectCode = "1"
        # 遍历所有用户数据
        for name, account in self.accounts.items():
            logger.set_tag(name)
            print(f"【{name}】任务开始".center(50, "-"))
            self.uk = None
            self.name = name
            # 获取用户数据
            self.current_user: MMKKAccount = account
            # 解析并设置用户cookie
            self.base_client.cookies = self.__parse_cookie(self.current_user.cookie)
            logger.info(
                f"【账号配置信息】\n> 账号名称: {name}\n> 提现方式: {self.withdraw_way}\n> 推送uid: {self.wx_pusher_uid}")
            # # 初始化链接
            # self.__init_userinfo()
            self.run()
            print(f"【{name}】任务结束".center(50, "-"))

        self.empty_client.close()
        self.base_client.close()
        self.read_client.close()
        self.withdraw_client.close()

    def run(self):
        try:
            self.__init_data()
            self.__start_read()
        except PauseReading | ReachedLimit as e:
            logger.war(f"🔘 {e}")
        except StopRun as e:
            logger.error(e)
            sys.exit(0)
        except Exception as e:
            logger.exception(e)
        finally:
            try:
                self.__request_withdraw()
            except Exception as e:
                logger.exception(e)

    @property
    def app_token(self):
        return self.mmkk_config_data.appToken

    @property
    def origin_cookie(self) -> str:
        return self.current_user.cookie

    @property
    def cookie(self) -> str:
        return "; ".join([f"{key}={value}" for key, value in self.base_client.cookies.items()])

    @property
    def wx_pusher_uid(self):
        return self.current_user.uid

    @property
    def read_delay(self):
        delay = self.current_user.delay
        ret = delay.read_delay if delay is not None else self.mmkk_config_data.delay.read_delay
        return ret

    @property
    def push_delay(self):
        delay = self.current_user.delay
        ret = delay.push_delay if delay is not None else self.mmkk_config_data.delay.push_delay
        return ret

    @property
    def withdraw(self):
        ret = self.current_user.withdraw
        if ret == 0:
            ret = self.mmkk_config_data.withdraw
        return ret

    @property
    def withdraw_way(self):
        if self.aliName and self.aliAccount:
            return f"支付宝\n> > 支付宝姓名: {self.aliName}\n> > 支付宝账号: {self.aliAccount}"
        return "微信"

    @property
    def aliAccount(self):
        ret = self.current_user.aliAccount
        if not ret:
            ret = self.mmkk_config_data.aliAccount

        return ret

    @property
    def aliName(self):
        ret = self.current_user.aliName
        if not ret:
            ret = self.mmkk_config_data.aliName
        return ret

    def __init_data(self):
        entry_url = EntryUrl.get_mmkk_entry_url()
        self.entry_url = entry_url
        logger.info(f"入口链接：{entry_url}")
        home_url = self.__request_entry(entry_url)
        url_schema = urlparse(home_url)
        base_url = f"{url_schema.scheme}://{url_schema.netloc}"
        self.base_client.base_url = base_url
        self.base_client.headers.update({
            "Upgrade-Insecure-Requests": "1"
        })
        self.withdraw_client.base_url = base_url
        # 获取主页源代码
        homepage_html = self.__request_homepage(url_schema.path, url_schema.query)
        if "存在违规操作" in homepage_html:
            raise StopRun("账号已被封")
        self.base_client.headers.pop("Upgrade-Insecure-Requests")
        self.base_client.headers.update({
            "Referer": home_url,
        })
        # 固定延迟，防止执行过快
        time.sleep(1.5)
        # 获取用户信息
        user = self.__request_user()
        logger.info(user)
        # 固定延迟，防止执行过快
        time.sleep(0.5)
        # 获取今日阅读统计情况
        workInfo = self.__request_workInfo()
        logger.info(workInfo)
        self.base_client.headers.update({
            "Origin": base_url
        })
        # 获取提现页面
        withdraw_page = self.__request_withdraw_page()
        if r := self.WITHDRAW_REQ_ID_COMPILE.search(withdraw_page):
            self.req_id = r.group(1)

    def __start_read(self):
        time.sleep(1)
        # 获取阅读二维码链接
        wtmpDomain = self.__request_WTMPDomain()
        logger.info(wtmpDomain)
        qrCode_url_schema = urlparse(wtmpDomain.data.domain)
        try:
            self.uk = qrCode_url_schema.query.split("&")[0].split("=")[1]
        except:
            raise FailedFetchUK()

        self.read_client.headers.update({
            "Host": qrCode_url_schema.netloc,
            "Origin": f"{qrCode_url_schema.scheme}://{qrCode_url_schema.netloc}"
        })
        time.sleep(1.5)
        # 获取加载页面
        load_homepage = self.__request_load_page(wtmpDomain)
        v = self.__prepare_read_before(load_homepage)
        while True:
            time.sleep(1.5)
            params = self.__build_request_article_args(self.read_client.base_url.netloc, timestamp(13), v)
            article_res_model = self.__request_article_for_link(params)

            article_url = article_res_model

            if article_url is None:
                logger.error(f"获取阅读文章失败!")
                return

            if isinstance(article_res_model, MKWenZhang):
                article_url = article_res_model.data.link

            is_pass_push = False
            is_pushed = False

            # 检测文章链接是否符合
            if not self.ARTICLE_LINK_VALID_COMPILE.match(article_url):
                logger.war(f"\n🟡 阅读文章链接不是期待值，走推送通道!")
                is_pass_push = True
                is_pushed = self.wx_pusher_link(article_url)

            # 提取__biz值
            if r := self.ARTICLE_LINK_BIZ_COMPILE.search(article_url):
                __biz = r.group(1)
            else:
                __biz = ""

            # 检测漏网之鱼（不知道有没有用，我看大佬的代码中有这些，我个人能提供抓包的cookie有限，故只能这样）
            if __biz in self.mmkk_config_data.biz_data and not is_pushed:
                logger.war(f"\n🔶 检测到漏网之鱼，走推送通道")
                is_pass_push = True
                is_pushed = self.wx_pusher_link(article_url)

            # 判断是否走了推送通道
            if is_pass_push and not is_pushed:
                raise Exception(f"检测到用户 [{self.name}] 推送失败，停止此用户的运行!")

            # 尝试获取文章内容
            self.__request_article(article_url)

            # 开始尝试获取奖励和奖励信息
            self.__request_add_gold(params)

    def __request_add_gold(self, params: dict, is_pushed: bool = False) -> AddGolds | bool:
        """
        增加金币

        :return:
        """

        t = self.push_delay[0] if is_pushed else random.randint(self.read_delay[0], self.read_delay[1])
        logger.info(f"随机睡眠{t}秒")
        # 睡眠随机时间
        time.sleep(t)
        params = {
            "uk": params.get("uk"),
            "psign": params.get("mysign"),
            "time": t
        }
        response = self.read_client.get(APIS.ADDGOLDS, params=params)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"增加金币，read_client 用的请求头为：{response.request.headers}")
        res_json = None
        try:
            res_json = response.json()
            addGoldsModel = AddGolds.model_validate(res_json)
            logger.info(addGoldsModel)
            return addGoldsModel
        except ValidationError as e:
            logger.error(f"增加金币数据模型验证失败，请将下方错误信息截图给作者，方便改进\n{e}")
            if res_json is not None:
                logger.error(res_json)
                logger.info(f"正在尝试挽回错误...")
                if res_json["msg"] == "success":
                    data = res_json.get("data")
                    logger.info(
                        f"🟢 阅读成功! \n> 增加金币: {data['gold']}\n> 已阅读篇数: {data['gold']}\n> 共获得金币: {data['day_read']}\n> 剩余文章数: {data['remain_read']}")
                    return True
        except Exception as e:
            logger.exception(f"阅读异常, 原因: {e}")

    def __request_article(self, article_url: str):
        """
        获取文章内容
        :param article_url:
        :return:
        """
        # 重置请求头环境
        self.empty_client.headers = self.__build_base_headers()
        # 请求文章内容（源代码）
        response = self.empty_client.get(article_url)
        article_html = response.text
        logger.debug(f"请求的链接为: {response.request.url}")
        logger.debug(f"article_html，empty_client 用的请求头为：{response.request.headers}")

    @staticmethod
    def __parse_cookie(cookie_str: str) -> dict:
        """
        将字符串类型的cookie转换为字典
        :param cookie_str: 字符串类型的cookies
        :return: 包含cookie信息的字典
        """
        return {key: value.value for key, value in SimpleCookie(cookie_str).items()}

    def __build_base_headers(self):
        """
        构建基本请求头
        :return:
        """
        ua = self.accounts.get("ua")
        if ua is None:
            ua = self.accounts.get("User-Agent")

        return {
            "User-Agent": ua if ua else "Mozilla/5.0 (Linux; Android 14; M2012K11AC Build/UKQ1.230804.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 XWEB/1160083 MMWEBSDK/20231202 MMWEBID/4194 MicroMessenger/8.0.47.2560(0x28002F50) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "X-Requested-With": "com.tencent.mm",
        }

    def __build_withdraw_headers(self):
        """
        构建提现请求要用到的请求头
        :return:
        """
        headers = self.__build_base_headers()
        headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": self.origin_cookie,
            "Host": self.withdraw_client.base_url.netloc,
            "Origin": self.base_client.headers.get("Origin"),
            "Proxy-Connection": "keep-alive",
            "Referer": f"{self.withdraw_client.base_url}{APIS.WITHDRAW}",
            "X-Requested-With": "XMLHttpRequest",
        })
        return headers

    def __prepare_read_before(self, read_homepage: str) -> str:
        """
        阅读前期准备
        :param read_homepage: “阅读加载中, 请稍后”的页面源代码
        :return:
        """
        # 判断article.js版本是否更新
        if r := self.ARTICLE_JS_COMPILE.search(read_homepage):
            # 提取最新版本号
            latest_version = r.group(1)
            try:
                if r := self.ARTICLE_JS_SRC_COMPILE.search(r.group(0)):
                    article_js_url = r.group(1)
                else:
                    raise FailedFetchArticleJSUrl()
            except Exception as e:
                raise FailedFetchArticleJSUrl()
        else:
            raise FailedFetchArticleJSVersion()

        # 检查是否更新
        if latest_version != self.CURRENT_ARTICLE_JS_VERSION:
            raise ArticleJSUpdated(latest_version)

        article_js_url_schema = urlparse(article_js_url)

        self.empty_client.headers.update({
            "Host": article_js_url_schema.netloc
        })

        response = self.empty_client.get(article_js_url)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"article_js_url，empty_client 用的请求头为：{response.request.headers}")

        if md5(response.text) != self.ARTICLE_JS_CODE_MD5:
            raise CodeChanged()

        # 尝试从article_js_url中提取url的 protocol + domain（源码中貌似不会加密链接，故可以尝试一下）
        # 好像也没有太大的必要，因为js文件中是固定的字符串，如果发生改动，则md5值一定会改变
        # 不过这里也可以先尝试一下，万一做成了通用脚本，动态改变。后面说不定就可以不用上方的判断了，当然这是想象中的。

        # 提取protocol + domain
        if r := self.ARTICLE_JS_DOMAIN_COMPILE.search(response.text):
            self.read_client.base_url = r.group(1)
        else:
            # 目前V10.0版本都是用的这个
            self.read_client.base_url = self.ARTICLE_JS_DOMAIN

        self.read_client.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Host": self.read_client.base_url.netloc,
            "Upgrade-Insecure-Requests": "1"
        })

        if r := self.ARTICLE_JS_V_COMPILE.search(response.text):
            v = r.group(1)
        else:
            v = self.ARTICLE_JS_V

        return v

    def __request_article_for_link(self, params: dict):
        """
        发起请求，获取阅读文章的跳转链接
        :param params:
        :return:
        """
        res_json = None
        try:
            # 开始发起请求，获取阅读文章链接
            response = self.read_client.get(APIS.MKWENZHANGS, params=params)
            logger.debug(f"请求链接为: {response.url}")
            logger.debug(f"获取阅读文章的跳转链接，read_client 用的请求头为：{response.request.headers}")
            res_json = response.json()
            if res_json.get("errcode") == 407:
                msg = res_json.get('msg')
                if "继续阅读" in msg:
                    raise PauseReading(msg)
                elif "上限" in msg:
                    raise ReachedLimit(msg)
                raise ReadValid(msg)
            article_res_model = MKWenZhang.model_validate(response.json())
            logger.info(f"获取阅读文章链接成功：{article_res_model.data.link}")
            # self.wx_pusher_link(article_res_model.data.link)
            return article_res_model
        except PauseReading | ReachedLimit as e:
            raise e
        except ReadValid as e:
            raise e
        except ValidationError as e:
            logger.error(f"发生类型验证错误，请截图下方报错原因并提交给作者，以供改进: {e}")
            if res_json is not None:
                logger.error(res_json)
                logger.info(f"正在尝试挽回错误...")
                return res_json.get("data", {}).get("link")
        except Exception as e:
            raise FailedFetchReadUrl(e)

    # 构建获取【返回阅读文章链接】的请求链接参数
    def __build_request_article_args(self, host, t, v=ARTICLE_JS_V):
        return {
            "time": t,
            # 具体加密逆向过程请查看MMKK.md
            "mysign": md5(f"{host}{t}{self.ARTICLE_MD5_FIX_STR}"),
            "v": v,
            "uk": self.uk
        }

    # 获取“正在加载”页面源代码
    def __request_load_page(self, wtmpDomain: WTMPDomain) -> str:
        """
        获取“正在加载”页面（前往文章的中转页面）
        :param wtmpDomain: 文章阅读二维码链接
        :return: 文章阅读页面源代码
        """
        response = self.read_client.get(wtmpDomain.data.domain)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"获取“正在加载”页面，read_client 用的请求头为：{response.request.headers}")
        html = response.text
        return html

    # 获取文章阅读二维码相关信息
    def __request_WTMPDomain(self) -> WTMPDomain:
        """
        获取文章阅读二维码链接
        :return:
        """
        self.base_client.cookies = self.__parse_cookie(f"ejectCode={self.ejectCode}; {self.origin_cookie}")
        response = self.base_client.post(APIS.WTMPDOMAIN)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"获取文章阅读二维码链接，base_client 用的请求头为：{response.request.headers}")
        try:
            res_json = response.json()
            wtmpDomain = WTMPDomain.model_validate(res_json)
            logger.info(f"获取文章阅读二维码信息成功")
            return wtmpDomain
        except Exception as e:
            logger.exception(f"账号[{self.name}]获取文章阅读二维码信息失败, {e}")

    # 请求今日阅读相关信息
    def __request_workInfo(self) -> WorkInfo:
        """
        获取文章阅读篇数和金币
        :return:
        """
        self.base_client.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        })
        response = self.base_client.get(APIS.WORKINFO)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"获取文章阅读篇数和金币，base_client 用的请求头为：{response.request.headers}")
        try:
            res_json = response.json()
            workInfo = WorkInfo.model_validate(res_json)
            return workInfo
        except Exception as e:
            logger.exception(f"账号[{self.name}]获取文章阅读篇数和金币失败, {e}")

    # 请求用户信息
    def __request_user(self) -> User:
        """
        获取用户信息
        :return:
        """
        self.base_client.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        })
        response = self.base_client.get(APIS.USER)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"获取用户信息，base_client 用的请求头为：{response.request.headers}")

        try:
            res_json = response.json()
            user = User.model_validate(res_json)
            logger.info(f"获取用户信息成功")
            return user
        except Exception as e:
            logger.exception(f"账号[{self.name}]获取用户信息失败, {e}")

    # 请求主页
    def __request_homepage(self, path, query):
        """
        请求首页
        :param path: 路径
        :param query: 参数
        :return:
        """
        response = self.base_client.get(f"{path}?{query}")
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"请求首页，base_client 用的请求头为：{response.request.headers}")

        homepage_html = response.text
        if "eject" not in self.origin_cookie:
            if r := MMKK.EJECTCODE_COMPILE.search(homepage_html):
                self.ejectCode = r.group(1)
        # 请求入口链接
        return homepage_html

    def __request_entry(self, entry_url: str = None) -> str:
        """
        请求入口链接，获取后续的请求链接
        :param entry_url: 入口链接
        :return:
        """
        entry_url_schema = urlparse(entry_url)
        self.empty_client.headers.update({
            "Host": entry_url_schema.netloc
        })

        response = self.empty_client.get(entry_url)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"请求入口链接，empty_client 用的请求头为：{response.request.headers}")

        if response.status_code != 302:
            raise Exception(f"请求入口链接失败")

        redirect_url = response.headers.get("Location")

        logger.debug(f"请求入口链接成功, {redirect_url}")

        redirect_url_schema = urlparse(redirect_url)
        self.base_client.headers.update({
            "Host": redirect_url_schema.netloc
        })

        response = self.base_client.get(redirect_url)
        logger.debug(f"请求链接为: {response.url}")
        logger.debug(f"请求入口链接，base_client 用的请求头为：{response.request.headers}")

        # 再次获取链接
        home_url = response.headers.get("Location")

        if "open.weixin.qq.com/connect/oauth2" in home_url:
            raise Exception(f"{self.name} cookie已失效，请重新获取cookie")
        logger.debug(f"账号[{self.name}]请求重定向链接成功, {home_url}")

        return home_url

    def __request_withdraw(self):
        """
        发起提现请求
        :return:
        """
        workInfo: WorkInfo = self.__request_workInfo()
        gold = int(int(workInfo.data.remain_gold) / 1000) * 1000
        money = workInfo.data.remain
        logger.info(f"【账户余额统计】\n> 待提现金额：{money}元\n> 待兑换金币: {gold}金币")
        self.withdraw_client.headers = self.__build_withdraw_headers()
        # 判断是否有金币，或者期待提现金额小于账户余额
        if gold != 0:
            # 表示可以提现
            if new_money := self.__request_exchange_gold(gold, money):
                money = new_money

        if money >= self.withdraw:
            self.__request_withdraw_money()
        else:
            logger.war(f"账户余额不足 {self.withdraw} 元, 提现停止!")

    def __request_withdraw_money(self):
        flag = True if self.aliName and self.aliAccount else False
        payload = {
            "signid": self.req_id,
            "ua": "2" if flag else "0",
            "ptype": "1" if flag else "0",
            "paccount": self.aliAccount,
            "pname": self.aliName
        }
        response = self.withdraw_client.post(APIS.GETWITHDRAW, data=payload)
        logger.debug(f"链接地址：{response.request.url}")
        logger.debug(f"人民币提现, withdraw_client 请求头为：{response.request.headers}")

        try:
            res_json = response.json()
            logger.info(f"提现结果：{res_json['msg']}")
        except Exception as e:
            logger.exception(f"提现失败，原因：{e}")

    def __request_exchange_gold(self, gold, money):
        """
        将金币兑换成现金
        :param gold: 当前金币余额
        :param money: 当前现金余额
        :return:
        """
        payload = {
            "request_id": self.req_id,
            "gold": str(gold)
        }
        response = self.withdraw_client.post(APIS.GETGOLD, data=payload)
        logger.debug(f"链接地址：{response.request.url}")
        logger.debug(f"兑换金币, withdraw_client 请求头为：{response.request.headers}")
        try:
            res_json = response.json()
            # 代码没写完，测试号都快封完了
            if res_json.get("errcode") == 0:
                withdrawBalanceNum = money + float(res_json["data"]["money"])
                logger.info(f"✅ 金币兑换为现金成功，开始提现，预计到账 {withdrawBalanceNum} 元")
                return withdrawBalanceNum
            else:
                logger.info(f"❌ 金币兑换为现金失败，原因：{res_json['msg']}")
        except Exception as e:
            logger.exception(f"金币兑换现金失败，原因：{e}")

    def __request_withdraw_page(self):
        """
        获取提现页面地址
        :return:
        """
        self.base_client.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/tpg,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Upgrade-Insecure-Requests": "1"
        })
        response = self.base_client.get(APIS.WITHDRAW)
        logger.debug(f"获取提现页面地址，base_client 请求头为: {response.request.headers}")
        return response.text

    def wx_pusher_link(self, link) -> bool:
        return WxPusher.push_by_uid(self.app_token, self.wx_pusher_uid, "猫猫看看阅读过检测", link)


if __name__ == '__main__':
    MMKK()
