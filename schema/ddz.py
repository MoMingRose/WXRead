# -*- coding: utf-8 -*-
# ddz.py created by MoMingLog on 17/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-17
【功能描述】
"""
from typing import Type, Dict

from pydantic import create_model, BaseModel, Field

from schema.common import CommonPartConfig, CommonGlobalConfig
from utils import extract_urls


class CommonDDZConfig(BaseModel):
    """点点赚全局和局部的相同配置"""
    withdraw_type: str = Field(None, description="提现类型: wx 微信, ali 支付宝")
    protocol: str | None = Field(None, description="协议")


class DDZAccount(CommonPartConfig, CommonDDZConfig):
    """点点赚（局部配置）"""
    host: str
    cookie: str


class BaseDDZGlobalConfig(CommonGlobalConfig, CommonDDZConfig):
    """点点赚（全局配置）"""
    pass


DDZConfig: Type[BaseDDZGlobalConfig] = create_model(
    "DDZConfig",
    account_data=(Dict[str | int, DDZAccount], {}),
    source=(str, "ddz.yaml"),
    __base__=BaseDDZGlobalConfig
)


class CommonRsp(BaseModel):
    code: int
    msg: str


class RspQrCode(CommonRsp):
    data: str | None = Field(None, description="二维码路径")
    web_url: str | None = Field(None, description="包含跳转链接和相关说明")

    def jump_url(self):
        if self.web_url:
            return extract_urls(self.web_url)

    def __str__(self):
        jump_url = self.jump_url()
        if jump_url is None:
            jump_url = "未提取成功跳转链接!"
        return "\n".join([
            "二维码信息",
            f"❄️>> 二维码路径： {self.data}",
            f"❄️>> 跳转链接： {jump_url}",
            f"❄️>> 官方描述： {self.web_url.replace(jump_url, '').strip()}"
        ])

    def __repr__(self):
        return self.__str__()
