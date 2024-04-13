# -*- coding: utf-8 -*-
# xyy_v2.py created by MoMingLog on 10/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-10
【功能描述】
"""
import re
import time
from typing import Type

import httpx
from httpx import URL
from pydantic import BaseModel

from config import load_xyy_config
from exception.common import RegExpError, FailedPushTooManyTimes, StopReadingNotExit, PauseReadingTurnNextAndCheckWait
from exception.klyd import FailedPassDetect
from schema.xyy import XYYConfig, WTMPDomain, Gold, ArticleUrl
from script.common.base import WxReadTaskBase
from utils import EntryUrl, timestamp


class APIS:
    """下方内容仅供参考，大部分API，由主程序自动提取生成"""
    # API通用前缀（程序自动解析获取）
    COMMON = "/yunonline/v1"

    # API: 金币情况(阅读收入)
    # 程序自动提取并生成
    GOLD_INFO = f"{COMMON}/gold"
    # API: 阅读跳转链接
    # 程序自动提取并生成
    JUMP_READ = f"{COMMON}/wtmpdomain2"
    # API: 将金币转成金额
    GOLD_TO_MONEY = f"{COMMON}/user_gold"
    # API: 提款
    WITHDRAW = f"{COMMON}/withdraw"

    # API: 获取文章链接（不共用同一域名）
    # 程序自动提取并生成
    ARTICLE_URL = "/dyuedus"
    # API: 增加金币（同上）
    ADD_GOLD = "/jinbicp"


class XYYV2(WxReadTaskBase):
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "2.0.1"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-04-10"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-13"
    # 当前任务名称
    CURRENT_TASK_NAME = "微信阅读任务"

    # 主页关键JS内容提取
    HOMEPAGE_JS_COMPILE = re.compile(r"<script\stype=['\"]text/javascript['\"]>(.*?)</script>", re.S)

    # 从主页JSCode中提取domain（包括schema和基本path）、跳转阅读API、unionid、阅读收入API
    JS_CODE_COMPILE = re.compile(
        r"var.*?domain\s*=\s*['\"](.*?)['\"].*?(?:跳转阅读)?read_jump_read.*?ajax.*?url:\s*.*?['\"](.*?)['\"],.*?websocket.*?\?unionid=(.*?)&.*?(?:阅读收入)?.*?get_gold_read.*?url:\s*.*?['\"](.*?)['\"].*?['\"](.*?)['\"].*?\}",
        re.S)

    # 从阅读加载页提取数据，目前包括（“增加金币”接口、psgn加密是否被注释、“获取文章”接口）
    JUMP_READ_PAGE_COMPILE = re.compile(
        r"(?:金币接口)?getGold.*?url.*?['\"](.*?)['\"].*?['\"](.*?)['\"].*?['\"](.*?)['\"].*?(//\s*var\spsgn\s*=\s*hex_md5\(.*?\)).*?url.*?['\"](.*?)['\"].*?['\"](.*?)['\"].*?['\"](.*?)['\"],",
        re.S)

    # 从主页提取提现链接
    EXCHANGE_URL_COMPILE = re.compile(r"找回原账户.*?href=['\"](.*?)['\"]>提现", re.S)

    # 从提现页面提取 request_id
    REQUEST_ID_COMPILE = re.compile(r"var\srequest_id\s*=\s*['\"](.*?)['\"];?", re.S)
    # 从提现页面提取当前金额和金币数
    EXCHANGE_INFO_COMPILE = re.compile(r"id=['\"](?:exchange_money|exchange_gold)['\"]>(\d+\.?\d*)</p>", re.S)
    # 从提现页面提取支付宝提现账号
    EXCHANGE_ALIPAY_COMPILE = re.compile(r"var\s(?:raccount|rname)\s*=\s*['\"](.*?)['\"];?", re.S)
    # 从提现页面提取提现API
    EXCHANGE_API_COMPILE = re.compile(
        r"提现失败，请稍后再试.*?else.*?ajax.*?url.*?['\"](.*?)['\"].*?success.*?ajax.*?url.*?['\"](.*?)['\"]", re.S)

    def __init__(self, config_data: XYYConfig = load_xyy_config(), run_read_task: bool = True):

        self.detected_biz_data = config_data.biz_data or []
        self.run_read_task = run_read_task
        super().__init__(config_data, logger_name="小阅阅", load_detected=True)

    def init_fields(self, retry_count=3):
        self.entry_url = self.request_for_redirect(
            self.entry_url,
            "入口页面重定向 main_client",
            client=self.main_client
        )
        if self.entry_url is None:
            if retry_count > 0:
                self.logger.war(f"入口页面重定向失败, 3秒后重试, 剩余重试次数：{retry_count - 1}")
                time.sleep(3)
                return self.init_fields(retry_count - 1)
            raise Exception("入口页面重定向失败, 程序停止执行")

        self.logger.debug(f"第 1 次入口重定向链接： {self.entry_url}")

    def run(self, name, *args, **kwargs):
        is_already = False

        # 从配置中读取 cookie 数据，并配置到 base_client
        self.base_client.cookies = self.cookie_dict
        self.homepage_url = self.request_for_redirect(
            self.entry_url,
            "入口页面2次重定向 base_client",
            client=self.base_client
        )
        self.logger.debug(f"获取主页入口链接： {self.homepage_url}")

        # 获取主页源代码
        homepage_html = self.request_for_page(
            self.homepage_url,
            "获取主页源代码 base_client",
            client=self.base_client
        )
        while "参数错误" in homepage_html:
            time.sleep(3)
            homepage_html = self.request_for_page(
                self.homepage_url,
                "获取主页源代码 base_client",
                client=self.base_client
            )

        if homepage_html:
            if r := self.HOMEPAGE_JS_COMPILE.search(homepage_html):
                js_code = r.group(1)

                if r := self.JS_CODE_COMPILE.search(js_code):
                    # 获取 domain 目前：http://1712719612.xxl860.top/yunonline/v1/
                    self.domain = r.group(1)
                    # 给 base_client 分析并设置 base_url
                    self.parse_base_url(self.domain, client=self.base_client)
                    # 自动解析并赋值【通用API前缀】
                    domain_url = URL(self.domain)
                    # 赋值 API 公共前缀
                    APIS.COMMON = domain_url.path
                    # 判断是否 "/" 结尾
                    if APIS.COMMON.endswith("/"):
                        # 是，则去掉末尾 "/" 按理为: /yunonline/v1
                        APIS.COMMON = APIS.COMMON[:-1]

                    # API:【跳转阅读链接】 目前 wtmpdomain2
                    jump_read_path = r.group(2)
                    # 如果不是以 “/” 开头
                    if not jump_read_path.startswith("/"):
                        # 则自动添加
                        jump_read_path = f"/{jump_read_path}"
                    #  API:【跳转阅读链接】
                    APIS.JUMP_READ = f"{APIS.COMMON}{jump_read_path}"

                    # 获取 union_id 目前：oZdBp0-uj9HlHHq9iZJ2WWe6lTyU
                    self.union_id = r.group(3)

                    # 获取阅读收入API 目前 4: gold?unionid= 5: &time=
                    # 这里自动填充unionid，time需要在请求的时候自动填充
                    api_gold = f"{r.group(4)}{self.union_id}{r.group(5)}"

                    if not api_gold.startswith("/"):
                        api_gold = f"/{api_gold}"

                    # API:【金币情况(阅读收入)】
                    APIS.GOLD_INFO = f"{APIS.COMMON}{api_gold}"

                    # 获取并打印金币数据
                    gold_info = self.__request_gold_info()
                    self.logger.info(gold_info)

                    # 设置当前阅读数量
                    self.current_read_count = int(gold_info.data.day_read)

                    is_already = True
                else:
                    raise RegExpError(self.JS_CODE_COMPILE)
            else:
                raise RegExpError(self.HOMEPAGE_JS_COMPILE)
        else:
            self.logger.error(f"🔴 获取主页源代码失败, 响应数据为：{homepage_html}")
            return

        if is_already:
            if self.run_read_task:
                self.logger.info("🟢 阅读准备就绪, 开始运行")
            self.__already_to_run(homepage_html)
        else:
            self.logger.error("🔴 阅读准备未就绪, 请检查代码!")
            return

    def __already_to_run(self, homepage_html: str = None):
        jump_read_url = self.get_jump_read_url()

        # 添加请求头项
        self.read_client.headers.update({
            "Referer": jump_read_url
        })

        self.parse_base_url(jump_read_url, client=self.read_client)
        if self.run_read_task:
            self.parse_jump_read_url(jump_read_url)
        # 获取阅读加载页源代码
        jump_read_page = self.__request_jump_read_page(jump_read_url)
        if jump_read_page:
            try:
                # 判断是否需要运行阅读任务
                if not self.run_read_task:
                    return
                self.__start_read(jump_read_url, jump_read_page)
            finally:
                if homepage_html is not None:
                    self.__request_withdraw(homepage_html)
        else:
            self.logger.error("🔴 获取跳转阅读页面失败, 请检查代码!")

    def __request_withdraw(self, homepage_html):

        # 判断是否要进行提现操作
        if not self.is_withdraw:
            self.logger.war(f"🟡💰 提现开关已关闭，已停止提现任务")
            return

        if r := self.EXCHANGE_URL_COMPILE.search(homepage_html):
            exchange_page_url = r.group(1)

            # 更新unionid
            self.union_id = URL(exchange_page_url).params.get("unionid")

            # 获取提现页面
            exchange_page = self.request_for_page(
                exchange_page_url,
                "请求提现页面 base_client",
                client=self.base_client
            )
            if exchange_page:
                self.base_client.headers.update({
                    "Referer": exchange_page_url
                })
                if r := self.REQUEST_ID_COMPILE.search(exchange_page):
                    self.request_id = r.group(1)
                else:
                    raise RegExpError(self.REQUEST_ID_COMPILE)

                # 尝试提取API
                if r := self.EXCHANGE_API_COMPILE.search(exchange_page):
                    # API: 金币转金额
                    gold_to_money_api = r.group(1) if r.group(1).startswith("/") else f"/{r.group(1)}"
                    APIS.GOLD_TO_MONEY = f"{APIS.COMMON}{gold_to_money_api}"
                    # API: 提现
                    withdraw_api = r.group(2) if r.group(2).startswith("/") else f"/{r.group(2)}"
                    APIS.WITHDRAW = f"{APIS.COMMON}{withdraw_api}"

                # 提取并打印提现信息
                if r := self.EXCHANGE_INFO_COMPILE.findall(exchange_page):
                    if len(r) == 2:
                        money = float(r[0])
                        gold = float(r[1])
                        self.logger.info("\n".join([
                            "【提款用户信息】",
                            f"> 当前余额: {r[0]} 元",
                            f"> 当前金币: {r[1]} 个"
                        ]))
                        # 将金币转成金额
                        res_json = self.__request_gold_to_money(gold)
                        res_money = res_json.get("data", {}).get("money", 0)
                        if res_money != 0:
                            if isinstance(res_money, str):
                                res_money = float(res_money)
                            money += res_money
                            self.logger.info(f"🟢💰 金币转换成功, 当前余额为：{money} 元")

                        if money < 0.3 or money < self.withdraw:
                            self.logger.war(f"🟡💰 账户余额 [{money}] 不满足提现要求，停止提现")
                            return

                        # 提取支付宝信息
                        if r := self.EXCHANGE_ALIPAY_COMPILE.findall(exchange_page):
                            try:
                                u_ali_account = r[0] if r[0] is not None else self.aliAccount
                                u_ali_real_name = r[1] if r[1] is not None else self.aliName
                            except:
                                u_ali_account = self.aliAccount
                                u_ali_real_name = self.aliName
                        else:
                            raise RegExpError(self.EXCHANGE_ALIPAY_COMPILE)
                        # 提现
                        self.__request_do_withdraw(money, u_ali_account, u_ali_real_name)

                    else:
                        raise RegExpError(self.EXCHANGE_INFO_COMPILE)
                else:
                    raise RegExpError(self.EXCHANGE_INFO_COMPILE)
            else:
                self.logger.error("🔴💰 获取提现页面失败, 请检查代码!")
        else:
            raise RegExpError(self.EXCHANGE_URL_COMPILE)

    def __request_do_withdraw(self, money, u_ali_account=None, u_ali_real_name=None):
        """提款请求"""
        data = {
            "unionid": self.union_id,
            "signid": self.request_id,
            "ua": "2",
            "ptype": "0",
            "paccount": "",
            "pname": ""
        }
        if self.withdraw_type == "ali":
            self.logger.info("💰 开始进行支付宝提现操作...")
            data.update({
                "ptype": "1",
                "paccount": u_ali_account,
                "pname": u_ali_real_name
            })
        elif self.withdraw_type == "wx":
            self.logger.info("💰 开始进行微信提现操作...")
        else:
            raise ValueError(f"💰 不支持的提现方式：{self.withdraw_type}")

        # 提现
        withdraw_result = self._request_for_json(
            "POST",
            APIS.WITHDRAW,
            "提现 base_client",
            client=self.base_client,
            data=data
        )

        if isinstance(withdraw_result, list):
            withdraw_result: dict = withdraw_result[0]
        msg = withdraw_result.get("msg", "")
        if "success" in msg:
            self.logger.info(f"🟢💰 提现成功! 本次提现金额: {money} 元")
        else:
            self.logger.error(f"🔴💰 提现失败!")

    def __request_gold_to_money(self, gold) -> dict:
        """金币转金额"""
        # 取整数
        if isinstance(gold, str):
            gold = int(gold)

        if gold < 3000:
            return {}

        gold = int(gold - gold % 1000)

        return self._request_for_json(
            "POST",
            APIS.GOLD_TO_MONEY,
            "金币转金额 base_client",
            client=self.base_client,
            update_headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            data={
                "unionid": self.union_id,
                "request_id": self.request_id,
                "gold": str(gold)
            }
        )

    def __start_read(self, jump_read_url, jump_read_page):
        if r := self.JUMP_READ_PAGE_COMPILE.search(jump_read_page):
            # 提取并生成“增加金币”API及其路径参数
            add_gold_api = f"{r.group(1)}{self.uk}{r.group(2)}{{sleep_time}}{r.group(3)}{timestamp(13)}"

            if not add_gold_api.startswith("/"):
                add_gold_api = f"/{add_gold_api}"

            # 缺少睡眠时间参数，后续需要进行替换
            APIS.ADD_GOLD = add_gold_api

            psgn = r.group(4).strip()
            if not psgn.startswith("//"):
                # 这里需要进行md5加密，目前并未发现有实际的加密执行
                raise Exception("🔴 发现阅读加载页 psgn 启用了 hex_md5 加密，请通知作者实现此算法!")
            else:
                # 截止脚本2024.04.10, psgn为固定值( 直接赋值，不是变量，但不代表后端返回的代码中不会变化，故这里选择从源代码中提取API路径参数)
                article_api = f"{r.group(5)}{self.uk}{r.group(6)}{{timestamp}}{r.group(7)}"
                if not article_api.startswith("/"):
                    article_api = f"/{article_api}"
                APIS.ARTICLE_URL = article_api
            # 计算当前阅读轮数
            turn_count = self.current_read_count // 30 + 1
            # 计算当前轮数的阅读篇数
            read_count = self.current_read_count % 30 + 1
            # 暂存文章链接数据
            article_map = {}
            while True:
                # 更新 API
                APIS.ARTICLE_URL = APIS.ARTICLE_URL.replace("{timestamp}", str(timestamp(13)))
                # 获取文章链接
                article_url_model = self.__request_article_url()
                # 判断文章链接是否获取成功
                if article_url_model:
                    if "分钟后" in article_url_model.msg:
                        self.logger.info(f"🟢📖 本轮阅读已完成 {article_url_model.msg}")
                        self.__request_jump_read_page(jump_read_url)
                        raise PauseReadingTurnNextAndCheckWait(article_url_model.msg)
                    elif "存在违规操作" in article_url_model.msg:
                        self.logger.error(f"🔴⭕️ {article_url_model.msg}")
                        return
                    elif "阅读暂时无效" in article_url_model.msg:
                        a = article_map.get(f"{turn_count} - {read_count - 1}")
                        if a:
                            self.new_detected_data.add(a)
                        raise StopReadingNotExit(article_url_model.msg)
                    elif "今日阅读已达上限" in article_url_model.msg:
                        raise StopReadingNotExit(article_url_model.msg)
                    elif "success" == article_url_model.msg:
                        if isinstance(article_url_model, ArticleUrl):
                            article_url = article_url_model.data.link
                        else:
                            article_url = article_url_model.get("data", {}).get("link")

                        if not article_url:
                            raise Exception(f"🔴 获取阅读文章链接失败, 原始响应数据: {article_url_model}")

                        # 打印阅读情况
                        if self.current_read_count != 0:
                            msg = f"🟡📖 准备阅读第[{turn_count} - {read_count}]篇, 已成功阅读[{self.current_read_count}]篇"
                        else:
                            msg = f"🟡📖 准备阅读[{turn_count} - {read_count}]篇"

                        self.logger.war(msg)

                        self.logger.info(
                            f"【第 [{turn_count} - {read_count}] 篇文章信息】\n{self.parse_wx_article(article_url)}")

                        article_map[f"{turn_count} - {read_count}"] = article_url

                        is_pushed = self.__check_article_url(article_url, turn_count, read_count)

                        if is_pushed:
                            a = article_map.get(f"{turn_count} - {read_count - 1}")
                            if a:
                                self.new_detected_data.add(a)

                        # 随机睡眠，并获取睡眠时间（秒数）
                        sleep_time = self.sleep_fun(is_pushed)

                        # 更新增加金币的睡眠时间
                        APIS.ADD_GOLD = APIS.ADD_GOLD.replace("{sleep_time}", str(sleep_time))

                        # 请求增加金币
                        gold_info = self.__request_add_gold()

                        if "未能获取到用户信息" in gold_info.msg:
                            self.logger.war(gold_info.msg)
                            return self.__already_to_run()

                        self.logger.info(f"🟢 {gold_info.get_read_result()}")

                        # 更新当前阅读数
                        self.current_read_count += 1
                        read_count += 1
                    else:
                        self.new_detected_data.add(article_map.get(f"{turn_count} - {read_count - 1}", ""))
                        raise FailedPassDetect(f"🟢⭕️ {article_url_model.msg}")
                else:
                    raise Exception(f"🔴 获取阅读文章链接失败, 原始响应数据: {article_url_model}")

        else:
            raise RegExpError(self.JUMP_READ_PAGE_COMPILE)

    def __check_article_url(self, article_url, turn_count, read_count) -> bool:
        """
        检查文章链接是否合法，否则直接推送
        :param article_url: 文章链接
        :param turn_count: 当前轮数
        :param read_count: 当前轮数的篇数
        :return: 返回是否推送成功
        """
        is_pushed = False
        # 提取链接biz
        biz_match = self.NORMAL_LINK_BIZ_COMPILE.search(article_url)
        is_need_push = False
        # 判断下一篇阅读计数是否达到指定检测数
        if self.current_read_count + 1 in self.custom_detected_count:
            self.logger.war(f"🟡 达到自定义计数数量，走推送通道!")
            is_need_push = True
            # 判断是否是检测文章
        elif article_url in self.detected_data or article_url in self.new_detected_data:
            self.logger.war(f"🟡 出现被标记的文章链接, 走推送通道!")
            is_need_push = True
        # 判断是否是检测文章
        elif "chksm" in article_url or not self.ARTICLE_LINK_VALID_COMPILE.match(article_url):
            self.logger.war(f"🟡 出现包含检测特征的文章链接，走推送通道!")
            is_need_push = True
        # 判断是否是检测文章
        elif biz_match and biz_match.group(1) in self.detected_biz_data:
            self.logger.war(f"🟡 出现已被标记的biz文章，走推送通道!")
            is_need_push = True
        if is_need_push:
            push_types = self.push_types
            push_result = []
            if 1 in push_types:
                push_result.append(self.wx_pusher(article_url, detecting_count=read_count))
            if 2 in push_types:
                push_result.append(self.wx_business_pusher(
                    article_url,
                    detecting_count=read_count,
                    situation=(
                        self.logger.name, turn_count, read_count - 1, self.current_read_count, read_count),
                    tips=f"请尽快在指定时间{self.push_delay[0]}秒内阅读完此篇文章"
                ))

            # 只要其中任意一个推送成功，则赋值为True
            is_pushed = any(push_result)
            # 如果推送失败
            if not is_pushed:
                # 直接抛出异常
                raise FailedPushTooManyTimes()
        return is_need_push

    def __request_add_gold(self) -> Gold | dict:
        """请求增加金币"""
        return self._request_for_json(
            "GET",
            APIS.ADD_GOLD,
            "增加金币",
            client=self.read_client,
            model=Gold
        )

    def __request_article_url(self) -> ArticleUrl | dict:
        """请求获取文章链接"""
        return self._request_for_json(
            "GET",
            APIS.ARTICLE_URL,
            "获取文章链接 read_client",
            client=self.read_client,
            model=ArticleUrl
        )

    def __request_jump_read_page(self, jump_read_url):
        """请求跳转阅读链接，获取加载页面源代码"""
        return self.request_for_page(
            jump_read_url,
            "获取跳转阅读链接",
            client=self.read_client
        )

    def parse_jump_read_url(self, jump_read_url) -> str:
        """解析阅读跳转链接，并返回 uk"""
        url = URL(jump_read_url)
        self.uk = url.params.get("uk")
        return self.uk

    def get_jump_read_url(self, retry_count: int = 3) -> str | None:
        """获取阅读跳转链接"""
        # 获取阅读跳转链接
        jump_read_model = self.__request_jump_read()
        # 判断是否获取成功
        if jump_read_model:
            # 获取成功则打印跳转链接
            if isinstance(jump_read_model, WTMPDomain):
                if self.run_read_task:
                    self.logger.info(jump_read_model)
                jump_read_url = jump_read_model.data.domain
            else:
                jump_read_url = jump_read_model.get("data", {}).get("domain")
            return jump_read_url
        else:
            if retry_count > 0:
                self.logger.war(f"获取跳转阅读链接失败, 3秒后重试，剩余重试次数{retry_count - 1}")
                time.sleep(3)
                return self.get_jump_read_url(retry_count - 1)
            else:
                raise Exception("获取跳转阅读链接失败")

    def __request_jump_read(self) -> WTMPDomain | dict:
        """请求和获取阅读跳转链接"""
        return self._request_for_json(
            "POST",
            APIS.JUMP_READ,
            "获取跳转阅读链接",
            client=self.base_client,
            update_headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_client.base_url.__str__()
            },
            model=WTMPDomain,
            data={
                "unionid": self.union_id
            }

        )

    def __request_gold_info(self) -> Gold | dict:
        """请求获取金币情况（阅读收入）"""
        return self._request_for_json(
            "GET",
            f"{APIS.GOLD_INFO}{timestamp(13)}",
            "获取金币数据",
            client=self.base_client,
            update_headers={
                "Referer": self.homepage_url.__str__()
            },
            model=Gold
        )

    def _request_for_json(self, method: str, url: str | URL, prefix: str, *args, client: httpx.Client = None,
                          model: Type[BaseModel] = None,
                          **kwargs):
        update_headers = kwargs.pop("update_headers", {})
        return self.request_for_json(
            method,
            url,
            prefix,
            *args,
            client=client,
            model=model,
            update_headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                **update_headers
            },
            **kwargs
        )

    def get_entry_url(self) -> str:
        return EntryUrl.get_xyy_entry_url()

    @property
    def homepage_url(self):
        return self._cache.get(f"homepage_url_{self.ident}")

    @homepage_url.setter
    def homepage_url(self, value):
        self._cache[f"homepage_url_{self.ident}"] = value

    @property
    def domain(self):
        return self._cache.get(f"domain_{self.ident}")

    @domain.setter
    def domain(self, value):
        self._cache[f"domain_{self.ident}"] = value

    @property
    def request_id(self):
        return self._cache.get(f"request_id_{self.ident}")

    @request_id.setter
    def request_id(self, value):
        self._cache[f"request_id_{self.ident}"] = value

    @property
    def union_id(self):
        return self._cache.get(f"union_id_{self.ident}")

    @union_id.setter
    def union_id(self, value):
        self._cache[f"union_id_{self.ident}"] = value

    @property
    def withdraw_type(self):
        """
        提现方式 默认微信提现
        :return:
        """
        ret = self.account_config.withdraw_type
        if ret is None:
            ret = self.config_data.withdraw_type
        return ret if ret is not None else "wx"

    @property
    def uk(self):
        return self._cache.get(f"uk_{self.ident}")

    @uk.setter
    def uk(self, value):
        self._cache[f"uk_{self.ident}"] = value


if __name__ == '__main__':
    XYYV2()
