# -*- coding: utf-8 -*-
# mmkk.py created by MoMingLog on 28/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-28
【功能描述】
"""
from typing import Dict, Type

from pydantic import BaseModel, Field, create_model

__all__ = [
    "WorkInfo",
    "User",
    "WTMPDomain",
    "MKWenZhang",
    "AddGolds",
    "MMKKConfig",
]


class DelayConfig(BaseModel):
    read_delay: list
    push_delay: list


class CommonConfig(BaseModel):
    """全局配置和局部配置的共同部分"""
    withdraw: float = Field(0, description="提现金额（单位: 元），表示只有大于等于这个数才可以提现")
    aliAccount: str = Field("", description="支付宝账号，默认为空")
    aliName: str = Field("", description="支付宝账号姓名，默认为空")
    delay: DelayConfig | None = Field(None, description="阅读延迟时间（单位: 秒）")
    ua: str | None = Field(None, description="用户浏览器标识")


class MMKKAccount(CommonConfig):
    """账号配置（局部配置）"""
    cookie: str
    uid: str


class BaseMMKKConfig(CommonConfig):
    """猫猫看看阅读配置（全局配置）"""
    biz_data: list
    delay: DelayConfig
    appToken: str = Field(..., description="WxPusher推送通知的appToken")
    debug: bool = Field(False, description="是否开启调试模式")
    # source: str = Field("mmkk.yaml", description="配置来源")


# 通过 create_model() 方法创建动态键模型
MMKKConfig: Type[BaseModel] = create_model(
    'MMKKConfig',
    account_data=(Dict[str | int, MMKKAccount], {}),
    source=(str, "mmkk.yaml"),
    __base__=BaseMMKKConfig
)


class Common(BaseModel):
    errcode: int
    msg: str


class WorkInfoData(BaseModel):
    dayreads: int = Field(..., description="今天阅读的文章篇数")
    gold: int = Field(..., description="今天获得的金币数")
    remain_gold: str = Field(..., description="当前的金币数量")
    remain: float = Field(..., description="当前现金余额(元)")


class WorkInfo(Common):
    data: WorkInfoData

    def __str__(self):
        return f"【今日统计信息】\n> 阅读文章数: {self.data.dayreads}\n> 获得金币数: {self.data.gold}\n> 当前金币数: {self.data.remain_gold}\n> 当前余额(元): {self.data.remain}"

    def __repr__(self):
        return self.__str__()


class UserData(BaseModel):
    userid: str = Field(..., description="用户ID")
    addtime: str | int = Field(..., description="注册时间")
    adddate: str = Field(..., description="注册日期")
    partner_id: str = Field(..., description="")
    pid: str = Field(..., description="")
    note: str = Field(..., description="备注")


class User(Common):
    data: UserData

    def __str__(self):
        return f"【账号注册信息】\n> 账号唯一ID: {self.data.userid}\n> 注册时间: {self.data.addtime}\n> 注册日期: {self.data.adddate}"

    def __repr__(self):
        return self.__str__()


class WTMPDomainData(BaseModel):
    domain: str = Field(..., description="域名链接（返回的是完整的链接）")


class WTMPDomain(Common):
    data: WTMPDomainData

    def __str__(self):
        return f"【阅读二维码链接】\n> 阅读二维码链接: {self.data.domain}"

    def __repr__(self):
        return self.__str__()


class MKWenZhangData(BaseModel):
    link: str = Field(..., description="阅读文章链接")
    type: str = Field(..., description="类型：目前已知的有read")
    type2: str = Field("", description="类型: 目前已知的有read，有的响应体中没有这个参数，故设置默认值为空字符串")


class MKWenZhang(Common):
    data: MKWenZhangData

    def __str__(self):
        return f"【文章链接】\n > {self.data.link}"

    def __repr__(self):
        return self.__str__()


class AddGoldsData(BaseModel):
    gold: int = Field(..., description="获得金币数")
    day_read: int = Field(..., description="今日阅读文章数")
    day_gold: int = Field(..., description="今日获得金币数")
    last_gold: int = Field(..., description="当前账户金币数")
    remain_read: int = Field(..., description="今日剩余阅读文章数")


class AddGolds(Common):
    data: AddGoldsData

    def __str__(self):
        return f"【阅读信息统计】\n> 获得金币数: {self.data.gold}\n> 今日阅读文章数: {self.data.day_read}\n> 今日获得金币数: {self.data.day_gold}\n> 当前账户金币数: {self.data.last_gold}\n> 今日剩余阅读文章数: {self.data.remain_read}"

    def __repr__(self):
        return self.__str__()
