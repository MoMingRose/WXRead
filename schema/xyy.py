# -*- coding: utf-8 -*-
# xyy.py created by MoMingLog on 8/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-08
【功能描述】
"""
from typing import Type, Dict

from pydantic import create_model, BaseModel, Field

from schema.common import CommonPartConfig, CommonGlobalConfig

class CommonYRYDConfig(BaseModel):
    withdraw_type: str = Field(None, description="提现类型: wx 微信, ali 支付宝")


class XYYAccount(CommonPartConfig, CommonYRYDConfig):
    """账号配置（局部配置）"""
    cookie: str


class BaseXYYGlobalConfig(CommonGlobalConfig, CommonYRYDConfig):
    """小阅阅 阅读配置（全局配置）"""
    biz_data: list | None = Field(None, description="检测文章的biz")


# 通过 create_model() 方法创建动态键模型
XYYConfig: Type[BaseXYYGlobalConfig] = create_model(
    'XYYConfig',
    account_data=(Dict[str | int, XYYAccount], {}),
    source=(str, "xyy.yaml"),
    __base__=BaseXYYGlobalConfig
)


class RspCommon(BaseModel):
    errcode: int
    msg: str | None = Field(None, description="响应信息")


class GoldData(BaseModel):
    """金币数据"""
    gold: str | None = Field(None, description="此次阅读获取的金币数")
    last_gold: str | None = Field(None, description="上次金币数")
    day_read: str | None = Field(None, description="当天阅读数")
    day_gold: str | None = Field(None, description="当天金币数")
    remain_read: int | str | None = Field(None, description="剩余阅读数")

    def __str__(self):
        return "\n".join([
            "【阅读收入情况】",
            f"> 剩余金币: {self.last_gold}",
            f"> 今日阅读: {self.day_read}",
            f"> 今日获得: {self.day_gold}",
            f"> 剩余篇数: {self.remain_read}"
        ])

    def __repr__(self):
        return self.__str__()

    def get_read_result(self):
        return f"获得金币: {self.gold}, 今日共得: {self.day_gold}, 当前余额: {self.last_gold}"


class Gold(RspCommon):
    """金币数据"""
    data: GoldData | None = Field(None, description="金币数据")

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()

    def get_read_result(self):
        return self.data.get_read_result()


class WTMPDomainData(BaseModel):
    """跳转链接数据"""
    domain: str | None = Field(None, description="跳转链接")

    def __str__(self):
        return f"阅读跳转链接: {self.domain}"

    def __repr__(self):
        return self.__str__()


class WTMPDomain(RspCommon):
    data: WTMPDomainData | None = Field(None, description="跳转链接数据")

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


class ArticleUrlData(BaseModel):
    link: str | None = Field(None, description="文章链接")
    type: str | None = Field(None, description="类型")
    a: str | None = Field(None, description="未知")

    def __str__(self):
        return f"文章链接: {self.link}"

    def __repr__(self):
        return self.__str__()


class ArticleUrl(RspCommon):
    data: ArticleUrlData | None = Field(None, description="文章链接数据")

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()
