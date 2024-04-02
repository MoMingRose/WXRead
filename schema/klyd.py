# -*- coding: utf-8 -*-
# klyd.py created by MoMingLog on 30/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-30
【功能描述】
"""
import re
from typing import Type, Dict

from httpx import URL
from pydantic import BaseModel, create_model, Field, field_validator, HttpUrl

from schema.common import CommonGlobalConfig, CommonPartConfig

__all__ = [
    "KLYDAccount",
    "KLYDConfig",
    "RspRecommend"
]

from utils.logger_utils import NestedLogColors


class CommonKLYDConfig(BaseModel):
    """可乐阅读全局和局部的相同配置"""
    withdraw_type: str = Field(None, description="提现类型: wx 微信, ali 支付宝")


class KLYDAccount(CommonPartConfig, CommonKLYDConfig):
    """账号配置（局部配置）"""
    cookie: str


class BaseKLYDGlobalConfig(CommonGlobalConfig, CommonKLYDConfig):
    """可乐阅读配置（全局配置）"""
    pass


KLYDConfig: Type[BaseModel] = create_model(
    'KLYDConfig',
    account_data=(Dict[str | int, KLYDAccount], {}),
    source=(str, "klyd.yaml"),
    __base__=BaseKLYDGlobalConfig
)


class RspRecommendUser(BaseModel):
    """推荐 响应数据 User"""
    username: str = Field(..., description="用户名")
    upuid: str = Field(..., description="上级用户uid")
    uid: str = Field(..., description="当前用户uid")
    regtime: str = Field(..., description="注册日期")
    score: float = Field(..., description="当前积分")
    rebate_count_show: bool
    rebate_count: str
    new_read_count: str = Field(..., description="新阅读数")

    def __str__(self):
        msg_list = [
            f"{NestedLogColors.black('【用户信息】')}",
            f"> 用户昵称：{self.username}",
            f"> 上级用户：{self.upuid}",
            f"> 当前用户：{self.uid}",
            f"> 注册日期：{self.regtime}",
            f"> 当前币数：{int(self.score * 100)}"
        ]
        return "\n".join(msg_list)

    def __repr__(self):
        self.__str__()


class RspRecommendReadCfg(BaseModel):
    """推荐 响应数据 ReadCfg"""
    check_score: float = Field(..., description="检查积分")
    user_score: float = Field(..., description="用户积分")


class RspRecommendInfoView(BaseModel):
    """推荐 响应数据 InfoView"""
    num: float
    score: float
    rest: float
    status: int = Field(..., description='''
        当前阅读状态，目前已知：
        当rest = 0 且 status = 1 时：等待下一批
        当rest = 4 且 status = 1 时: 等待开始阅读
        当rest = 1 且 status = 3 时：不确定此状态
        
        rest暂时不知道是什么，但就目前已知情况，可简略推测
        当 status = 1 时，表示此用户处于可正常阅读状态
    ''')
    msg: str = Field(None, description="当前阅读状态")

    def __str__(self):
        msg_list = [
            f"{NestedLogColors.black('【阅读信息】')}",
            f"> 今日阅读篇数: {self.num}",
            f"> 今日阅读奖励: {self.score * 100}",
            f"> 转换成现金为: {self.score / 100}",
            f"{NestedLogColors.black('【阅读状态】')}",
        ]
        if self.status == 1:
            msg_list.append(f"> 🟢 正常阅读")
        elif self.status == 4:
            msg_list.append(f"> 🔴 {NestedLogColors.red('不可阅读')}")
        elif self.status == 3 and self.rest == 1 and self.num == 0 and self.score == 0:
            msg_list.append(f"> 🟡 {NestedLogColors.yellow('等待阅读')}")
        else:
            msg_list.append(f"> ⚪️ {NestedLogColors.white(f'未记录此状态码{self.status}（可通知作者添加）')}")

        if self.msg:
            msg_list.append(f"> {self.msg}")

        return "\n".join(msg_list)


class RspRecommendData(BaseModel):
    """推荐 响应数据"""
    user: RspRecommendUser
    readCfg: RspRecommendReadCfg
    infoView: RspRecommendInfoView
    tips: str


class RspRecommend(BaseModel):
    """推荐 响应"""
    code: int
    data: RspRecommendData


class RspReadUrl(BaseModel):
    """获取阅读链接 响应"""
    link: str | HttpUrl = Field(..., alias="jump", description="阅读链接")

    @field_validator("link")
    def check_link(cls, v) -> URL:
        if not isinstance(v, URL):
            v = URL(v)
        return v


# 检测有效阅读链接
ARTICLE_LINK_VALID_COMPILE = re.compile(
    r"^https?://mp.weixin.qq.com/s\?__biz=[^&]*&mid=[^&]*&idx=\d*&(?!.*?chksm).*?&scene=\d*#wechat_redirect$")


class RspDoRead(BaseModel):
    """完成阅读检查 响应"""
    check_finish: int | None = Field(None,
                                     description="是否完成阅读，目前了解到的是 1：阅读成功。此外如果这个字段不存在，则表示不处于检测阶段")
    success_msg: str | None = Field(None, description="阅读完成后的提示信息")
    jkey: str | None = Field(None, description="阅读链接的jkey，当检测未通过时，这个字段不会返回")
    url: str | None = Field(None, description="阅读链接，有一次返回的是None")
    msg: str | None = Field(None, description="这个字段目前已知当阅读达到上限时出现")

    @property
    def is_next_check(self) -> bool:
        """
        当前返回的链接是否是检测文章
        :return: True: 是检测文章 False: 不是检测文章
        """
        if self.check_finish is None and self.success_msg is None:
            return True
        #
        return ARTICLE_LINK_VALID_COMPILE.match(self.url) is None

    @property
    def is_pass_failed(self) -> bool:
        """
        是否检测失败

        例如： {'check_finish': 1, 'success_msg': '检测未通过', 'url': 'close'}
        """
        if self.success_msg == "检测未通过" and self.url == "close":
            return True
        return False

    @property
    def is_check_success(self) -> bool:
        """上一次阅读检测文章链接是否检测成功"""
        if self.check_finish == 1 and self.success_msg == "阅读成功":
            return True
        return False

    @property
    def ret_count(self):
        """
        响应数据中的键值对个数

        经过粗略的观察，一般来说：
        返回2个，分两种情况，需要检测、检测失败
            - 需要检测
                {
                  "jkey": "MDAwMDAwMDAwM......",
                  "url": "https://mp.weixin.qq.com/s?__biz=Mzg2OTYyNDY1OQ==&mid=2247649861&idx=1&sn=f0216ebeec1edb6c30ba1ab54a6fec7d&scene=0#wechat_redirect"
                }
            - 检测失败
                {
                  "success_msg": "检测未通过",
                  "url": "close"
                }
        返回3个，分两种情况：检测失败、已通过检测并获得了奖励
            - 检测失败：{'check_finish': 1, 'success_msg': '检测未通过', 'url': 'close'}
            - 已通过检测并获得了奖励：
                {
                  "success_msg": "阅读成功，获得110币",
                  "jkey": "MDAwMDAw........",
                  "url": "https://mp.weixin.qq.com/s?__biz=Mzg3Nzg4OTA4Ng==&mid=2247526971&idx=1&sn=2edf88cefcf3e30f988fab3f1f4f86de&scene=0#wechat_redirect"
                }
        返回4个，应该表示正处于检测中，可以通过其中的 success_msg 获取阅读情况，目前一致的阅读情况有：阅读成功
            {
              "check_finish": 1,
              "success_msg": "阅读成功",
              "jkey": "MDAwMDAwMD.........",
              "url": "https://mp.weixin.qq.com/s?__biz=MjM5NDY4MTAwMA==&mid=2656010192&idx=1&sn=2f19bcd42822dff884fd1b3091732cbc&scene=0#wechat_redirect"
            }
        :return:
        """
        count = 0
        if self.check_finish is not None:
            count += 1
        if self.success_msg is not None:
            count += 1
        if self.jkey is not None:
            count += 1
        if self.url is not None:
            count += 1
        if self.msg is not None:
            count += 1
        return count


class ArticleInfo(BaseModel):
    """文章信息"""
    article_url: str
    article_biz: str
    article_title: str
    article_author: str
    article_desc: str

    def __str__(self):
        msg = ["【文章信息】"]
        if self.article_biz:
            msg.append(f"> 文章BIZ: {self.article_biz}")
        if self.article_url:
            msg.append(f"> 文章链接: {self.article_url}")
        if self.article_title:
            msg.append(f"> 文章标题: {self.article_title}")
        if self.article_author:
            msg.append(f"> 文章作者: {self.article_author}")
        if self.article_desc:
            msg.append(f"> 文章描述: {self.article_desc}")
        return "\n".join(msg)

    def __repr__(self):
        return self.__str__()


class RspWithdrawalUser(BaseModel):
    """提款用户信息"""
    uid: str
    username: str
    upuid: str | int | None = Field(None, description="上级ID")
    score: float
    weixinname: str
    u_ali_account: str | None = Field(None, description="支付宝账号")
    u_ali_real_name: str | None = Field(None, description="支付宝真实姓名")
    regtime: str
    super_user: float

    @property
    def amount(self):
        return int(self.score)

    def __str__(self):
        msg_list = [
            f"{NestedLogColors.black('【提款用户信息】')}",
            f"> 用户ID: {self.uid}",
            f"> 用户名: {self.username}",
            f"> 上级ID: {self.upuid}",
            f"> 当前余额: {int(self.score) * 100}",
            f"> 微信昵称: {self.weixinname}",
        ]
        if self.u_ali_account:
            msg_list.append(f"> 支付宝账号: {self.u_ali_account}")
        if self.u_ali_real_name:
            msg_list.append(f"> 支付宝真实姓名: {self.u_ali_real_name}")
        if self.regtime:
            msg_list.append(f"> 注册时间: {self.regtime}")
        return "\n".join(msg_list)

    def __repr__(self):
        return self.__str__()


class RspWithdrawalData(BaseModel):
    """提款信息"""
    user: RspWithdrawalUser
    kefuWx: str

    def __str__(self):
        return self.user.__str__()

    def __repr__(self):
        return self.__str__()


class RspWithdrawal(BaseModel):
    code: int
    data: RspWithdrawalData

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()
