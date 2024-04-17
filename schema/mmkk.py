# -*- coding: utf-8 -*-
# mmkk.py created by MoMingLog on 28/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-28
【功能描述】
"""
from typing import Dict, Type

from pydantic import BaseModel, Field, create_model

from schema.common import CommonGlobalConfig, CommonPartConfig

__all__ = [
    "MMKKConfig",
    "WorkInfoRsp",
    "UserRsp",
    "WTMPDomainRsp",
    "MKWenZhangRsp",
    "AddGoldsRsp",
]


class MMKKAccount(CommonPartConfig):
    """账号配置（局部配置）"""
    cookie: str


class BaseMMKKGlobalConfig(CommonGlobalConfig):
    """猫猫看看阅读配置（全局配置）"""
    biz_data: list


# 通过 create_model() 方法创建动态键模型
MMKKConfig: Type[BaseMMKKGlobalConfig] = create_model(
    'MMKKConfig',
    account_data=(Dict[str | int, MMKKAccount], {}),
    source=(str, "mmkk.yaml"),
    __base__=BaseMMKKGlobalConfig
)


class CommonRsp(BaseModel):
    errcode: int
    msg: str


class WorkInfoData(BaseModel):
    dayreads: int = Field(..., description="今天阅读的文章篇数")
    gold: int = Field(..., description="今天获得的金币数")
    remain_gold: str = Field(..., description="当前的金币数量")
    remain: float = Field(..., description="当前现金余额(元)")


class WorkInfoRsp(CommonRsp):
    data: WorkInfoData | None = Field(None, description="今日统计信息")

    def __str__(self):
        # return f"【今日统计信息】\n> 阅读文章数: {self.data.dayreads}\n> 获得金币数: {self.data.gold}\n> 当前金币数: {self.data.remain_gold}\n> 当前余额(元): {self.data.remain}"
        if self.data:
            return "\n".join([
                f"【今日统计信息】",
                f"❄️>> 阅读文章数: {self.data.dayreads}",
                f"❄️>> 获得金币数: {self.data.gold}",
                f"❄️>> 当前金币数: {self.data.remain_gold}",
                f"❄️>> 当前余额(元): {self.data.remain}"
            ])
        return self.msg

    def __repr__(self):
        return self.__str__()


class UserData(BaseModel):
    userid: str = Field(..., description="用户ID")
    addtime: str | int = Field(..., description="注册时间")
    adddate: str = Field(..., description="注册日期")
    partner_id: str = Field(..., description="")
    pid: str = Field(..., description="")
    note: str = Field(..., description="备注")


class UserRsp(CommonRsp):
    data: UserData | None = Field(None, description="账号注册信息")

    def __str__(self):
        # return f"【账号注册信息】\n> 账号唯一ID: {self.data.userid}\n> 注册时间: {self.data.addtime}\n> 注册日期: {self.data.adddate}"
        if self.data:
            return "\n".join([
                f"【账号注册信息】",
                f"❄️>> 账号唯一ID: {self.data.userid}",
                f"❄️>> 注册时间: {self.data.addtime}",
                f"❄️>> 注册日期: {self.data.adddate}"
            ])

    def __repr__(self):
        return self.__str__()


class WTMPDomainData(BaseModel):
    domain: str = Field(..., description="域名链接（返回的是完整的链接）")


class WTMPDomainRsp(CommonRsp):
    data: WTMPDomainData | None = Field(None, description="阅读二维码链接")

    def __str__(self):
        # return f"【阅读二维码链接】\n> 阅读二维码链接: {self.data.domain}"
        return "\n".join([
            f"【阅读二维码链接】",
            f"❄️>> 阅读二维码链接: {self.data.domain}"
        ])

    def __repr__(self):
        return self.__str__()


class MKWenZhangData(BaseModel):
    link: str | None = Field(None, description="阅读文章链接")
    type: str | None = Field(None, description="类型：目前已知的有read")
    type2: str | None = Field(None,
                              description="类型: 目前已知的有read，有的响应体中没有这个参数，故设置默认值为空字符串")


class MKWenZhangRsp(CommonRsp):
    data: MKWenZhangData | None = Field(None, description="阅读文章链接")

    def __str__(self):
        return f"【文章链接】\n❄️>> {self.data.link}"

    def __repr__(self):
        return self.__str__()


class AddGoldsData(BaseModel):
    gold: int = Field(..., description="获得金币数")
    day_read: int = Field(..., description="今日阅读文章数")
    day_gold: int = Field(..., description="今日获得金币数")
    last_gold: int = Field(..., description="当前账户金币数")
    remain_read: int = Field(..., description="今日剩余阅读文章数")


class AddGoldsRsp(CommonRsp):
    data: AddGoldsData | None = Field(None, description="阅读统计信息")

    def __str__(self):
        # return f"【阅读信息统计】\n> 获得金币数: {self.data.gold}\n> 今日阅读文章数: {self.data.day_read}\n> 今日获得金币数: {self.data.day_gold}\n> 当前账户金币数: {self.data.last_gold}\n> 今日剩余阅读文章数: {self.data.remain_read}"
        return "\n".join([
            f"【阅读信息统计】",
            f"❄️>> 获得金币数: {self.data.gold}",
            f"❄️>> 今日阅读文章数: {self.data.day_read}",
            f"❄️>> 今日获得金币数: {self.data.day_gold}",
            f"❄️>> 当前账户金币数: {self.data.last_gold}",
            f"❄️>> 今日剩余阅读文章数: {self.data.remain_read}"
        ])

    def __repr__(self):
        return self.__str__()
