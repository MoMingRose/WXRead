# -*- coding: utf-8 -*-
# mmkk_v2.py created by MoMingLog on 1/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-01
【功能描述】
"""
import random
import re
import time
from urllib.parse import quote_plus

from httpx import URL

from config import load_mmkk_config
from exception.common import RegExpError, ExitWithCodeChange, PauseReadingAndCheckWait, StopReadingNotExit, \
    FailedPushTooManyTimes
from exception.klyd import FailedPassDetect
from exception.mmkk import StopRun, StopRunWithShowMsg, FailedFetchUK
from schema.mmkk import MMKKConfig, UserRsp, WorkInfoRsp, WTMPDomainRsp, MKWenZhangRsp, AddGoldsRsp
from script.common.base import WxReadTaskBase
from utils import EntryUrl, md5, timestamp


class APIS:
    # 通用前缀路径
    COMMON = "/haobaobao"

    # API: 用户信息（程序自动提取）
    USER = f"{COMMON}/user"
    # API: 今日阅读统计（程序自动提取）
    WORKINFO = f"{COMMON}/workinfo"
    # API: 二维码相关信息（程序自动提取）
    WTMPDOMAIN = f"{COMMON}/wtmpdomain2"
    # API: 获取阅读文章
    GET_ARTICLE_URL = f"{COMMON}/mkwenzhangs"
    # API: 阅读成功后增加金币
    ADD_GOLD = f"{COMMON}/addgolds2"
    # API: 提现页面
    WITHDRAW = f"{COMMON}/withdraw"
    # API: 将金币兑换为人民币
    GETGOLD = f"{COMMON}/getgold"
    # API: 将人民币进行提现
    GETWITHDRAW = f"{COMMON}/getwithdraw"


class MMKKV2(WxReadTaskBase):
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "2.0.1"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-03-28"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-08"
    # 当前任务名称
    CURRENT_TASK_NAME = "猫猫看看"

    # 主页源代码正则，主要提取内容：用户数据API、文章篇数和金币API、阅读二维码链接API
    HOME_CONTENT_COMPILE = re.compile(
        r"(?:用户数据|文章篇数和金币|文章阅读二维码).*?function\s(?:sign_info|getGold|read_jump_read).*?ajax.*?url.*?['\"](.*?)['\"],",
        re.S)

    # 主页源代码正则2，用于提取：提现页面API
    HOME_CONTENT_COMPILE_2 = re.compile(r"提现页面.*?href\s*=\s*.*?['\"](.*?)['\"]", re.S)

    # 阅读加载页: 提取增加金币API
    LOADING_PAGE_ADD_GOLD_COMPILE = re.compile(
        r"(?:金币接口)?function\sgetGold.*?ajax.*?url:.*?['\"](.*?)['\"].*?['\"](.*?)['\"].*?['\"](.*?)['\"].*?,", re.S)
    # 阅读加载页：提取获取文章API
    LOADING_PAGE_GET_ARTILE_COMPILE = re.compile(
        r"(?:文章接口)?function\sread_jump_read.*?ajax.*?url:.*?['\"](.*?)['\"].*?['\"](.*?)['\"].*?,", re.S)

    # 获取 request_id
    WITHDRAW_REQ_ID_COMPILE = re.compile(r"request_id\s*=\s*['\"](.*?)['\"]")

    # 检测有效阅读链接
    ARTICLE_LINK_VALID_COMPILE = re.compile(
        r"^https?://mp.weixin.qq.com/s\?__biz=[^&]*&mid=[^&]*&idx=\d*&(?!.*?chksm).*?&scene=\d*#wechat_redirect$")
    # 提取阅读文章链接的__biz值
    ARTICLE_LINK_BIZ_COMPILE = re.compile(r"__biz=(.*?)&")

    def __init__(self, config_data: MMKKConfig = load_mmkk_config(), run_read_task: bool = True):
        self.run_read_task = run_read_task
        self.detected_biz_data = config_data.biz_data or []
        super().__init__(config_data, logger_name="😸阅读")

    def get_entry_url(self):
        return EntryUrl.get_mmkk_entry_url()

    def init_fields(self, retry_count=3):
        # 获取新的入口链接
        self.entry_url: URL = self.request_for_redirect(
            self.entry_url,
            "第一次重定向 main_client",
            client=self.main_client
        )
        self.logger.debug(f"第一次重定向链接: {self.entry_url}")
        redirect_url = self.entry_url.__str__()
        quote_url = quote_plus(redirect_url)
        self.logger.info(quote_url)
        if "showmsg" in redirect_url:
            self.logger.war(f"🟡 检测到公告信息, 正在提取...")
            html = self.request_for_page(
                redirect_url,
                "获取公告信息",
                client=self.main_client
            )
            raise StopRunWithShowMsg(self.__parse_show_msg(html))

    def run(self, name, *args, **kwargs):
        # 设置cookie
        self.base_client.cookies = self.cookie_dict
        # 开始第二次重定向，获取主页链接
        self.entry_url: URL = self.request_for_redirect(
            self.entry_url,
            "第二次重定向 base_client",
            client=self.base_client
        )
        # 请求首页源代码
        homepage_html = self.request_for_page(
            self.entry_url,
            "获取主页源代码 base_client",
            client=self.base_client
        )
        if "存在违规操作" in homepage_html:
            raise StopRun("账号已被封")

        # 更新 base_client 的 base_url
        self.parse_base_url(self.entry_url, client=self.base_client)

        if r := self.HOME_CONTENT_COMPILE.findall(homepage_html):
            if len(r) != 3:
                raise RegExpError(self.HOME_CONTENT_COMPILE)
            # 开始动态改变对应的API
            APIS.USER = r[0]
            APIS.WORKINFO = r[1]
            APIS.WTMPDOMAIN = r[2]
            self.logger.info("🟢 程序自动提取API成功!")
        else:
            raise RegExpError(self.HOME_CONTENT_COMPILE)

        # 随机睡眠2-4秒
        time.sleep(random.randint(2, 4))
        # 获取用户信息, 并打印
        self.logger.info(self.__request_user())
        # 随机睡眠2-4秒
        time.sleep(random.randint(1, 2))
        # 获取文章篇数和金币
        workinfo_model = self.__request_workinfo()
        if workinfo_model:
            self.logger.info(workinfo_model)
            self.current_read_count = workinfo_model.data.dayreads
            try:
                if not self.run_read_task:
                    return
                self.start_read()
            finally:
                # 提现
                self.__request_withdraw()
        else:
            self.logger.error(f"获取文章篇数和金币失败, 原数据为: {workinfo_model}")
            return

    def start_read(self):
        # 随机睡眠2-4秒
        time.sleep(random.randint(2, 4))
        # 获取阅读二维码链接
        read_load_model = self.__request_read_load_url()
        if read_load_model:
            self.logger.info(read_load_model)
            read_load_url = read_load_model.data.domain
            try:
                self.uk = URL(read_load_url).params["uk"]
            except:
                raise FailedFetchUK()
            time.sleep(random.randint(1, 2))
            # 获取正在加载页面源代码
            loading_page_html = self.__request_loading_page(read_load_url)
            # 先检查此页面和对应接口数据是否变动
            self.__parse_loading_page(loading_page_html)
            # 设置 read_client 的基本链接
            self.parse_base_url(read_load_url, client=self.read_client)
            # 开始阅读
            self.__start_read()
        else:
            self.logger.error(f"获取阅读二维码链接失败, 原数据为: {read_load_model}")
            return

    def __request_withdraw(self):
        """
        发起提现请求
        :return:
        """
        # 判断是否要进行提现操作
        if not self.is_withdraw:
            self.logger.war(f"🟡 提现开关已关闭，已停止提现任务")
            return
        # 获取提现页面
        withdraw_page = self.__request_withdraw_page()
        if r := self.WITHDRAW_REQ_ID_COMPILE.search(withdraw_page):
            self.req_id = r.group(1)
        else:
            raise RegExpError(self.WITHDRAW_REQ_ID_COMPILE)
        workInfo: WorkInfoRsp = self.__request_workinfo()
        gold = int(int(workInfo.data.remain_gold) / 1000) * 1000
        money = workInfo.data.remain
        self.logger.info(f"【账户余额统计】\n> 待提现金额：{money}元\n> 待兑换金币: {gold}金币")
        # 判断是否有金币，或者期待提现金额小于账户余额
        if gold != 0:
            # 表示可以提现
            if new_money := self.__exchange_gold(gold, money):
                money = new_money

        if money >= self.withdraw:
            self.__request_withdraw_money()
        else:
            self.logger.war(f"账户余额不足 {self.withdraw} 元, 提现停止!")

    def __request_withdraw_money(self):
        flag = True if self.aliName and self.aliAccount else False

        try:
            res_json: dict = self.request_for_json(
                "POST",
                APIS.GETWITHDRAW,
                "请求提现 base_client",
                data={
                    "signid": self.req_id,
                    "ua": "2" if flag else "0",
                    "ptype": "1" if flag else "0",
                    "paccount": self.aliAccount,
                    "pname": self.aliName
                },
                client=self.base_client
            )
            self.logger.info(f"提现结果：{res_json['msg']}")
        except Exception as e:
            self.logger.exception(f"提现失败，原因：{e}")

    def __exchange_gold(self, gold, money):
        """
        将金币兑换成现金
        :param gold: 当前金币余额
        :param money: 当前现金余额
        :return:
        """
        try:
            exchange_result = self.__request_exchange_gold(gold)
            if exchange_result.get("errcode") == 0:
                withdrawBalanceNum = money + float(exchange_result["data"]["money"])
                self.logger.info(f"✅ 金币兑换为现金成功，开始提现，预计到账 {withdrawBalanceNum} 元")
                return withdrawBalanceNum
            else:
                self.logger.info(f"❌ 金币兑换为现金失败，原因：{exchange_result['msg']}")
        except Exception as e:
            self.logger.exception(f"金币兑换现金失败，原因：{e}")

    def __request_exchange_gold(self, gold) -> dict:
        return self.request_for_json(
            "POST",
            APIS.GETGOLD,
            "请求金币兑换 base_client",
            data={
                "request_id": self.req_id,
                "gold": str(gold)
            },
            client=self.base_client
        )

    def __request_withdraw_page(self):
        return self.request_for_page(
            APIS.WITHDRAW,
            "请求提现页面 base_client",
            client=self.base_client
        )

    def __start_read(self):
        # 计算当前阅读轮数
        turn_count = self.current_read_count // 30 + 1
        # 计算当前轮数的阅读篇数
        read_count = self.current_read_count % 30 + 1
        while_count = 0
        # 暂存文章链接数据
        article_map = {}
        while True:
            # 先获取文章链接
            article_url_model = self.__request_get_article_url()
            # 判断文章链接是否获取成功
            if article_url_model:
                if "分钟后" in article_url_model.msg:
                    self.logger.info(f"🟢📖 本轮阅读已完成 {article_url_model.msg}")
                    raise PauseReadingAndCheckWait(article_url_model.msg)
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
                    if isinstance(article_url_model, MKWenZhangRsp):
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

                    is_pushed = self.__check_article_url(while_count, article_url, turn_count, read_count)

                    if is_pushed:
                        a = article_map.get(f"{turn_count} - {read_count - 1}")
                        if a:
                            self.new_detected_data.add(a)

                    # 随机睡眠，并获取睡眠时间（秒数）
                    sleep_time = self.sleep_fun(is_pushed)
                    # 请求增加金币
                    gold_info = self.__request_add_gold(sleep_time)

                    if "未能获取到用户信息" in gold_info.msg:
                        self.logger.war(gold_info.msg)
                        return self.start_read()

                    if gold_info.data:
                        self.logger.info(f"🟢 {gold_info}")
                    else:
                        self.logger.error(f"🔴 增加金币失败! 原始数据: {gold_info}")

                    # 更新当前阅读数
                    self.current_read_count += 1
                    read_count += 1
                    while_count += 1
                else:
                    self.new_detected_data.add(article_map.get(f"{turn_count} - {read_count - 1}", ""))
                    raise FailedPassDetect(f"🟢⭕️ {article_url_model.msg}")
            else:
                raise Exception(f"🔴 获取阅读文章链接失败, 原始响应数据: {article_url_model}")

    def __check_article_url(self, while_count, article_url, turn_count, read_count) -> bool:
        """
        检查文章链接是否合法，否则直接推送
        :param while_count: 当前循环的趟数
        :param article_url: 文章链接
        :param turn_count: 当前轮数
        :param read_count: 当前轮数的篇数
        :return: 返回是否推送成功
        """
        is_pushed = False
        # 提取链接biz
        biz_match = self.NORMAL_LINK_BIZ_COMPILE.search(article_url)
        is_need_push = False

        if while_count == 0 and self.first_while_to_push:
            self.logger.war("🟡 固定第一次循环，走推送通道")
            is_need_push = True
        # 判断下一篇阅读计数是否达到指定检测数
        elif self.current_read_count + 1 in self.custom_detected_count:
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

    def __request_add_gold(self, sleep_time: int) -> AddGoldsRsp | dict:
        return self.request_for_json(
            "GET",
            APIS.ADD_GOLD.replace("{time}", str(sleep_time)),
            "增加金币 read_client",
            client=self.read_client,
            model=AddGoldsRsp
        )

    def __request_get_article_url(self) -> MKWenZhangRsp | dict:
        return self.request_for_json(
            "GET",
            APIS.GET_ARTICLE_URL.replace("{time}", str(timestamp(13))),
            "获取文章链接 read_client",
            client=self.read_client,
            model=MKWenZhangRsp
        )

    def __parse_loading_page(self, loading_page_html: str):
        if r := self.LOADING_PAGE_ADD_GOLD_COMPILE.search(loading_page_html):
            api = f"{r.group(1)}{{time}}{r.group(2)}{{psign}}{r.group(3)}{{uk}}"
            if "9b604ee5c9fe3618441b7868ce9bb1f1" != md5(api):
                raise ExitWithCodeChange("增加金币接口变化")
            APIS.ADD_GOLD = api.replace("{uk}", self.uk) \
                .replace("{psign}", str(int(random.random() * 1000) + 1))
        else:
            raise RegExpError(self.LOADING_PAGE_ADD_GOLD_COMPILE)

        if r := self.LOADING_PAGE_GET_ARTILE_COMPILE.search(loading_page_html):
            api = f"{r.group(1)}{{time}}{r.group(2)}{{uk}}"
            if "2fe4402f3b8bfce53d0465b62e0fbac5" != md5(api):
                raise ExitWithCodeChange("获取文章接口变化")
            APIS.GET_ARTICLE_URL = api.replace("{uk}", self.uk)
        else:
            raise RegExpError(self.LOADING_PAGE_GET_ARTILE_COMPILE)

    def __request_loading_page(self, read_load_url: str):
        return self.request_for_page(
            read_load_url,
            "获取加载页面 read_client",
            client=self.read_client
        )

    def __request_read_load_url(self) -> WTMPDomainRsp | dict:
        return self.request_for_json(
            "POST",
            APIS.WTMPDOMAIN,
            "获取用户数据 base_client",
            client=self.base_client,
            model=WTMPDomainRsp,
            update_headers={
                "Origin": self.base_client.base_url.__str__()
            }
        )

    def __request_workinfo(self) -> WorkInfoRsp | dict:
        return self.request_for_json(
            "GET",
            APIS.WORKINFO,
            "获取用户数据 base_client",
            client=self.base_client,
            model=WorkInfoRsp,
        )

    def __request_user(self) -> UserRsp | dict:
        return self.request_for_json(
            "GET",
            APIS.USER,
            "获取用户数据 base_client",
            client=self.base_client,
            model=UserRsp,
            update_headers={
                "Referer": self.entry_url.__str__(),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01"
            }
        )

    def __parse_show_msg(self, show_msg_html: str):
        """
        解析公告信息
        :param show_msg_html:
        :return:
        """
        body_html = re.search(r"<body(.*?)</body>", show_msg_html, re.S).group(1)
        if r := re.search(r"container.*?p.*?>(.*?)</p\s*>", body_html, re.S):
            return re.sub(r"<br/?\s*>", "\n", r.group(1))
        # 如果上方的正则失效，则手动进行检查
        if "系统维护中" in body_html:
            return "系统维护中, 请耐心等待官方恢复!"
        return "检测到公告信息, 请自行前往查看, 脚本已自动停止运行!"

    @property
    def uk(self):
        return self._cache.get(f"uk_{self.ident}")

    @uk.setter
    def uk(self, value):
        self._cache[f"uk_{self.ident}"] = value

    @property
    def req_id(self):
        return self._cache.get(f"req_id_{self.ident}")

    @req_id.setter
    def req_id(self, value):
        self._cache[f"req_id_{self.ident}"] = value


if __name__ == '__main__':
    MMKKV2()
