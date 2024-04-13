# -*- coding: utf-8 -*-
# yryd.py created by MoMingLog on 3/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-03
【功能描述】
"""
import random
import re
import time
from urllib.parse import unquote_plus

from httpx import URL

from config import load_yryd_config
from exception.common import Exit, StopReadingNotExit, RegExpError, ExitWithCodeChange, PauseReadingTurnNext, \
    FailedPushTooManyTimes, CookieExpired
from schema.yryd import YRYDConfig, RspReadUrl, RspDoRead
from script.common.base import WxReadTaskBase, RetTypes
from utils import EntryUrl


class APIS:
    # API: 阅读（扫码后跳转的链接） - 程序自动提取
    GET_READ_URL = "/read_task/gru"
    # API: do_read（目前默认是这个） - 程序自动提取
    DO_READ = "/read_task/do_read"
    # API: 提款页面
    WITHDRAWAL = "/withdrawal"
    # API: 提款请求
    DO_WITHDRAW = "/withdrawal/submit_withdraw"


class YRYDV2(WxReadTaskBase):
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "2.0.1"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-04-03"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-08"
    # 当前任务名称
    CURRENT_TASK_NAME = "鱼儿阅读"

    # 提取主页源代码中的阅读情况（目前仅提取ID、余额、已读篇数、阅读规则、扫码后跳转的API、获取成功阅读链接后的type参数）
    HOMEPAGE_COMPILE = re.compile(
        r"<p.*?>【ID:(.*?)】余额.*?(\d+\.*\d*)元.*?p>今日已读(\d+)篇[,，].*?</p>.*?p.*?>(每小时.*?)</p>.*?show_qrcode.*?is_make_qrcode.*?get\(['\"](.*?)['\"].*?var.*?['\"]&type=(\d+)['\"]",
        re.S)
    # 判断是否是链接格式
    LINK_MATCH_COMPILE = re.compile(r"^https?://[^\s/$.?#].\S*$")
    # 提取阅读跳转主页中的数据（do_read API、do_read部分参数、部分参数随机数特征）
    LOADING_PAGE_COMPILE = re.compile(r"script.*?url\s*=\s*['\"](.*?)['\"].*?加载中.*?get\(.*?['\"](.*?)['\"](.*?)\)",
                                      re.S)
    # 提取提款界面的原有支付宝账号
    WITHDRAWAL_PAGE_COMPILE = re.compile(r"id=['\"](?:u_ali_real_name|u_ali_account).*?value=['\"](.*?)['\"]", re.S)
    # 提款界面的当前余额
    CURRENT_GOLD_COMPILE = re.compile(r"当前余额.*?>(\d+\.?\d*)<", re.S)

    def __init__(self, config_data: YRYDConfig = load_yryd_config(), run_read_task: bool = True):
        self.run_read_task = run_read_task
        self.homepage_api = None
        self.main_thread_ident = self.ident
        self.detected_biz_data = config_data.biz_data or []
        super().__init__(config_data, logger_name="🐟️阅读", load_detected=True)

    def get_entry_url(self):
        return EntryUrl.get_yryd_entry_url()

    def init_fields(self, retry_count=3):
        # 在主线程中先判断入口链接是否获取成功
        if self.entry_url is None:
            raise Exit("入口链接为空!")
        # 初始化 main_client
        self.parse_base_url(self.entry_url, self.main_client)
        # 对入口链接发起请求，获取重定向链接
        redirect_url = self.request_for_redirect(
            self.entry_url,
            "请求入口链接 main_client",
            client=self.main_client
        )
        self.logger.debug(f"第一次重定向链接: {redirect_url}")
        # 对重定向后的链接发起请求，获取二次重定向链接
        redirect_url = self.request_for_redirect(
            redirect_url,
            "二次重定向 main_client",
            client=self.main_client
        )
        self.logger.debug(f"二次重定向链接为：{redirect_url}")
        # 开始提取二次重定向链接中的参数值
        # 先转成 URL 类型
        url_params = URL(redirect_url).params
        # 提取链接中的重定向链接
        redirect_url = URL(url_params.get("redirect_uri", ""))
        # 储存一下注意API
        self.homepage_api = redirect_url.params.get("redirect")
        # 再次更新 main_client
        self.parse_base_url(redirect_url, self.main_client)

    def run(self, name, *args, **kwargs):
        self.base_client.base_url = self.main_client.base_url
        self.read_client.base_url = self.main_client.base_url
        # 判断 cookie中是否有 PHPSESSID
        if "PHPSESSID" in self.origin_cookie:
            # 再为当前用户更新对应配置的cookie
            self.read_client.cookies = self.cookie_dict
            self.base_client.cookies = self.cookie_dict
            self.entry_func_for_cookie()
        else:
            self.read_client.headers.update({
                "Cookie": self.origin_cookie
            })
            self.base_client.headers.update({
                "Cookie": self.origin_cookie
            })
            self.entry_func_for_id()

    def entry_func_for_id(self):
        """
        使用ID进行阅读的入口函数
        :return:
        """
        # 拼接获取阅读链接的URL
        api_path = f"{APIS.GET_READ_URL}?iu=iuMjA2ODc0OQ2"
        # read_url_model = self.__request_read_url(api_path)
        # self.logger.info(read_url_model)
        self.logger.war("🟡 当前正在通过ID进行阅读操作（ID无法获取用户信息和提现, 只能进行阅读操作）...")
        self.logger.war("🟡 由于无法获取用户信息，故每次运行默认为第1轮第1篇!")
        time.sleep(5)
        self.current_read_count = 0
        self.__start_read(turn_count=1, read_url_api_path=api_path)

    def entry_func_for_cookie(self):
        """
        使用Cookie进行阅读的入口函数
        :return:
        """
        # 尝试获取主页源代码
        homepage_html = self.request_for_page(
            self.homepage_api,
            "请求主页源代码 read_client",
            client=self.read_client
        )
        if not homepage_html:
            raise CookieExpired()

        if r := self.HOMEPAGE_COMPILE.search(homepage_html):
            self.current_read_count = int(r.group(3))
            self.logger.info("\n".join([
                "【用户数据】",
                f"> 用户 ID: {r.group(1)}",
                f"> 当前余额: {r.group(2)}",
                f"> 今日已读: {self.current_read_count}",
                f"> 阅读规则: {r.group(4)}"
            ]))

            if not self.run_read_task:
                self.__request_withdraw()
                return

            # 覆盖原API
            APIS.GET_READ_URL = r.group(5)
            _type = r.group(6)
            turn_count = self.current_read_count // 30 + 1
            self.logger.war(f"🟡 当前是第[{turn_count}]轮阅读")
            self.__start_read(_type, turn_count)
            self.__request_withdraw()
        else:
            raise RegExpError(self.HOMEPAGE_COMPILE)

    def __start_read(self, _type=7, turn_count=None, retry: int = 3, read_url_api_path: str = None):
        self.logger.war("🟡 正在获取阅读链接...")
        read_url_model = self.__request_read_url(read_url_api_path)
        # 获取阅读加载页链接
        read_url: URL = self.__get_read_url(read_url_model)

        # 构建完整阅读链接
        full_read_url = f"{read_url}&type={_type}"
        # 更新read_client请求头
        self.read_client.headers.update({
            "Referer": full_read_url
        })

        read_count = self.current_read_count % 30 + 1
        jkey = None
        use_user_cookie = False
        article_map = {}
        while True:
            # 请求加载页源代码
            loading_page = self.__request_loading_page(full_read_url, use_user_cookie)
            # 正则匹配提取相关需要参数
            if r2 := self.LOADING_PAGE_COMPILE.search(loading_page):
                # 以防万一判断下 r 参数的值是否为 随机数
                if "Math.random" in r2.group(3):
                    # 覆盖原API（附带参数）
                    APIS.DO_READ = f"{r2.group(1)}?iu={self.iu}&type={_type}{r2.group(2)}{random.random()}"
                    # 判断jkey是否已填充
                    if jkey is not None:
                        APIS.DO_READ = f"{APIS.DO_READ}&jkey={jkey}"
                    # 发起 完成阅读 请求
                    do_read_model = self.__request_do_read()
                    # 判断是否转换模型成功，并且article_url存在
                    if isinstance(do_read_model, RspDoRead) and (article_url := do_read_model.url):
                        unquote_url = unquote_plus(article_url)
                        # 判断当前阅读链接是否已经失效
                        if "链接失效" in unquote_url:
                            # 判断当前递归重试次数是否大于0
                            if retry > 0:
                                # 重试次数自减1
                                retry -= 1
                                self.logger.war(f"🟡 阅读链接已失效! 尝试重新获取, 剩余尝试次数: {retry}")
                                # 递归调用
                                # 先随机睡眠1-3秒
                                time.sleep(random.randint(1, 3))
                                self.__start_read(_type, retry)
                            else:
                                # 重试次数已归零则抛出异常
                                raise PauseReadingTurnNext("重新获取阅读链接次数已用尽!")
                        elif "当前已经被限制" in unquote_url:
                            last_article_url = article_map.get(f"{turn_count} - {read_count - 1}", "")
                            if last_article_url:
                                self.new_detected_data.add(last_article_url)
                            self.logger.error("🔴 当前已经被限制，请明天再来")
                            return
                        elif "/finish?" in unquote_url:
                            self.logger.war(f"🟡 本轮阅读任务可能已经完成, 响应链接: {unquote_url}")
                            return
                        # 更新下一次 do_read 链接的 jkey 参数
                        jkey = do_read_model.jkey
                        # 顺便将请求加载页源代码的使用用户cookie打开
                        use_user_cookie = True
                        # 打印阅读情况
                        if self.current_read_count != 0:
                            msg = f"🟡 准备阅读第[{turn_count} - {read_count}]篇, 已成功阅读[{self.current_read_count}]篇"
                        else:
                            msg = f"🟡 准备阅读[{turn_count} - {read_count}]篇"
                        self.logger.war(msg)

                        self.logger.info(
                            f"【第 [{turn_count} - {read_count}] 篇文章信息】\n{self.parse_wx_article(article_url)}")

                        article_map[f"{turn_count} - {read_count}"] = article_url

                        self.__check_article_url(article_url, turn_count, read_count)
                        # 无法判断是否阅读成功，股这里直接自增
                        read_count += 1
                        self.current_read_count += 1
                    else:
                        # 如果转换失败，那么此时说明返回的数据是字典类型
                        # 这里目前暂不打算适配
                        # self.logger.war("")
                        pass
                else:
                    # 接口参数发生变化，抛出异常
                    raise ExitWithCodeChange(APIS.DO_READ)
            else:
                # 正则匹配失败，需要更新了，此时也有可能是源代码更新
                raise RegExpError(self.LOADING_PAGE_COMPILE)

    def __check_article_url(self, article_url, turn_count, read_count):
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
        self.sleep_fun(is_pushed)
        return is_need_push

    def __request_withdraw(self):
        # 判断是否要进行提现操作
        if not self.is_withdraw:
            self.logger.war(f"🟡 提现开关已关闭，已停止提现任务")
            return
        # 先请求提现页面
        withdrawal_page = self.__request_withdrawal_page()

        if money_match := self.CURRENT_GOLD_COMPILE.search(withdrawal_page):
            money = money_match.group(1)
        else:
            raise RegExpError(self.CURRENT_GOLD_COMPILE)

        if float(money) / 100 < self.withdraw:
            self.logger.war(f"🟡 账户余额 [{float(money) / 100}] 不足 [{self.withdraw}]，无法提现")
            return

        if self.withdraw_type == "wx":
            withdraw_result = self.__request_do_withdrawal(money)
        else:
            if self.aliName and self.aliAccount:
                u_ali_account = self.aliAccount
                u_ali_real_name = self.aliName
            else:
                if r := self.WITHDRAWAL_PAGE_COMPILE.findall(withdrawal_page):
                    if len(r) == 2:
                        u_ali_account = r[0]
                        u_ali_real_name = r[1]
                    else:
                        raise RegExpError(self.WITHDRAWAL_PAGE_COMPILE)
                else:
                    raise RegExpError(self.WITHDRAWAL_PAGE_COMPILE)

            withdraw_result = self.__request_do_withdrawal(money, u_ali_account, u_ali_real_name)

        if isinstance(withdraw_result, list):
            withdraw_result: dict = withdraw_result[0]
        msg = withdraw_result.get("msg", "")
        if "提现成功" in msg:
            self.logger.info(f"🟢 {msg}")
        else:
            self.logger.error(f"🔴 {msg}")

    def __request_do_withdrawal(self, money: float, u_ali_account=None, u_ali_real_name=None):

        if u_ali_account is None and u_ali_real_name is None:
            data = {
                "channel": "wechat",
                "money": money
            }
        else:
            data = {
                "channel": "alipay",
                "money": money,
                "u_ali_account": u_ali_account,
                "u_ali_real_name": u_ali_real_name
            }

        return self.request_for_json(
            "POST",
            APIS.DO_WITHDRAW,
            "请求提现请求 base_client",
            client=self.base_client,
            update_headers={
                "Accept": "*/*",
                "Origin": self.base_client.base_url.__str__(),
                "Referer": f"{self.base_client.base_url}{APIS.WITHDRAWAL}",
                "X-Requested-With": "XMLHttpRequest"
            },
            data=data,
            # 忽略json解析错误
            ignore_json_error=True,
            ret_types=RetTypes.TEXT
        )

    def __request_withdrawal_page(self):
        return self.request_for_page(
            APIS.WITHDRAWAL,
            "请求提现页 base_client",
            client=self.base_client,
            update_headers={
                "X-Requested-With": "com.tencent.mm"
            }
        )

    def __request_do_read(self) -> RspDoRead | dict:
        return self.request_for_json(
            "GET",
            APIS.DO_READ,
            "完成阅读请求 read_client",
            client=self.read_client,
            model=RspDoRead,
            update_headers={
                "Accept": "*/*"
            }
        )

    def __request_loading_page(self, read_url, use_user_cookie=False):
        """使用不包含用户cookie的客户端请求加载页源代码"""
        return self.request_for_page(
            read_url,
            "请求阅读加载页 read_client",
            client=self.main_client if not use_user_cookie else self.read_client
        )

    def __get_read_url(self, read_url_model) -> URL:
        """
        获取阅读链接
        :return:
        """
        read_url = None

        if isinstance(read_url_model, RspReadUrl) and (read_url := read_url_model.jump):
            self.logger.info(f"🟢 获取成功 [10分钟内勿分享] -> {read_url}")
            read_url = URL(read_url)
        else:
            # 如果模型匹配失败，则尝试自动提取阅读链接
            for value in read_url_model.values():
                if self.LINK_MATCH_COMPILE.match(value) and "iu" in value:
                    self.logger.info(f"🟢 获取成功 [10分钟内勿分享] -> {value}")
                    read_url = URL(value)
                    break
        if read_url:
            # 从read_url中提取出iu值并缓存
            self.iu = read_url.params.get("iu")
            # 顺手把 read_client 的 更新下
            self.parse_base_url(read_url, client=self.read_client)
            return read_url
        else:
            raise StopReadingNotExit("阅读链接获取失败!")

    def __request_read_url(self, api_path: str = None) -> RspReadUrl | dict:

        return self.request_for_json(
            "GET",
            APIS.GET_READ_URL if api_path is None else api_path,
            "请求阅读链接 read_client",
            client=self.read_client,
            model=RspReadUrl,
            update_headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*"
            }
        )

    @property
    def withdraw_type(self):
        ret = self.account_config.withdraw_type
        if ret is None:
            ret = self.config_data.withdraw_type
        return ret if ret is not None else "wx"

    @property
    def iu(self):
        return self._cache.get(f"iu_{self.ident}")

    @iu.setter
    def iu(self, value):
        self._cache[f"iu_{self.ident}"] = value


if __name__ == '__main__':
    YRYDV2()
