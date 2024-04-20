# -*- coding: utf-8 -*-
# klyd_v2.py created by MoMingLog on 1/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-01
【功能描述】
"""
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from httpx import URL

from config import load_klyd_config
from exception.common import PauseReadingAndCheckWait, StopReadingNotExit, CookieExpired, RspAPIChanged, \
    ExitWithCodeChange, \
    FailedPushTooManyTimes, NoSuchArticle, RegExpError, PauseReadingTurnNext
from exception.klyd import FailedPassDetect, \
    WithdrawFailed
from schema.klyd import KLYDConfig, RspRecommend, RspReadUrl, RspDoRead, RspWithdrawal, RspWithdrawalUser
from script.common.base import WxReadTaskBase, RetTypes
from utils import EntryUrl, md5
from utils.logger_utils import NestedLogColors


class APIS:
    # 获取推荐信息
    RECOMMEND = "/tuijian"
    # 获取阅读链接（貌似现在会动态变化）故此API由程序自动获取
    # 懒得写那么多，就用最笨的方法了
    GET_READ_URL = "/new/gru"
    # 获取提现用户信息
    WITHDRAWAL = "/withdrawal"
    # 开始进行提现
    DO_WITHDRAWAL = "/withdrawal/doWithdraw"


class KLYDV2(WxReadTaskBase):
    CURRENT_SCRIPT_VERSION = "2.1.0"
    CURRENT_TASK_NAME = "可乐阅读"

    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-03-30"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-11"

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

    # 普通链接Biz提取
    NORMAL_LINK_BIZ_COMPILE = re.compile(r"__biz=(.*?)&", re.S)

    # 提取最新的获取阅读跳转链接
    FETCH_READ_URL_COMPILE = re.compile(r"make_qrcode\(\)\s*\{.*?\+\s*['\"](.*?)['\"]", re.S)

    def __init__(self, config_data: KLYDConfig = load_klyd_config(), run_read_task: bool = True):
        self.detected_biz_data = config_data.biz_data
        self.base_full_url = None
        self.run_read_task = run_read_task
        # self.exclusive_url = config_data.exclusive_url
        super().__init__(config_data=config_data, logger_name="🥤阅读", load_detected=True)

    def get_entry_url(self):
        return EntryUrl.get_klrd_entry_url()[0]

    def init_fields(self, retry_count=3):
        first_redirect_url: URL = self.__request_entry_for_redirect()
        self.base_url = f"{first_redirect_url.scheme}://{first_redirect_url.host}"
        self.base_full_url = first_redirect_url

    def run(self, name, *args, **kwargs):
        self.base_client.base_url = self.base_url
        self.logger.info(f"开始执行{NestedLogColors.red(name)}的任务")
        homepage_url: URL = self.__request_redirect_for_redirect()
        self.logger.debug(f"homepage_url：{homepage_url}")

        # 观看抓包数据流，貌似下方的请求可有可无，无所谓，判断一下也好
        homepage_html, status = self.request_for_page(
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
        # if '58c414e70fcc67cd5dcda712d18fc82c' != md5(homepage_html):
        #     raise ExitWithCodeChange("homepage_html")

        # 提取阅读跳转链接
        read_url = self.fetch_read_api(homepage_html)
        if read_url is not None:
            APIS.GET_READ_URL = read_url
        else:
            raise ExitWithCodeChange("fetch_read_api")
        self.is_need_withdraw = True
        try:
            # 获取推荐数据（里面包含当前阅读的信息）
            recommend_data = self.__request_recommend_json(homepage_url)
            self.__print_recommend_data(recommend_data)
            # 判断是否需要运行阅读任务
            if not self.run_read_task:
                return
            # 获取加载页面跳转链接
            self.load_page_url: URL = self.__request_for_read_url()
            self.logger.info(f"获取加载页链接成功: {self.load_page_url}")
            # 获取加载页面源代码
            read_load_page_html: str = self.__request_for_read_load_page(self.load_page_url)
            forstr, zs, r_js_path, r_js_version = self.__parse_read_load_page(read_load_page_html)
            self.logger.debug(f"r_js_path：{r_js_path}")
            self.logger.debug(f"r_js_version：{r_js_version}")
            if self.CURRENT_R_JS_VERSION != r_js_version:
                raise ExitWithCodeChange("r_js_version")
            # 设置read_client的base_url
            self.read_client.base_url = f"{self.load_page_url.scheme}://{self.load_page_url.host}"
            r_js_code = self.__request_r_js_code(r_js_path)
            if self.R_JS_CODE_MD5 != md5(r_js_code):
                raise ExitWithCodeChange("r_js_code")
            # 解析完成阅读的链接
            do_read_url_part_path = self.__parse_r_js_code(r_js_code, forstr, zs)
            do_read_url_full_path = self.__build_do_read_url_path(do_read_url_part_path)
            # 尝试通过检测并且开始阅读
            self.__pass_detect_and_read_v2(do_read_url_part_path, do_read_url_full_path)
            # 尝试进行提现操作
            self.__request_withdraw()
            self.is_need_withdraw = False
        except FailedPushTooManyTimes as e:
            self.logger.war(e)
            self.is_need_withdraw = False
            sys.exit(0)
        except (WithdrawFailed, NoSuchArticle) as e:
            self.logger.war(e)
            self.is_need_withdraw = False
        finally:
            if self.is_need_withdraw:
                self.__request_withdraw()

    def __request_withdraw(self):
        """
        发起提现请求
        :return:
        """
        # 判断是否要进行提现操作
        if not self.is_withdraw:
            self.logger.war(f"🟡💰 提现开关已关闭，已停止提现任务")
            return

        # 先获取要进行提现的用户信息
        withdrawal_model: RspWithdrawal | dict = self.__request_withdrawal_for_userinfo()
        # 判断数据模型是否验证成功
        if isinstance(withdrawal_model, RspWithdrawal):
            # 获取用户信息
            withdrawal_user_info: RspWithdrawalUser = withdrawal_model.data.user
            # 打印用户信息
            self.logger.info(withdrawal_user_info)
            amount = withdrawal_user_info.amount
            u_ali_account = withdrawal_user_info.u_ali_account
            u_ali_real_name = withdrawal_user_info.u_ali_real_name
        else:
            user_info = withdrawal_model.get("data", {}).get("user")
            if user_info is None:
                raise RspAPIChanged(APIS.WITHDRAWAL)
            self.logger.info(user_info)
            amount = user_info.get("amount", 0)
            u_ali_account = user_info.get("u_ali_account")
            u_ali_real_name = user_info.get("u_ali_real_name")

        if amount < 30 or amount // 100 < self.withdraw:
            raise WithdrawFailed(f"当前账户余额达不到提现要求!")

        if self.withdraw_type == "wx":
            self.logger.info("💰 开始进行微信提现操作...")
            self.__request_do_withdraw(amount, "wx")
        elif self.withdraw_type == "ali":
            self.logger.info("💰 开始进行支付宝提现操作...")
            if u_ali_account is None or u_ali_real_name is None:
                u_ali_account = self.aliAccount
                u_ali_real_name = self.aliName

            if u_ali_account is None or u_ali_real_name is None:
                raise Exception("🔴💰 请先配置支付宝账号信息，再进行提现操作!")

            self.__request_do_withdraw(
                amount,
                "ali",
                u_ali_account,
                u_ali_real_name
            )
        else:
            raise Exception(f"🟡💰 作者目前暂未适配此【{self.withdraw_type}】提现方式!")

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

        withdraw_result: list | str = self.request_for_json(
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
            if isinstance(withdraw_result, list):
                withdraw_result: dict = withdraw_result[0]
            elif isinstance(withdraw_result, str):
                withdraw_result: str = re.sub(r"<pre>.*?</pre>", "", withdraw_result, flags=re.S)
                withdraw_result: dict = json.loads(withdraw_result)
            else:
                raise RspAPIChanged(APIS.DO_WITHDRAWAL)

            if withdraw_result['code'] == 0:
                self.logger.info(f"🟢💰 提现成功! 预计到账 {amount / 100} 元")
            else:
                self.logger.info(f"🟡💰 提现失败，原因：{withdraw_result['msg']}")
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.exception(f"🟡💰 提现失败，原因：{e}，原始数据: {withdraw_result}")

    def __request_withdrawal_for_userinfo(self) -> RspWithdrawal | dict:
        """
        发起提款请求，从而获取提款用户信息
        :return:
        """
        return self.request_for_json(
            "GET",
            APIS.WITHDRAWAL,
            "获取提款用户信息 base_client",
            client=self.base_client,
            model=RspWithdrawal
        )

    def __pass_detect_and_read_v2(self, part_api_path, full_api_path, *args, **kwargs):

        is_need_push = False
        is_need_increase = False  # 是否需要自增计数

        retry_count = 2
        turn_count = self.current_read_count // 30 + 1
        self.logger.war(f"🟡📖 当前是第[{turn_count}]轮阅读")
        read_count = self.current_read_count % 30 + 1
        # 打印阅读情况
        if self.current_read_count != 0:
            msg = f"🟡📖 准备阅读第[{turn_count} - {read_count}]篇, 已成功阅读[{self.current_read_count}]篇"
        else:
            msg = f"🟡📖 准备阅读[{turn_count} - {read_count}]篇"
        self.logger.war(msg)

        retry_count_when_None = retry_count
        retry_count_when_exp_access = retry_count

        article_map = {}

        t_c = 0

        while True:
            # 发起初始请求，获取阅读文章链接数据
            res_model = self.__request_for_do_read_json(full_api_path)
            # 判断是否阅读成功，并且获得了奖励

            if res_model is None:
                if retry_count_when_None == 0:
                    raise PauseReadingTurnNext("完成阅读数据返回为空次数过多，为避免封号和黑号，暂停此用户阅读")
                if retry_count_when_None > 0:
                    self.logger.error("完成阅读失败，数据返回为空, 尝试重新请求")
                    retry_count_when_None -= 1
                    # 睡眠
                    self.sleep_fun(False)
                    continue
            else:
                # 如果模型数据不为空，那么这里判断上一篇文章的检测结果是否成功
                if t_c >= 1 and res_model.success_msg and "阅读成功" in res_model.success_msg:
                    if t_c <= 1:
                        s = f'🟢✅️ [{turn_count} - {read_count}] {res_model.success_msg}'
                    else:
                        s = f'🟢✅️ [{turn_count} - {read_count - 1}] {res_model.success_msg}'
                    self.logger.info(s)
                    read_count += 1
                    self.current_read_count += 1
            if isinstance(res_model, dict):
                self.logger.war(f"此消息用来调试，报错请截图: {res_model.__str__()}")
            else:
                self.logger.war(f"此消息用来调试，报错请截图: {res_model.dict().__str__()}")
            # 获取有效的返回个数
            ret_count = res_model.ret_count
            if ret_count == 3 and res_model.jkey is None:
                # 如果是3个，且没有jkey返回，则大概率就是未通过检测
                self.new_detected_data.add(article_map.get(f"{turn_count} - {read_count - 1}", ""))
                if res_model.is_pass_failed:
                    raise FailedPassDetect()
                else:
                    raise FailedPassDetect("🔴 貌似检测失败了，具体请查看上方报错原因")
            # 获取返回的阅读文章链接
            article_url = res_model.url
            # 判断当前阅读状态是否被关闭
            if article_url == "close":
                if res_model.msg and res_model.msg is not None:
                    msg = res_model.msg
                else:
                    msg = res_model.success_msg

                if "本轮阅读已完成" == msg:
                    self.logger.info(f"🟢✔️ {msg}")
                    return
                if "任务获取失败" in msg:
                    self.wait_queue.put(5)
                    self.wait_queue.put(self.logger.name)
                    raise StopReadingNotExit(f"检测到任务获取失败，当前可能暂无文章返回，线程自动睡眠5分钟后重启")
                if "检测未通过" in msg:
                    last_article_url = article_map.get(f"{turn_count} - {read_count - 1}", "")
                    if last_article_url:
                        self.new_detected_data.add(last_article_url)
                    raise FailedPassDetect(f"🟢⭕️ {msg}")
                if "异常访问" in msg:
                    self.logger.error(msg)
                    if retry_count_when_exp_access > 0:
                        self.logger.war("正在准备重试...")
                        time.sleep(2)
                        retry_count_when_exp_access -= 1
                        continue
                    else:
                        raise StopReadingNotExit("异常访问重试次数过多，当前用户停止执行!")

                raise FailedPassDetect(f"🟢⭕️ {msg}")
            # 抓包时偶然看到返回的数据（猜测应该是晚上12点前后没有阅读文章）
            if ret_count == 1 and article_url is None:
                # 这里做一下重试，固定重试次数为 2
                if retry_count == 0:
                    raise NoSuchArticle(
                        "🟡 当前账号没有文章链接返回，为避免黑号和封号，已停止当前账号运行，请等待5至6分钟再运行或先手动阅读几篇再运行!")
                if ret_count >= 0:
                    self.logger.war(f"🟡 返回的阅读文章链接为None, 尝试重新请求")
                    retry_count -= 1
                    full_api_path = self.__build_do_read_url_path(
                        part_api_path,
                        jkey=res_model.jkey
                    )
                    # 睡眠
                    self.sleep_fun(False)
                    continue

            # 如果经过上方重试后仍然为None，则抛出异常
            if article_url is None:
                raise ValueError(f"🔴 返回的阅读文章链接为None, 或许API关键字更新啦, 响应模型为：{res_model}")

            if t_c >= 1:
                # 打印阅读情况
                self.logger.war(f"🟡 准备阅读第[{turn_count} - {read_count}]篇, 已成功阅读[{self.current_read_count}]篇")
            else:
                t_c += 1
            self.logger.info(f"【第 [{turn_count} - {read_count}] 篇文章信息】\n{self.parse_wx_article(article_url)}")

            article_map[f"{turn_count} - {read_count}"] = article_url

            # 提取链接biz
            biz_match = self.NORMAL_LINK_BIZ_COMPILE.search(article_url)

            if t_c == 0 and self.first_while_to_push:
                self.logger.war("🟡 固定第一次循环，走推送通道")
                is_need_push = True
            # 判断下一篇阅读计数是否达到指定检测数
            elif self.current_read_count + 1 in self.custom_detected_count:
                self.logger.war(f"🟡📕 达到自定义计数数量，走推送通道!")
                is_need_push = True
            # 判断是否是检测文章
            elif "chksm" in article_url or not self.ARTICLE_LINK_VALID_COMPILE.match(article_url):
                self.logger.war(f"🟡📕 出现包含检测特征的文章链接，走推送通道!")
                is_need_push = True
            # 判断是否是检测文章
            elif article_url in self.detected_data or article_url in self.new_detected_data:
                self.logger.war(f"🟡📕 出现被标记的文章链接, 走推送通道!")
                is_need_push = True
            # 判断是否是检测文章
            elif biz_match and biz_match.group(1) in self.detected_biz_data:
                self.logger.war(f"🟡📕 出现已被标记的biz文章，走推送通道!")
                is_need_push = True
            # 判断此次请求后返回的键值对数量是多少
            elif ret_count == 2:
                self.logger.war(f"🟡📕 当前已进入检测文章盲区，无法判断是否会返回检测文章")
                # 判断下一篇阅读计数是否达到指定检测数
                if self.current_read_count + 1 in self.custom_detected_count:
                    self.logger.war(f"🟡📕 达到自定义计数数量，走推送通道!")
                    is_need_push = True
                else:
                    # 判断是否开启了“未知走推送”开关，以及当前是第2次循环及以上
                    if self.unknown_to_push:
                        self.logger.war(f"🟡📕 “未知走推送”已开启，当前文章走推送通道!")
                        is_need_push = True
                    elif not self.unknown_to_push:
                        self.logger.war(
                            f"🟡📕 “未知走推送”未开启, 阅读成功与否听天由命, 响应数据如下: \n{res_model.dict()}")
            elif ret_count == 4:
                # 表示正处于检测中
                self.logger.war(f"🟡📕 上篇文章[{turn_count} - {read_count - 1}]检测结果为：{res_model.success_msg}")
                if self.just_in_case:
                    self.logger.war(f"🟡📕 “以防万一”已开启，下一篇仍然推送")
                    is_need_push = True
                # 判断是否是阅读成功，如果是则标记上一个文章链接
                if "阅读成功" in res_model.success_msg:
                    self.new_detected_data.add(article_map.get(f"{turn_count} - {read_count - 1}", ""))
            elif ret_count == 3 and res_model.jkey is not None:
                if "阅读成功" not in res_model.success_msg:
                    self.logger.error(f"🔴📕 {res_model.success_msg}")
                # 没有看到要用什么，但是每次do_read都会请求2遍，故这里也添加调用
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
            else:
                raise Exception(f"🔴📕 do_read 出现未知错误，ret_count={ret_count}")

            # 先推送
            if is_need_push:
                is_pushed = self.__push_article(article_url, turn_count, read_count)
                is_need_push = False
                # 当前阅读篇数自增1
                self.current_read_count += 1
                read_count += 1
            else:
                is_pushed = False

            # 重新构建 full_api_path
            full_api_path = self.__build_do_read_url_path(
                part_api_path,
                jkey=res_model.jkey
            )
            # 随机睡眠，模拟阅读时间
            self.sleep_fun(is_pushed)
            # 重置重试次数

    def __pass_detect_and_read(self, part_api_path, full_api_path, *args, **kwargs):
        """
        尝试通过检测并且开始阅读
        :param part_api_path: 部分api路径
        :param full_api_path: 初始完整api路径（后面会随着阅读文章链接的不同改变）
        :return:
        """
        is_need_push = False
        is_need_increase = False  # 是否需要自增计数

        retry_count = 2
        turn_count = self.current_read_count // 30 + 1
        self.logger.war(f"🟡 当前是第[{turn_count}]轮阅读")
        read_count = self.current_read_count % 30 + 1
        # 打印阅读情况
        if self.current_read_count != 0:
            msg = f"🟡 准备阅读第[{turn_count} - {read_count}]篇, 已成功阅读[{self.current_read_count}]篇"
        else:
            msg = f"🟡 准备阅读[{turn_count} - {read_count}]篇"
        self.logger.war(msg)

        retry_count_when_None = retry_count
        retry_count_when_exp_access = retry_count

        article_map = {}

        t_c = 0

        while True:
            # 发起初始请求，获取阅读文章链接数据
            res_model = self.__request_for_do_read_json(full_api_path)
            # 判断是否阅读成功，并且获得了奖励

            if res_model is None:
                if retry_count_when_None == 0:
                    raise PauseReadingTurnNext("完成阅读数据返回为空次数过多，为避免封号和黑号，暂停此用户阅读")
                if retry_count_when_None > 0:
                    self.logger.error("完成阅读失败，数据返回为空, 尝试重新请求")
                    retry_count_when_None -= 1
                    # 睡眠
                    self.sleep_fun(False)
                    continue
            else:
                # 如果模型数据不为空，那么这里判断上一篇文章的检测结果是否成功
                if res_model.success_msg and "获得" in res_model.success_msg:
                    if t_c <= 1:
                        s = f'🟢✅️ [{turn_count} - {read_count}] {res_model.success_msg}'
                    else:
                        s = f'🟢✅️ [{turn_count} - {read_count - 1}] {res_model.success_msg}'
                    self.logger.info(s)
                    read_count += 1
                    self.current_read_count += 1
            # 获取有效的返回个数
            ret_count = res_model.ret_count
            if ret_count == 3 and res_model.jkey is None:
                # 如果是3个，且没有jkey返回，则大概率就是未通过检测
                self.new_detected_data.add(article_map.get(f"{turn_count} - {read_count - 1}", ""))
                if res_model.is_pass_failed:
                    raise FailedPassDetect()
                else:
                    raise FailedPassDetect("🔴 貌似检测失败了，具体请查看上方报错原因")
            # 获取返回的阅读文章链接
            article_url = res_model.url
            # 判断当前阅读状态是否被关闭
            if article_url == "close":

                if res_model.msg and res_model.msg is not None:
                    msg = res_model.msg
                else:
                    msg = res_model.success_msg

                if "本轮阅读已完成" == msg:
                    self.logger.info(f"🟢✔️ {msg}")
                    return
                if "任务获取失败" in msg:
                    self.wait_queue.put(5)
                    self.wait_queue.put(self.logger.name)
                    raise StopReadingNotExit(f"检测到任务获取失败，当前可能暂无文章返回，线程自动睡眠5分钟后重启")
                if "检测未通过" in msg:
                    last_article_url = article_map.get(f"{turn_count} - {read_count - 1}", "")
                    if last_article_url:
                        self.new_detected_data.add(last_article_url)
                    raise FailedPassDetect(f"🟢⭕️ {msg}")
                if "异常访问" in msg:
                    self.logger.error(msg)
                    if retry_count_when_exp_access > 0:
                        self.logger.war("正在准备重试...")
                        time.sleep(2)
                        retry_count_when_exp_access -= 1
                        continue
                    else:
                        raise StopReadingNotExit("异常访问重试次数过多，当前用户停止执行!")

                raise FailedPassDetect(f"🟢⭕️ {msg}")
            # 抓包时偶然看到返回的数据（猜测应该是晚上12点前后没有阅读文章）
            if ret_count == 1 and article_url is None:
                # 这里做一下重试，固定重试次数为 2
                if retry_count == 0:
                    raise NoSuchArticle(
                        "🟡 当前账号没有文章链接返回，为避免黑号和封号，已停止当前账号运行，请等待5至6分钟再运行或先手动阅读几篇再运行!")
                if ret_count >= 0:
                    self.logger.war(f"🟡 返回的阅读文章链接为None, 尝试重新请求")
                    retry_count -= 1
                    full_api_path = self.__build_do_read_url_path(
                        part_api_path,
                        jkey=res_model.jkey
                    )
                    # 睡眠
                    self.sleep_fun(False)
                    continue

            # 如果经过上方重试后仍然为None，则抛出异常
            if article_url is None:
                raise ValueError(f"🔴 返回的阅读文章链接为None, 或许API关键字更新啦, 响应模型为：{res_model}")

            if t_c >= 1:
                # 打印阅读情况
                self.logger.war(f"🟡 准备阅读第[{turn_count} - {read_count}]篇, 已成功阅读[{self.current_read_count}]篇")
            else:
                t_c += 1
            self.logger.info(f"【第 [{turn_count} - {read_count}] 篇文章信息】\n{self.parse_wx_article(article_url)}")

            article_map[f"{turn_count} - {read_count}"] = article_url

            # 提取链接biz
            biz_match = self.NORMAL_LINK_BIZ_COMPILE.search(article_url)
            # 判断下一篇阅读计数是否达到指定检测数
            if self.current_read_count + 1 in self.custom_detected_count:
                self.logger.war(f"🟡 达到自定义计数数量，走推送通道!")
                is_need_push = True
            # 判断是否是检测文章
            elif "chksm" in article_url or not self.ARTICLE_LINK_VALID_COMPILE.match(article_url):
                self.logger.war(f"🟡 出现包含检测特征的文章链接，走推送通道!")
                is_need_push = True
            # 判断是否是检测文章
            elif article_url in self.detected_data or article_url in self.new_detected_data:
                self.logger.war(f"🟡 出现被标记的文章链接, 走推送通道!")
                is_need_push = True
            # 判断是否是检测文章
            elif biz_match and biz_match.group(1) in self.detected_biz_data:
                self.logger.war(f"🟡 出现已被标记的biz文章，走推送通道!")
                is_need_push = True
            # 判断此次请求后返回的键值对数量是多少
            elif ret_count == 2:
                self.logger.war(f"🟡 当前已进入检测文章盲区，无法判断是否会返回检测文章")
                # 判断下一篇阅读计数是否达到指定检测数
                if self.current_read_count + 1 in self.custom_detected_count:
                    self.logger.war(f"🟡 达到自定义计数数量，走推送通道!")
                    is_need_push = True
                else:
                    # 判断是否开启了“未知走推送”开关，以及当前是第2次循环及以上
                    if self.unknown_to_push:
                        self.logger.war(f"🟡 “未知走推送”已开启，当前文章走推送通道!")
                        is_need_push = True
                    elif not self.unknown_to_push:
                        self.logger.war(
                            f"🟡 “未知走推送”未开启, 阅读成功与否听天由命, 响应数据如下: \n{res_model.dict()}")
            elif ret_count == 4:
                # 表示正处于检测中
                self.logger.war(f"🟡 上篇文章[{turn_count} - {read_count - 1}]检测结果为：{res_model.success_msg}")
                if self.just_in_case:
                    self.logger.war(f"🟡 “以防万一”已开启，下一篇仍然推送")
                    is_need_push = True
                # 判断是否是阅读成功，如果是则标记上一个文章链接
                if "阅读成功" in res_model.success_msg:
                    self.new_detected_data.add(article_map.get(f"{turn_count} - {read_count - 1}", ""))
            elif ret_count == 3 and res_model.jkey is not None:
                if "阅读成功" not in res_model.success_msg:
                    self.logger.error(f"🔴 {res_model.success_msg}")
                # 没有看到要用什么，但是每次do_read都会请求2遍，故这里也添加调用
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
            else:
                raise Exception(f"🔴 do_read 出现未知错误，ret_count={ret_count}")

            # 先推送
            if is_need_push:
                is_pushed = self.__push_article(article_url, turn_count, read_count)
                is_need_push = False
                # 当前阅读篇数自增1
                self.current_read_count += 1
                read_count += 1
            else:
                is_pushed = False

            # 重新构建 full_api_path
            full_api_path = self.__build_do_read_url_path(
                part_api_path,
                jkey=res_model.jkey
            )
            # 随机睡眠，模拟阅读时间
            self.sleep_fun(is_pushed)
            # 重置重试次数

    def __push_article(self, article_url, turn_count, read_count):
        push_types = self.push_types
        push_result = []
        if 1 in push_types:
            push_result.append(self.wx_pusher(article_url, detecting_count=read_count))
        if 2 in push_types:
            push_result.append(self.wx_business_pusher(
                article_url,
                detecting_count=read_count,
                situation=(
                    self.logger.name, turn_count, read_count, self.current_read_count, self.current_read_count + 1),
                tips=f"请尽快在指定时间{self.push_delay[0]}秒内阅读完此篇文章"
            ))

        # 只要其中任意一个推送成功，则赋值为True
        is_pushed = any(push_result)
        # 如果推送失败
        if not is_pushed:
            # 直接抛出异常
            raise FailedPushTooManyTimes()
        return is_pushed

    def __request_for_do_read_json(self, do_read_full_path: str) -> RspDoRead | dict:
        ret = self.request_for_json(
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
        return self.request_for_page(
            r_js_path,
            "请求r.js源代码, read_client",
            client=self.read_client,
            update_headers={
                "Referer": self.load_page_url.__str__(),
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
        return self.request_for_page(
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
            self.logger.info(recommend_data.data.user)
            infoView = recommend_data.data.infoView
            num = int(infoView.num)
            self.logger.info(infoView)
            msg = infoView.msg
        else:
            infoView = recommend_data.get("data", {}).get("infoView")
            if infoView is None:
                raise RspAPIChanged(APIS.RECOMMEND)
            num = infoView.get("num")
            if num is None:
                raise RspAPIChanged(APIS.RECOMMEND)
            else:
                num = int(num)
            msg = infoView.get("msg")
        # 记录当前阅读文章篇数
        self.current_read_count = int(num)
        # 判断是否返回了msg
        if msg:
            # 如果返回的信息，有以下内容，则提前进行异常抛出，避免出现其他冗余的请求
            if "下一批" in msg:
                raise PauseReadingAndCheckWait(msg)
            elif "阅读限制" in msg or "任务上限" in msg or "微信限制" in msg:
                raise StopReadingNotExit(msg)

    def __request_for_read_url(self, retry: int = 3) -> URL:
        """
        获取阅读链接
        :return:
        """
        data: RspReadUrl | dict | None = self.request_for_json(
            "GET",
            APIS.GET_READ_URL,
            "请求阅读链接 base_client",
            model=RspReadUrl,
            client=self.base_client
        )
        if data is None:
            if retry <= 0:
                raise StopReadingNotExit("获取阅读链接重试次数过多，停止运行")
            else:
                self.logger.war(f"获取阅读链接失败，准备重新获取，剩余重试次数: {retry - 1}")
                return self.__request_for_read_url(retry=retry - 1)

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
        recommend_data = self.request_for_json("GET", APIS.RECOMMEND, "请求推荐数据 base_client", update_headers={
            "Referer": referer.__str__()
        }, model=RspRecommend, client=self.base_client)

        return recommend_data

    def __request_redirect_for_redirect(self) -> URL:
        """
        请求入口链接返回的重定向链接（这个链接用来获取首页源代码）
        :return:
        """
        self.base_client.cookies = self.cookie_dict
        return self.request_for_redirect(self.base_full_url, "请求入口链接返回的重定向链接", client=self.base_client)

    def __request_entry_for_redirect(self) -> URL:
        """
        请求入口链接，从而获取重定向链接
        :return:
        """
        return self.request_for_redirect(self.entry_url, "请求入口链接， main_client", client=self.main_client)

    def fetch_read_api(self, homepage: str):
        result = re.findall(r"(?:href|src)=['\"](.*?)['\"]", homepage)
        all_js_url = [r for r in result if r.endswith('.js')]

        def __fetch(url):
            js_code = httpx.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            })
            if r := re.search(r"make_qrcode\(\)\s*\{.*?\+\s*['\"](.*?)['\"]", js_code.text):
                return r.group(1)

        self.lock.locked()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(__fetch, url) for url in all_js_url]
            for future in as_completed(futures):
                if r := future.result():
                    self.logger.war(f"🟢 阅读API提取成功: {r}")
                    return r
        self.lock.release()

    @property
    def unknown_to_push(self):
        ret = self.account_config.unknown_to_push
        if ret is None:
            ret = self.config_data.unknown_to_push
        return ret if ret is not None else False

    @property
    def just_in_case(self):
        ret = self.account_config.just_in_case
        if ret is None:
            ret = self.config_data.just_in_case
        return ret if ret is not None else True

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
    def iu(self):
        return self._cache.get(f"iu_{self.ident}")

    @iu.setter
    def iu(self, value):
        self._cache[f"iu_{self.ident}"] = value

    @property
    def load_page_url(self):
        return self._cache.get(f"load_page_url_{self.ident}")

    @load_page_url.setter
    def load_page_url(self, value):
        self._cache[f"load_page_url_{self.ident}"] = value


if __name__ == '__main__':
    KLYDV2()
