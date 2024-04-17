# -*- coding: utf-8 -*-
# ymz_v2.py created by MoMingLog on 17/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-17
【功能描述】
"""
import base64
import re
import time
from io import BytesIO

from PIL import Image
from httpx import URL
from pyzbar.pyzbar import decode

from config import load_ymz_config
from exception.common import RegExpError, PauseReadingAndCheckWait
from schema.ymz import YMZConfig, RspTaskList, RspLogin, RspArticleUrl, RspSignIn, RspWithdrawOptions, RspUserInfo
from script.common.base import WxReadTaskBase


class APIS:
    COMMON = "/ttz/api"

    # API: 登录
    LOGIN = f"{COMMON}/login"
    # API: 获取用户信息
    GET_USER_INFO = f"{COMMON}/queryUserSumScoreById"
    # API: 获取任务列表信息
    GET_TASK_LIST = f"{COMMON}/queryActivityContentList"
    # API: 设置密码
    SET_WITHDRAW_PWD = f"{COMMON}/setUserCashPwd"
    # API: 阅读二维码
    READ_QR_CODE = f"{COMMON}/queryActivityContentx"

    # API: 获取文章链接（程序自动获取）
    GET_ARTICLE = ""

    # API: 签到
    SIGN_IN = f"{COMMON}//userSignin"
    # API: 提现选项
    WITHDRAW_OPTIONS = f"{COMMON}/queryMoneyInfo"
    # API: 提现
    WITHDRAW = "/ttz/pay/pocketMoney"


class YMZV2(WxReadTaskBase):
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "2.0.0"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-04-17"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-17"
    # 当前任务名称
    CURRENT_TASK_NAME = "有米赚"

    CURRENT_BASE_URL = "http://xingeds.3fexgd.zhijianzzmm.cn"
    CURRENT_ORIGIN_URL = "http://gew.gewxg.234tr.zhijianzzmm.cn"

    # 加载页正则，主要提取 originPath(包括链接)
    LOADING_PAGE_COMPILE = re.compile(r"var\soriginPath\s*=\s*['\"](.*?)['\"];?", re.S)
    # 提取获取文章链接的API
    GET_ARTICLE_API_COMPILE = re.compile(r"(?<!//\s)var\stoUrl\s*=\s*['\"](.*?)['\"]", re.S)

    def __init__(self, config_data: YMZConfig = load_ymz_config(), run_read_task: bool = True):
        self.run_read_task = run_read_task
        super().__init__(config_data, logger_name="有米赚")

    def init_fields(self, retry_count: int = 3):
        pass

    def run(self, name, *args, **kwargs):
        self.parse_base_url(self.CURRENT_BASE_URL, self.base_client)

        login_result = self.__request_login()

        retry_count = kwargs.pop("retry_count", 3)

        if login_result is None:
            if retry_count <= 0:
                self.logger.err(f"❌ 登录失败, 重试次数已用完")
                return

            self.logger.err(f"❌ 登录失败, 准备重试，当前重试次数为：{retry_count}")
            retry_count -= 1
            time.sleep(3)
            self.run(name, retry_count=retry_count, **kwargs)
            return

        self.logger.info(login_result)
        if not login_result.data.isPwd:
            self.logger.war(f"🟡 当前用户未设置提现密码!")
            if self.pwd is not None:
                self.logger.war(f"🟡 检测到当前用户配置了提现密码，正在自动设置密码为：{self.pwd}")
                set_pwd_result = self.__request_set_pwd()
                if set_pwd_result.get("code") == 200 and set_pwd_result.get("success"):
                    self.logger.suc(f"🟢 自动设置提现密码成功")
                else:
                    self.logger.err(f"❌ 自动设置提现密码失败, 原始响应数据为: {set_pwd_result}")
            else:
                self.logger.war(f"🟡 当前用户未设置提现密码，会影响到提现操作，请前往配置项配置，程序会自动设置密码!")
        else:
            self.logger.info(f"🟢 当前用户已设置提现密码")

        if not self.run_read_task:
            self.do_withdraw_task()
            return

        userinfo = self.__request_userinfo()
        self.logger.info(userinfo)

        task_list = self.__request_task_list()

        is_raise_next = False
        btn_name = ""

        for task in task_list.data:
            if "文章阅读" in task.typeName:
                if task.isShowBtn == 0:
                    self.do_read_task(task.typeName)
                elif task.isShowBtn == 1:
                    if "还剩" in task.btnName:
                        self.logger.info(f"⏳️ 任务 [{task.typeName}] {task.btnName}")
                        is_raise_next = True
                        btn_name = task.btnName
                    else:
                        self.logger.info(f"⏩ 任务 [{task.typeName}] {task.btnName}")
                else:
                    self.logger.info(f"按钮处于未记录状态 {task.isShowBtn} - {task.btnName}")
            elif "每日签到" in task.typeName:
                if task.isShowBtn == 0:
                    self.do_sign_in_task(task.typeName)
                elif task.isShowBtn == 1:
                    if "已签到" in task.btnName:
                        self.logger.info(f"✅️ 任务 [{task.typeName}] {task.btnName}")
                    else:
                        self.logger.info(f"⏩ 任务 [{task.typeName}] {task.btnName}")
                else:
                    self.logger.info(f"按钮处于未记录状态 {task.isShowBtn} - {task.btnName}")
        try:
            if is_raise_next:
                raise PauseReadingAndCheckWait(btn_name)
        finally:
            self.do_withdraw_task()

    def do_withdraw_task(self):

        if not self.is_withdraw:
            self.logger.war(f"🟡 提现开关已关闭，已停止提现任务")
            return

        self.logger.info(f"当前处于提现阶段，1秒后查询用户信息...")
        time.sleep(1)
        userinfo = self.__request_userinfo()
        self.logger.info(userinfo)
        # 获取当前积分
        current_money = userinfo.data.cashMoney

        if self.withdraw != 0 and current_money < self.withdraw:
            self.logger.war(f"当前积分不足 {self.withdraw}，无法提现")
            return

        # 获取所有提现金额选项
        withdraw_options = self.__request_withdraw_options()
        goods = []
        for option in withdraw_options.data:
            self.logger.info(f"此消息用来调试，主要看 onMoney 是干嘛的 {option}")
            goods.append((option.money, option.id))

        # 从后往前遍历
        for money, id in goods[::-1]:
            if current_money >= money:
                result = self.__request_withdraw(money, id)
                self.logger.info(result)
                break

    def do_sign_in_task(self, task_name):
        self.logger.war(f"任务 [{task_name}] 未完成，正在尝试签到...")
        result = self.__request_sign_in()
        if result.get("code") == 200:
            self.logger.info(f"✅️ 任务 [{task_name}] {result}")
        else:
            self.logger.err(f"❌ 任务 [{task_name}] 签到失败, 原始响应数据为: {result}")

    def do_read_task(self, task_name):
        self.logger.war(f"任务 [{task_name}] 未完成，正在尝试获取二维码...")
        result = self.__request_qr_code_img_data()
        if result.get("code") == 200:
            self.logger.info(f"✅️ 任务 [{task_name}] 获取二维码成功")
            data = result.get("data", {}).get("twoMicrocodeUrl", "").replace("data:image/png;base64,", "")
            # 将Base64编码的字符串转换为字节
            image_data = base64.b64decode(data)

            # 使用BytesIO将字节转换为二进制流
            image = Image.open(BytesIO(image_data))

            # 使用pyzbar的decode函数解析二维码
            decoded_objects = decode(image)
            # 打印解析结果
            for obj in decoded_objects:
                url = URL(obj.data.decode("utf-8"))
                self.origin_token = url.params.get("token")
                self.logger.info(f"✅️ 任务 [{task_name}] 二维码解析成功：{url}")

                loading_page = self.__request_read_loading_page(url)
                if loading_page:
                    self.logger.info(f"✅️ 任务 [{task_name}] 二维码跳转成功")
                    if r := self.LOADING_PAGE_COMPILE.search(loading_page):
                        if len(r.groups()) != 1:
                            raise RegExpError(self.LOADING_PAGE_COMPILE)
                        # 提取originPath
                        origin_path = r.group(1)
                        self.base_read_url = URL(origin_path)
                        # 更新read_client的base_url
                        self.parse_base_url(origin_path, self.read_client)
                    else:
                        raise RegExpError(self.LOADING_PAGE_COMPILE)

                    if r := self.GET_ARTICLE_API_COMPILE.search(loading_page):
                        if len(r.groups()) != 1:
                            raise RegExpError(self.GET_ARTICLE_API_COMPILE)
                        start_num = 0
                        while True:
                            # 构建获取文章链接API
                            APIS.GET_ARTICLE = f"{self.base_read_url.path}{r.group(1)}{self.modify_token(start_num)}"

                            article_url_model = self.__request_get_article_url()
                            print(article_url_model)
                            if article_url_model:
                                if article_url := article_url_model.data.url:
                                    self.logger.info(self.parse_wx_article(article_url))
                                    start_num = article_url_model.data.startNum
                                    end_num = article_url_model.data.endNum
                                    self.logger.info(f"🟡 任务 [{task_name}] 当前进度：{start_num}/{end_num}")
                                    if start_num == end_num or start_num is None:
                                        self.logger.suc(f"✅️ 任务 [{task_name}] 完成")
                                        break
                                    self.sleep_fun()
                                else:
                                    self.logger.war(
                                        f"🟡 任务 [{task_name}] 链接貌似获取失败了，原始响应为：{article_url_model}")
                                    return
                            else:
                                self.logger.err(f"任务 [{task_name}] 获取文章链接请求失败")
                                return
                    else:
                        raise RegExpError(self.GET_ARTICLE_API_COMPILE)
                else:
                    self.logger.err(f"任务 [{task_name}] 二维码跳转失败")
                    return
        else:
            self.logger.err(f"任务 [{task_name}] 获取二维码失败")
            return

    def __request_withdraw(self, money, moneyId):
        return self.request_for_json(
            "GET",
            f"{APIS.WITHDRAW}?userShowId={self.user_id}&money={money}&wdPassword={self.pwd}&moneyId={moneyId}",
            "请求提现 base_client",
            client=self.base_client
        )

    def __request_withdraw_options(self) -> RspWithdrawOptions | dict:
        return self.request_for_json(
            "GET",
            APIS.WITHDRAW_OPTIONS,
            "请求提现选项 base_client",
            client=self.base_client,
            model=RspWithdrawOptions
        )

    def __request_sign_in(self) -> RspSignIn | dict:
        return self.request_for_json(
            "POST",
            f"{APIS.SIGN_IN}?userShowId={self.user_id}",
            "请求签到 base_client",
            client=self.base_client,
            model=RspSignIn
        )

    def __request_get_article_url(self) -> RspArticleUrl | dict:
        return self.request_for_json(
            "GET",
            APIS.GET_ARTICLE,
            "请求文章链接 base_client",
            client=self.read_client,
            model=RspArticleUrl
        )

    def __request_read_loading_page(self, read_url: str | URL):
        return self.request_for_page(
            read_url,
            "请求阅读加载页面 base_client",
            client=self.read_client
        )

    def __request_qr_code_img_data(self):
        return self.request_for_json(
            "GET",
            f"{APIS.READ_QR_CODE}?userShowId={self.user_id}&type=1",
            "请求二维码 base_client",
            client=self.base_client
        )

    def __request_task_list(self) -> RspTaskList | dict:
        return self.request_for_json(
            "GET",
            f"{APIS.GET_TASK_LIST}?userShowId={self.user_id}",
            "请求任务列表 base_client",
            client=self.base_client,

            model=RspTaskList
        )

    def __request_userinfo(self) -> RspUserInfo | dict:
        return self.request_for_json(
            "GET",
            f"{APIS.GET_USER_INFO}?userShowId={self.user_id}",
            "请求用户信息 base_client",
            client=self.base_client,
            model=RspUserInfo
        )

    def __request_set_pwd(self):
        return self.request_for_json(
            "GET",
            f"{APIS.SET_WITHDRAW_PWD}?userShowId={self.user_id}&wdPassword={self.pwd}&rewdPassword={self.pwd}",
            "设置提现密码 base_client",
            client=self.base_client
        )

    def __request_login(self) -> RspLogin | dict:
        return self.request_for_json(
            "POST",
            APIS.LOGIN,
            "请求登录 base_client",
            client=self.base_client,
            update_headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.CURRENT_ORIGIN_URL,
                "Referer": f"{self.CURRENT_ORIGIN_URL}/"
            },
            data={"userShowId": self.user_id},
            model=RspLogin
        )

    def modify_token(self, number: int = 0):
        """
        模拟JS中
        token = btoa(atob(token)+"&startNumber="+number)
        的行为
        :param number: 固定从0开始，后面请求getArticleListxAuto接口后，才会更新number
        :return:
        """
        # 解码 base64 字符串
        decoded_token = base64.b64decode(self.origin_token).decode('utf-8')

        # 添加新的参数
        modified_string = decoded_token + "&startNumber=" + str(number)

        # 重新编码为 base64
        encoded_token = base64.b64encode(modified_string.encode('utf-8')).decode('utf-8')

        return encoded_token

    def get_entry_url(self) -> str:
        return "http://i3n0nzg2wcvnhzu6opsu.xoa8m3pb4.zhijianzzmm.cn/ttz/wechat/ttzScanCode?userShowId=5332"

    @property
    def origin_token(self):
        return self._cache.get(f"origin_token_{self.user_id}_{self.ident}", )

    @origin_token.setter
    def origin_token(self, value: str):
        self._cache[f"origin_token_{self.user_id}_{self.ident}"] = value

    @property
    def base_read_url(self) -> URL:
        return self._cache.get(f"base_read_url_{self.user_id}_{self.ident}", )

    @base_read_url.setter
    def base_read_url(self, value: URL):
        self._cache[f"base_read_url_{self.user_id}_{self.ident}"] = value

    @property
    def user_id(self):
        return self.account_config.userShowId

    @property
    def pwd(self):
        ret = self.account_config.pwd
        if ret is None:
            ret = self.config_data.pwd
        return ret if ret is not None else "6666"

    @property
    def is_set_pwd(self):
        return self._cache.get(f"is_set_pwd_{self.user_id}_{self.ident}", False)


if __name__ == '__main__':
    YMZV2()
