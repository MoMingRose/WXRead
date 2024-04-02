# -*- coding: utf-8 -*-
# common.py created by MoMingLog on 30/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-30
【功能描述】
"""

from pydantic import BaseModel, Field


class CommonDelayConfig(BaseModel):
    """延迟配置"""
    read_delay: list = Field([10, 20], description="阅读延迟时间（单位: 秒）")
    push_delay: list = Field([19], description="推送延迟时间（单位: 秒）")


class CommonConfig(BaseModel):
    """相同的全局和局部配置（任务和任务账号配置）"""
    withdraw: float = Field(0, description="提现金额（单位: 元），表示只有大于等于这个数才可以提现")
    aliAccount: str | None = Field(None, description="支付宝账号，默认为空")
    aliName: str | None = Field(None, description="支付宝账号姓名，默认为空")
    ua: str | None = Field(None, description="用户浏览器标识")
    appToken: str | None = Field(None, description="WxPusher推送通知的appToken")
    delay: CommonDelayConfig = Field(CommonDelayConfig(), description="阅读延迟时间（单位: 秒）")
    wait_next_read: bool | None = Field(None, description="是否自动等待下批阅读")


class CommonPartConfig(CommonConfig):
    """相同的局部配置（账号配置）"""
    uid: str


class CommonGlobalConfig(CommonConfig):
    """相同的全局配置（任务配置）"""
    debug: bool = Field(False, description="是否开启调试模式")
    strategy: int = Field(
        2,
        description="配置全局优先策略（仅限全局配置，不包括账号局部配置） 1: 全局优先 2: 任务配置优先）"
    )
    max_thread_count: int = Field(1, description="线程池中的最大线程数")
