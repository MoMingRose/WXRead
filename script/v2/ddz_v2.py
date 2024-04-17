# -*- coding: utf-8 -*-
# ddz_v2.py created by MoMingLog on 17/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-17
【功能描述】
"""
import re

from config import load_ddz_config
from exception.common import RegExpError, APIChanged
from schema.ddz import DDZConfig, DDZAccount, RspQrCode
from script.common.base import WxReadTaskBase
from utils import hide_dynamic_middle, md5


class APIS:
    COMMON = "/index/mob"

    # API: 主页
    HOMEPAGE = f"{COMMON}/index.html?tt=1"
    # API: 阅读二维码
    READ_QRCODE = f"{COMMON}/get_read_qr.html"
    # API: 点赞看二维码
    LIKE_QRCODE = f"{COMMON}/get_zan_qr.html"


class DDZV2(WxReadTaskBase):
    # 当前脚本作者
    CURRENT_SCRIPT_AUTHOR = "MoMingLog"
    # 当前脚本版本
    CURRENT_SCRIPT_VERSION = "2.0.0"
    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-04-17"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-17"
    # 当前任务名称
    CURRENT_TASK_NAME = "点点赚"

    HOMEPAGE_CONTENT_COMPILE = re.compile(
        r"div.*?nickname.*?>(.*?)</div.*?userid.*?>(.*?)</div.*?(上级ID.*?)</div>.*?(可用积分.*?)<text.*?var\s*phone\s*=\s*['\"](\d+)['\"];?.*?var\s*pwd\s*=\s*['\"](.*?)['\"];?",
        re.S
    )
    # 提取二维码 API (包括：文章二维码、点赞看二维码)
    QR_CODE_COMPILE = re.compile(r"phone.*?layer.load.*?var\surl\s*=\s*['\"](.*?)['\"];?", re.S)

    def __init__(self, config_data: DDZConfig = load_ddz_config(), run_read_task: bool = True):
        self.run_read_task = run_read_task
        super().__init__(config_data, logger_name="点点赚")

    def init_fields(self, retry_count: int = 3):
        pass

    def run(self, name, *args, **kwargs):

        self.base_client.base_url = self.protocol + "://" + self.host

        self.base_client.cookies = self.cookie_dict

        homepage_html = self.__request_homepage()

        self.__parse_homepage(homepage_html)

        read_qr_model = self.__request_read_qr_url()
        self.logger.info(f"阅读{read_qr_model}")

        if read_qr_model.data:
            self.__request_read_qr_code(read_qr_model.data)

    def __request_read_qr_code(self, qr_code_api: str):
        return self.base_client.get(qr_code_api)

    def __request_like_qr_url(self) -> RspQrCode | dict:
        return self.request_for_json(
            "GET",
            APIS.LIKE_QRCODE,
            "获取点赞看二维码链接 base_client",
            client=self.base_client,
            model=RspQrCode
        )

    def __request_read_qr_url(self) -> RspQrCode | dict:
        return self.request_for_json(
            "GET",
            APIS.READ_QRCODE,
            "获取阅读二维码链接 base_client",
            client=self.base_client,
            model=RspQrCode
        )

    def __parse_homepage(self, homepage_html):
        if r := self.HOMEPAGE_CONTENT_COMPILE.search(homepage_html):
            if len(r.groups()) != 6:
                raise RegExpError(self.HOMEPAGE_CONTENT_COMPILE)

            self.phone = r.group(5)
            self.pwd = r.group(6)

            self.logger.info("\n".join([
                "【用户信息】",
                f"❄️>> 用户昵称: {r.group(1).strip()}",
                f"❄️>> {r.group(2).strip()}",
                f"❄️>> {r.group(3)}",
                f"❄️>> {r.group(4)}",
                f"❄️>> 手机号: {hide_dynamic_middle(self.phone)}(已自动隐藏部分内容)",
                f"❄️>> 密码: {hide_dynamic_middle(self.pwd)}(已自动隐藏部分内容)"
            ]))
        else:
            raise RegExpError(self.HOMEPAGE_CONTENT_COMPILE)

        if r := self.QR_CODE_COMPILE.findall(homepage_html):
            if len(r) != 2:
                raise RegExpError(self.QR_CODE_COMPILE)

            read_qr_api = r[0]
            like_qr_api = r[1]

            if "19a07dface972ecd96546da6cc5052c8" != md5(read_qr_api) or "cc47a0b8fb0666b6f973bc18adb8533f" != md5(
                    like_qr_api):
                raise APIChanged("获取二维码")

            APIS.READ_QRCODE = read_qr_api
            APIS.LIKE_QRCODE = like_qr_api
            self.logger.info("🟢 二维码API提取成功!")
        else:
            raise RegExpError(self.QR_CODE_COMPILE)

    def __request_homepage(self):
        return self.request_for_page(
            APIS.HOMEPAGE,
            "获取主页源代码",
            client=self.base_client
        )

    def get_entry_url(self) -> str:
        return "http://qqd0vlfcop-185334769.baihu.sbs/index/center/poster.html?pid=61552"

    @property
    def phone(self):
        return self._cache.get(f"phone_{self.ident}")

    @phone.setter
    def phone(self, value):
        self._cache[f"phone_{self.ident}"] = value

    @property
    def pwd(self):
        return self._cache.get(f"pwd_{self.ident}")

    @pwd.setter
    def pwd(self, value):
        self._cache[f"pwd_{self.ident}"] = value

    @property
    def protocol(self):
        ret = self.account_config.protocol
        if ret is None:
            ret = self.config_data.protocol
        return ret if ret is not None else "http"

    @property
    def host(self):
        ret = self.account_config.host
        if ret is None:
            ret = self.config_data.host
        return ret if ret is not None else "28917700289.sx.shuxiangby.cn"

    @property
    def account_config(self) -> DDZAccount:
        return super().account_config


if __name__ == '__main__':
    DDZV2()
