# -*- coding: utf-8 -*-
# ltwm_v2.py created by MoMingLog on 4/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-04
【功能描述】
"""
import re
import time

from httpx import URL

from config import load_ltwm_config
from exception.common import StopReadingNotExit, PauseReadingTurnNext, CookieExpired
from schema.ltwm import LTWMConfig, UserPointInfo, LTWMAccount, TaskList, ReaderDomain, GetTokenByWxKey, ArticleUrl, \
    CompleteRead, Sign, BalanceWithdraw
from script.common.base import WxReadTaskBase


class APIS:
    # 通用API前缀
    COMMON = "/api/mobile"

    # API: 获取用户积分信息
    USER_ACCOUNT = f"{COMMON}/userCenter/v1/userAccount"
    # API: 获取当前任务列表信息
    TASK_LIST = f"{COMMON}/task/v1/taskList"

    # 通用阅读任务前缀
    COMMON_READ = f"{COMMON}/act/officialArticle/v1"

    # 阅读任务API: 获取阅读链接
    GET_READ_DOMAIN = f"{COMMON_READ}/getReaderDomain"
    # 阅读任务API: 可能是重置或者获取新的Authorization值，也有可能是将Auth值与domain的key值绑定起来
    GET_TOKEN_BY_WX_KEY = f"{COMMON_READ}/getTokenByWxKey"  # 这个路径并不完整，后面还需要拼接上key值路径
    # 阅读任务API: 获取文章阅读地址
    GET_ARTICLE_URL = f"{COMMON_READ}/getArticle"
    # 阅读任务API: 阅读完成上报地址
    COMPLETE_READ = f"{COMMON_READ}/completeRead"

    # 签到任务API
    SIGN = f"{COMMON}/act/sign/v1/sign"
    # API: 申请提现
    WITHDRAW = f"{COMMON}/withdraw/v1/requestBalanceWithdraw"
    # API: 提现记录
    WITHDRAW_DETAIL = f"{COMMON}/detail/v1/pageAccountWithdraw"


class LTWMV2(WxReadTaskBase):
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "2.0.0"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-04-04"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-04"
    # 当前任务名称
    CURRENT_TASK_NAME = "力天微盟"

    # 当前使用的API域名（这里选择包含protocol）
    CURRENT_API_DOMAIN = "https://api.mb.s8xnldd7kpd.litianwm.cn"

    # 提取“获取域名”操作返回的key值
    FETCH_KEY_COMPILE = re.compile(r"key=(.*)")

    def __init__(self, config_data: LTWMConfig = load_ltwm_config(), run_read_task: bool = True):
        self.run_read_task = run_read_task
        super().__init__(config_data, logger_name="力天微盟")

    def init_fields(self):
        pass

    def run(self, name):
        # 配置基本URL
        self.base_client = self._get_client("base", headers=self.build_base_headers(account_config=self.accounts),
                                            base_url=self.CURRENT_API_DOMAIN, verify=False)
        self.base_client.headers.update({
            "Authorization": self.account_config.authorization
        })
        # 获取用户积分信息，并输出
        user_account = self.__request_user_account()
        if user_account.data is None:
            if "重新登录" in user_account.message:
                raise CookieExpired()
            else:
                raise StopReadingNotExit(user_account.message)

        if user_account.code == 500:
            raise StopReadingNotExit(user_account.message)
        else:
            self.logger.info(user_account)

        if not self.run_read_task:
            self.__request_withdraw()
            return

        # 获取用户任务列表
        task_list = self.__request_taskList()
        is_wait = False
        # 检查当前任务还有哪些未完成
        for data in task_list.data:
            if "文章阅读" in data.name:
                if data.taskRemainTime != 0 and data.status == 2:
                    self.logger.info(f"🟢 当前阅读任务已完成，{data.taskRemainTime}分钟后可继续阅读")
                elif data.taskRemainTime == 0 and data.status == 4:
                    self.logger.info(f"🟢 今日阅读任务已完成!")
                else:
                    self.logger.war(f"🟡 检测到阅读任务待完成，3秒后开始执行...")
                    time.sleep(3)
                    try:
                        self.__do_read_task()
                    except Exception as e:
                        if "本轮阅读成功完成，奖励发放中" in str(e) or "今天任务已完成" in str(e):
                            is_wait = True
                        self.logger.war(f"🟡 {e}")
            if "每日签到" in data.name:
                self.__do_sign_task()

        self.__request_withdraw(is_wait=is_wait)

    def __do_sign_task(self):
        sign_model = self.__request_sign()
        if sign_model.data:
            self.logger.info(sign_model.data)
        else:
            self.logger.war(f"🟡 {sign_model.message}")

    def __do_read_task(self):
        # self.logger.info(task_list)
        # 获取用户阅读链接
        self.logger.war("🟡 正在获取阅读链接...")
        time.sleep(1)
        reader_domain = self.__request_reader_domain()
        if url := reader_domain.data:
            self.logger.info(f"🟢 阅读链接获取成功: {url}")
            url = URL(url)
            self.base_client.headers.update({
                "Origin": f"{url.scheme}://{url.host}",
                "Referer": f"{url.scheme}://{url.host}"
            })
            # self.parse_base_url(read_domain.data, self.read_client)
            self.docking_key = url.params.get("key")
        else:
            raise StopReadingNotExit(f"阅读链接获取失败!")

        # 开始对接阅读池
        self.logger.war("🟡 正在对接阅读池...")
        time.sleep(1.5)
        docking_model = self.__request_docking()
        if "操作成功" in docking_model.message:
            self.logger.info("🟢 阅读池对接成功!")
            if docking_model.data is not None:
                # 无论是否是原来的 auth，这里都进行更新一下，以防万一
                self.base_client.headers.update({
                    "Authorization": docking_model.data
                })
        else:
            self.logger.error("🔴 阅读池对接失败，请联系作者更新!")
        # 开始提取阅读文章地址
        self.logger.war("🟡 正在抽取阅读文章...")
        time.sleep(1.5)
        article_model = self.__request_article_url()
        if "文章地址获取成功" in article_model.message:
            if article_url := article_model.data.articleUrl:
                self.logger.info(f"🟢 文章抽取成功! ")
                self.logger.info(article_model)
                # 打印文章信息
                # self.logger.info(self.parse_wx_article(article_url))
            else:
                self.logger.war(f"🟠 文章地址为空，请检查!")
        else:
            self.logger.error("🔴 阅读文章抽取失败，请联系作者更新!")

        data = {
            "readKey": article_model.data.readKey,
            "taskKey": article_model.data.taskKey
        }

        while True:
            self.sleep_fun(False)
            # 上报阅读结果
            complete_model = self.__request_complete_read(data)

            if complete_model.code == 200:
                if "阅读任务上报成功" in complete_model.message:
                    self.logger.info(f"🟢 阅读任务上报成功")
                    self.logger.info(complete_model)
                    data = {
                        "readKey": complete_model.data.readKey,
                        "taskKey": complete_model.data.taskKey
                    }
                elif "本轮阅读成功" in complete_model.message:
                    raise PauseReadingTurnNext(complete_model.message)
                else:
                    raise StopReadingNotExit(f"阅读任务上报失败, {complete_model.message}")

    def __request_withdraw(self, is_wait: bool = False):
        # 判断是否要进行提现操作
        if not self.is_withdraw:
            self.logger.war(f"🟡 提现开关已关闭，已停止提现任务")
            return

        if is_wait:
            self.logger.info("5秒后开始提现, 请稍后")
            time.sleep(5)
        # 发起查询请求，查看当前用户积分
        user_model = self.__request_user_account()
        if user_model.data.balance > 1000:
            self.logger.war("🟡 满足提现要求，准备提现...")
            withdraw_model = self.__request_do_withdraw()
            if "成功" in withdraw_model.message:
                self.logger.info(f"🟢 提现成功! \n {withdraw_model}")
                # 顺便请求下提现详情
                self.__request_withdraw_detail()
            else:
                self.logger.error(f"🔴 提现失败, {withdraw_model.message}")
        else:
            self.logger.war(f"🟡 当前积分{user_model.data.balance}不满足最低提现要求, 脚本结束!")

    def __request_withdraw_detail(self):
        return self.request_for_json(
            "POST",
            APIS.WITHDRAW_DETAIL,
            "提现详情数据",
            client=self.base_client,
            data={}
        )

    def __request_do_withdraw(self) -> BalanceWithdraw | dict:

        return self.request_for_json(
            "POST",
            APIS.WITHDRAW,
            "提现",
            client=self.base_client,
            model=BalanceWithdraw,
            json={}
        )

    def __request_sign(self) -> Sign | dict:
        """发起签到请求"""
        return self.request_for_json(
            "GET",
            APIS.SIGN,
            "签到请求 base_client",
            client=self.base_client,
            model=Sign
        )

    def __request_complete_read(self, data: dict) -> CompleteRead | dict:
        """
        阅读上报
        :return:
        """
        return self.request_for_json(
            "POST",
            APIS.COMPLETE_READ,
            "阅读任务上报 base_client",
            client=self.base_client,
            model=CompleteRead,
            json=data
        )

    def __request_article_url(self) -> ArticleUrl | dict:
        """获取文章阅读地址"""
        return self.request_for_json(
            "GET",
            APIS.GET_ARTICLE_URL,
            "获取文章阅读地址 base_client",
            client=self.base_client,
            model=ArticleUrl
        )

    def __request_docking(self) -> GetTokenByWxKey | dict:
        """请求阅读对接，对接成功会返回用户的auth，或许也会返回新的，目前未知"""
        return self.request_for_json(
            "GET",
            f"{APIS.GET_TOKEN_BY_WX_KEY}/{self.docking_key}",
            "请求对接阅读池 base_client",
            client=self.base_client,
            model=GetTokenByWxKey
        )

    def __request_reader_domain(self) -> ReaderDomain | dict:
        """获取正在进行阅读操作的用户对应的domain"""
        return self.request_for_json(
            "GET",
            APIS.GET_READ_DOMAIN,
            "获取专属阅读链接 base_client",
            client=self.base_client,
            model=ReaderDomain
        )

    def __request_taskList(self) -> TaskList | dict:
        """获取任务列表信息"""
        return self.request_for_json(
            "GET",
            APIS.TASK_LIST,
            "获取任务列表信息 base_client",
            client=self.base_client,
            model=TaskList
        )

    def __request_user_account(self) -> UserPointInfo | dict:
        """获取用户积分信息"""
        return self.request_for_json(
            "GET",
            APIS.USER_ACCOUNT,
            "获取用户积分信息 base_client",
            client=self.base_client,
            model=UserPointInfo,
        )

    def build_base_headers(self, account_config: LTWMConfig = None):
        entry_url = self.get_entry_url()
        header = super().build_base_headers()
        header.update({
            "Origin": entry_url,
            "Referer": entry_url,
        })
        return header

    def get_entry_url(self) -> str:
        return "http://e9adf325c38844188a2f0aefaabb5e0d.op20skd.toptomo.cn/?fid=12286"

    @property
    def docking_key(self):
        return self._cache.get(f"docking_key_{self.ident}")

    @docking_key.setter
    def docking_key(self, value):
        if not value or value is None:
            raise StopReadingNotExit("key不能为空，已停止对接")

        self._cache[f"docking_key_{self.ident}"] = value

    @property
    def account_config(self) -> LTWMAccount:
        return super().account_config


if __name__ == '__main__':
    LTWMV2()
