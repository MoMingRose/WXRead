# -*- coding: utf-8 -*-
# yryd.py created by MoMingLog on 3/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-03
【功能描述】
"""
from typing import Type, Dict

from pydantic import BaseModel, Field, create_model, HttpUrl

from schema.common import CommonPartConfig, CommonGlobalConfig


class CommonYRYDConfig(BaseModel):
    withdraw_type: str = Field(None, description="提现类型: wx 微信, ali 支付宝")


class YRYDAccount(CommonPartConfig, CommonYRYDConfig):
    """鱼儿阅读（局部配置）"""
    cookie: str | None = Field(None, description="用户cookie")


class BaseYRYDGlobalConfig(CommonGlobalConfig, CommonYRYDConfig):
    """鱼儿阅读（全局配置）"""
    biz_data: list | None = Field(None, description="检测文章的biz")


YRYDConfig: Type[BaseYRYDGlobalConfig] = create_model(
    'YRYDConfig',
    account_data=(Dict[str | int, YRYDAccount], {}),
    source=(str, "yryd.yaml"),
    __base__=BaseYRYDGlobalConfig
)


class RspReadUrl(BaseModel):
    """获取阅读链接的响应"""
    jump: str | None = Field(None, description="阅读链接")


class RspDoRead(BaseModel):
    """do_read响应"""
    error_msg: str | None = Field(None, description="错误信息")
    jkey: str | None = Field(None, description="阅读key")
    url: str | HttpUrl | None = Field(None, description="阅读链接")
