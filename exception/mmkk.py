# -*- coding: utf-8 -*-
# mmkk.py created by MoMingLog on 28/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-28
【功能描述】
"""


class ReadValid(Exception):
    """当前阅读暂时无效，请稍候再来"""

    def __init__(self, msg):
        super().__init__(f"获取文章阅读链接失败，原因：{msg}")


class FailedFetch(Exception):
    """提取失败"""

    def __init__(self, pre_str: str, message: str = "请通知作者更新脚本"):
        super().__init__(f"{pre_str}, {message}")


class FailedFetchUK(FailedFetch):
    """提取UK失败"""

    # 设置默认的错误消息
    def __init__(self):
        super().__init__("提取用户UK失败")


class FailedFetchArticleJSUrl(FailedFetch):
    def __init__(self):
        super().__init__("提取article.js链接失败")


class FailedFetchArticleJSVersion(FailedFetch):
    def __init__(self):
        super().__init__("提取article.js版本失败")


class FailedFetchReadUrl(FailedFetch):
    def __init__(self, e):
        super().__init__(f"提取阅读链接失败, 原因: {e}")


class ArticleJSUpdated(Exception):
    """article.js已更新"""

    def __init__(self, latest_version: str):
        super().__init__(f"官方接口更新至【v{latest_version}】版本，请通知作者更新脚本!")


class CodeChanged(Exception):
    """代码更新"""

    def __init__(self):
        super().__init__("官方代码发生变化，请通知作者更新脚本!")


class PauseReading(Exception):
    def __init__(self, message):
        super().__init__(f"暂停阅读: {message}")


class ReachedLimit(Exception):
    pass


class StopRun(Exception):
    def __init__(self, message):
        super().__init__(f"🈲 {message}，脚本停止运行, 请快去通知小伙伴们!")


class WithDrawFailed(Exception):
    pass
