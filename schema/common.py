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
    read_delay: list | None = Field(None, description="阅读延迟时间（单位: 秒）")
    push_delay: list | None = Field(None, description="推送延迟时间（单位: 秒）")


class CommonConfig(BaseModel):
    """相同的全局和局部配置（任务和任务账号配置）"""
    init_colorama: bool = Field(True,                           description="是否初始化colorama，当此项为True青龙面板的颜色渲染会消失，这样或许可以避免不支持颜色显示的青龙面板出现乱码的现象")
    is_withdraw: bool | None = Field(None, description="是否进行提现操作")
    withdraw: float = Field(0, description="提现金额（单位: 元），表示只有大于等于这个数才可以提现")
    aliAccount: str | None = Field(None, description="支付宝账号，默认为空")
    aliName: str | None = Field(None, description="支付宝账号姓名，默认为空")
    ua: str | None = Field(None, description="用户浏览器标识")
    delay: CommonDelayConfig = Field(None, description="阅读延迟时间（单位: 秒）")
    wait_next_read: bool | None = Field(None, description="是否自动等待下批阅读")
    custom_detected_count: list | None = Field(None, description="达到指定阅读篇数走推送通道")
    push_types: list | None = Field(None, description="推送通道类型 1: WxPusher 2: WxBusinessPusher")
    # WxPusher
    appToken: str | None = Field(None, description="WxPusher推送通知的appToken")
    topicIds: str | list | None = Field(None, description="WxPusher推送通知的topicIds")
    # WxBusinessPusher Robot
    use_robot: bool | None = Field(None, description="是否使用企业微信机器人推送")
    is_push_markdown: bool | None = Field(None, description="是否推送MarkDown格式")
    webhook_url: str | None = Field(None, description="企业微信机器人推送通知的webhook_url")
    # WxBusinessPusher
    corp_id: str | None = Field(None, description="企业微信推送通知的企业ID")
    corp_secret: str | None = Field(None, description="企业微信推送通知的应用密钥")
    agent_id: int | None = Field(None, description="企业微信推送通知的应用ID")


class CommonPartConfig(CommonConfig):
    """相同的局部配置（账号配置）"""
    uid: str | None = Field(None, description="账号ID")


class CommonGlobalConfig(CommonConfig):
    """相同的全局配置（任务配置）"""
    debug: bool = Field(False, description="是否开启调试模式")
    strategy: int = Field(
        2,
        description="配置全局优先策略（仅限全局配置，不包括账号局部配置） 1: 全局优先 2: 任务配置优先）"
    )
    max_thread_count: int = Field(1, description="线程池中的最大线程数")
    is_log_response: bool | None = Field(None, description="是否打印响应日志")


class ArticleInfo(BaseModel):
    """文章信息"""
    article_url: str
    article_biz: str
    article_title: str
    article_author: str
    article_desc: str

    def __str__(self):
        msg = []
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
