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

from httpx import URL

from config import load_klyd_config
from exception.common import PauseReadingTurnNext, StopReadingNotExit, CookieExpired, RspAPIChanged, ExitWithCodeChange, \
    FailedPushTooManyTimes, NoSuchArticle
from exception.klyd import FailedPassDetect, \
    RegExpError, WithdrawFailed
from schema.klyd import KLYDConfig, RspRecommend, RspReadUrl, RspDoRead, ArticleInfo, RspWithdrawal, RspWithdrawalUser
from script.common.base import WxReadTaskBase, RetTypes
from utils import EntryUrl, md5
from utils.logger_utils import NestedLogColors


class APIS:
    # 获取推荐信息
    RECOMMEND = "/tuijian"
    # 获取阅读链接
    GET_READ_URL = "/new/get_read_url"
    # 获取提现用户信息
    WITHDRAWAL = "/withdrawal"
    # 开始进行提现
    DO_WITHDRAWAL = "/withdrawal/doWithdraw"


class KLYDV2(WxReadTaskBase):
    CURRENT_SCRIPT_VERSION = "2.0.1"
    CURRENT_TASK_NAME = "可乐阅读"

    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-03-30"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-02"

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
    # 普通链接Biz提取
    NORMAL_LINK_BIZ_COMPILE = re.compile(r"__biz=(.*?)&", re.S)

    def __init__(self, config_data: KLYDConfig = load_klyd_config()):
        self.detected_biz_data = config_data.biz_data
        self.base_full_url = None
        # self.exclusive_url = config_data.exclusive_url
        super().__init__(config_data=config_data, logger_name="🥤阅读")

    def get_entry_url(self):
        return EntryUrl.get_klrd_entry_url()[0]

    def init_fields(self):
        first_redirect_url: URL = self.__request_entry_for_redirect()
        self.base_url = f"{first_redirect_url.scheme}://{first_redirect_url.host}"
        self.base_full_url = first_redirect_url

    def run(self, name):

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
        if 'f9839ced92845cbf6166b0cf577035d3' != md5(homepage_html):
            raise ExitWithCodeChange("homepage_html")

        self.is_need_withdraw = False
        try:
            # 获取推荐数据（里面包含当前阅读的信息）
            recommend_data = self.__request_recommend_json(homepage_url)
            self.__print_recommend_data(recommend_data)
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
            self.__pass_detect_and_read(do_read_url_part_path, do_read_url_full_path)
            # 尝试进行提现操作
            self.__request_withdraw()
            self.is_need_withdraw = False
        except FailedPushTooManyTimes as e:
            self.logger.war(e)
            self.is_need_withdraw = False
            sys.exit(0)
        except (FailedPassDetect, WithdrawFailed, NoSuchArticle) as e:
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
            raise WithdrawFailed("🔴 提现失败, 当前账户余额达不到提现要求!")

        if self.withdraw_type == "wx":
            self.logger.info("开始进行微信提现操作...")
            self.__request_do_withdraw(amount, "wx")
        elif self.withdraw_type == "ali":
            self.logger.info("开始进行支付宝提现操作...")
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
                self.logger.info(f"🟢 提现成功! 预计到账 {amount / 100} 元")
            else:
                self.logger.info(f"🟡 提现失败，原因：{withdraw_result['msg']}")
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.exception(f"🟡 提现失败，原因：{e}，原始数据: {withdraw_result}")

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

    def __pass_detect_and_read(self, part_api_path, full_api_path, *args, **kwargs):
        """
        尝试通过检测并且开始阅读
        :param part_api_path: 部分api路径
        :param full_api_path: 初始完整api路径（后面会随着阅读文章链接的不同改变）
        :return:
        """
        is_need_push = False
        is_pushed = False
        retry_count = 2
        turn_count = self.current_read_count // 30 + 1
        self.logger.info(f"♻️ 开始第{turn_count}轮阅读...")
        read_count = 0
        while True:
            if self.current_read_count != 0:
                msg = f"准备阅读{turn_count}轮第{read_count + 1}篇, 已阅读{self.current_read_count}篇"
            else:
                msg = f"准备阅读{turn_count}轮第{read_count + 1}篇"
            self.logger.info(msg)
            # 发起完成阅读请求，从而获取下一次阅读的文章链接
            res_model = self.__request_for_do_read_json(full_api_path, is_pushed=is_pushed)
            # 获取有效的返回个数
            ret_count = res_model.ret_count
            if ret_count == 3 and res_model.jkey is None:
                # 如果是3个，且没有jkey返回，则大概率就是未通过检测
                if res_model.is_pass_failed:
                    raise FailedPassDetect()
                else:
                    raise FailedPassDetect("🔴 貌似检测失败了，具体请查看上方报错原因")
            # 获取返回的阅读文章链接
            article_url = res_model.url
            # 判断当前阅读状态是否被关闭
            if article_url == "close":
                if "本轮阅读已完成" == res_model.success_msg:
                    self.logger.info(f"🟢✔️ {res_model.success_msg}")
                    return
                raise FailedPassDetect(f"🟢⭕️ {res_model.success_msg}")
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
                    self.__alone_sleep_fun(False)
                    continue

            # 如果经过上方重试后仍然为None，则抛出异常
            if article_url is None:
                raise ValueError(f"🔴 返回的阅读文章链接为None, 或许API关键字更新啦, 响应模型为：{res_model}")
            # 提取链接biz
            biz_match = self.NORMAL_LINK_BIZ_COMPILE.search(article_url)
            # 判断是否是检测文章
            if "chksm" in article_url or not self.ARTICLE_LINK_VALID_COMPILE.match(article_url):
                self.logger.info(f"🟡 出现包含检测特征的文章链接，走推送通道!")
                is_need_push = True
            # 判断是否是检测文章
            elif biz_match and biz_match.group(1) in self.detected_biz_data:
                self.logger.info(f"🟡 出现已被标记的biz文章，走推送通道!")
                is_need_push = True
            # 判断此次请求后返回的键值对数量是多少
            elif ret_count == 2:
                # 判断当前阅读数量是否达到指定检测数
                if self.current_read_count in self.custom_detected_count:
                    self.logger.info(f"🟡 达到自定义计数数量，走推送通道!")
                    is_need_push = True
            elif ret_count == 4:
                # 表示正处于检测中
                self.logger.info(f"🟡 此次检测结果为：{res_model.success_msg}")
                if self.just_in_case:
                    self.logger.info(f"🟡 “以防万一”已开启，下一篇仍然推送")
                    is_need_push = True
            elif ret_count == 3 and res_model.jkey is not None:
                # 如果是3个，且有jkey返回，则表示已经通过检测
                if "成功" in res_model.success_msg:
                    # 当前阅读篇数自增1
                    self.current_read_count += 1
                    read_count += 1
                    self.logger.info(f"🟢✅️ {res_model.success_msg}")
                else:
                    self.logger.info(f"🟢❌️ {res_model.success_msg}")
                # 没有看到要用什么，但是每次do_read都会请求2遍，故这里也添加调用
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
                time.sleep(random.randint(1, 3))
                self.__request_for_read_url()
            else:
                raise Exception(f"🔴 do_read 出现未知错误，ret_count={ret_count}")

            # 先推送
            if is_need_push:
                is_pushed = self.wx_pusher_link(res_model.url)
                if not is_pushed:
                    raise FailedPushTooManyTimes()
                is_need_push = False
            else:
                is_pushed = False

            # 重新构建 full_api_path
            full_api_path = self.__build_do_read_url_path(
                part_api_path,
                jkey=res_model.jkey
            )
            # 后打印
            self.__print_article_info(res_model.url)

            self.__alone_sleep_fun(is_pushed)

    def __alone_sleep_fun(self, is_pushed: bool):
        t = self.push_delay[0] if is_pushed else random.randint(self.read_delay[0], self.read_delay[1])
        self.logger.info(f"等待检测完成, 💤 睡眠{t}秒" if is_pushed else f"💤 随机睡眠{t}秒")
        # 睡眠随机时间
        time.sleep(t)

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
        self.logger.info(ArticleInfo(
            article_url=article_url,
            article_biz=article_biz,
            article_title=article_title,
            article_author=article_author,
            article_desc=article_desc
        ))

    def __request_article_page(self, article_url: str):
        return self.request_for_page(article_url, "请求文章信息 article_client", client=self.article_client)

    def __request_for_do_read_json(self, do_read_full_path: str, is_pushed: bool = False) -> RspDoRead | dict:
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
                raise PauseReadingTurnNext(msg)
            elif "阅读限制" in msg or "任务上限" in msg or "微信限制" in msg:
                raise StopReadingNotExit(msg)

    def __request_for_read_url(self) -> URL:
        """
        获取阅读链接
        :return:
        """
        data: RspReadUrl | dict = self.request_for_json(
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

    @property
    def custom_detected_count(self):
        ret = self.config_data.custom_detected_count
        if ret is None:
            ret = self.account_config.custom_detected_count
        return ret if ret is not None else []

    @property
    def current_read_count(self):
        return self._cache.get(f"current_read_count_{self.ident}")

    @current_read_count.setter
    def current_read_count(self, value):
        self._cache[f"current_read_count_{self.ident}"] = value

    @property
    def just_in_case(self):
        ret = self.config_data.just_in_case
        if ret is None:
            ret = self.account_config.just_in_case
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
