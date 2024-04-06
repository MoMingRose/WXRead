# -*- coding: utf-8 -*-
# mmkk_v2.py created by MoMingLog on 1/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-01
【功能描述】
"""
import re

from config import load_mmkk_config
from schema.mmkk import MMKKConfig
from script.common.base import WxReadTaskBase
from utils import EntryUrl


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


class MMKKV2(WxReadTaskBase):
    CURRENT_SCRIPT_VERSION = "2.0.0"
    CURRENT_TASK_NAME = "可乐阅读"

    # 当前脚本创建时间
    CURRENT_SCRIPT_CREATED = "2024-03-28"
    # 当前脚本更新时间
    CURRENT_SCRIPT_UPDATED = "2024-04-02"
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
        r"^https?://mp.weixin.qq.com/s\?__biz=[^&]*&mid=[^&]*&idx=\d*&(?!.*?chksm).*?&scene=\d*#wechat_redirect$")
    # 提取阅读文章链接的__biz值
    ARTICLE_LINK_BIZ_COMPILE = re.compile(r"__biz=(.*?)&")

    def __init__(self, config_data: MMKKConfig = load_mmkk_config(), run_read_task: bool = True):
        self.run_read_task = run_read_task
        super().__init__(config_data, logger_name="😸阅读")

    def get_entry_url(self):
        return EntryUrl.get_mmkk_entry_url()

    def init_fields(self):
        pass

    def run(self, name):
        pass


if __name__ == '__main__':
    MMKKV2()
