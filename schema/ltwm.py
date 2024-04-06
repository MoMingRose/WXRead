# -*- coding: utf-8 -*-
# ltwm.py created by MoMingLog on 4/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-04
【功能描述】
"""
from typing import Type, Dict, List

from pydantic import create_model, BaseModel, Field

from schema.common import CommonPartConfig, CommonGlobalConfig
from utils import is_date_after_today


class LTWMAccount(CommonPartConfig):
    """力天微盟（局部配置）"""
    authorization: str


class BaseLTWMGlobalConfig(CommonGlobalConfig):
    """力天微盟（全局配置）"""
    pass


LTWMConfig: Type[BaseLTWMGlobalConfig] = create_model(
    "LTWMConfig",
    account_data=(Dict[str | int, LTWMAccount], {}),
    source=(str, "ltwm.yaml"),
    __base__=BaseLTWMGlobalConfig
)


class CommonRsp(BaseModel):
    code: int
    businessCode: str
    message: str | None
    remark: str | None


class UserPointInfoData(BaseModel):
    """用户积分信息"""
    balance: int
    totalIncome: int
    withdrawAmount: float

    def __str__(self):
        return "\n".join([
            f"【用户积分信息】",
            f"> 可用积分: {self.balance} 积分",
            f"> 总 收 入: {self.totalIncome} 积分",
            f"> 已 兑 换: {self.withdrawAmount} 元"
        ])

    def __repr__(self):
        return self.__str__()


class UserPointInfo(CommonRsp):
    data: UserPointInfoData | None

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


class TaskListDataItem(BaseModel):
    """
    参考数据如下：
      "id": 1,
      "name": "文章阅读推荐",
      "code": 200,
      "taskKey": "209",
      "taskTag": "每日任务，多劳多得",
      "label": "单轮上限20篇，完成阅读后积分秒到账",
      "icon": "https://litianwm.oss-cn-hangzhou.aliyuncs.com/act/wx_article_read_xxhdpi.png?2",
      "data": "{\"cycleCount\":10,\"cycleMinute\":60,\"endHour\":20,\"startHour\":9}",
      "status": 2,
      "sortIndex": 1,
      "remark": "280积分/轮",
      "linkUrl": None,
      "taskRemainTime": 0
    """
    id: int
    name: str
    code: int
    taskKey: str | None
    taskTag: str
    label: str
    icon: str
    data: str | None
    status: int
    sortIndex: int
    remark: str
    linkUrl: None | str
    taskRemainTime: int | None


class TaskList(CommonRsp):
    """获取用户任务列表响应体"""
    data: List[TaskListDataItem] | None


class ReaderDomain(CommonRsp):
    """获取阅读链接响应体"""
    data: str | None


class GetTokenByWxKey(CommonRsp):
    """获取token"""
    data: str | None


class ArticleUrlData(BaseModel):
    articleUrl: str | None = Field(..., description="下一篇文章的访问地址")
    taskKey: int = Field(..., description="任务key，目前作用不详")
    readKey: str = Field(..., description="下一篇阅读完成请求体中的内容数据")
    readSecond: int = Field(..., description="阅读的秒数")
    articleNum: int = Field(..., description="当前阅读的篇数")
    participateUserNum: int = Field(..., description="参与此任务的用户编号")

    def __str__(self):
        msg_list = [
            f"【响应数据如下】",
            f"> 用户编号: {self.participateUserNum}",
            f"> 下篇链接: {self.articleUrl}",
            f"> taskKey: {self.taskKey}",
            f"> readKey: {self.readKey}",
        ]
        if self.readSecond > 0:
            msg_list.append(f"> 上篇阅读: {self.readSecond}秒")

        msg_list.append(f"> 已阅篇数: {self.articleNum}篇")
        return "\n".join(msg_list)

    def __repr__(self):
        return self.__str__()


class ArticleUrl(CommonRsp):
    """获取文章地址响应体"""
    data: ArticleUrlData | None

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


class CompleteRead(CommonRsp):
    """阅读上报响应"""
    data: ArticleUrlData | None

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


class SignItem(BaseModel):
    date: str
    signed: bool
    integral: int

    def __str__(self):
        msg_list = [f"> 日期: {self.date}"]
        if self.signed:
            msg_list.append(f"> 状态：✅️ 已签")
            msg_list.append(f"> 已获积分: {self.integral}")
        else:
            if is_date_after_today(self.date):
                msg_list.append(f"> 状态: 🔶 待签")
                msg_list.append(f"> 待领积分: {self.integral}")
            else:
                msg_list.append(f"> 状态: ❌️ 漏签")
                msg_list.append(f"> 遗憾失去: {self.integral}")
        return "\n".join(msg_list)

    def __repr__(self):
        return self.__str__()


class SignData(BaseModel):
    signItemList: List[SignItem]
    todayCanSign: bool = Field(..., description="今天是否可以签到")
    todaySigned: bool = Field(..., description="今天是否已经签到")
    currentIntegral: int = Field(..., description="当前签到应获得积分")
    nextIntegral: int = Field(..., description="下次签到应获得积分")

    def __str__(self):
        if self.todaySigned:
            return f"> 🟢 今日已签到! 获得{self.currentIntegral}积分，明日签到将获得{self.nextIntegral}积分"
        elif not self.todayCanSign:
            return "当前还不允许签到，可能未满足签到要求!"

    def __repr__(self):
        return self.__str__()

    def print_week_sign_status(self):
        for item in self.signItemList:
            print(item)
            print()


class Sign(CommonRsp):
    """签到任务"""
    data: SignData | None


class BalanceWithdrawData(BaseModel):
    exchangeBefore: int
    balance: int
    withdrawIntegral: int
    exchangeMoney: int
    progress: int | None
    minIntegralLimit: int

    def __str__(self):
        return "\n".join([
            "【提现响应数据】",
            f"> 原始积分: {self.exchangeBefore}",
            f"> 剩余积分: {self.balance}",
            f"> 消耗积分: {self.withdrawIntegral}",
            f"> 已兑金额: {self.exchangeMoney}元"
        ])

    def __repr__(self):
        return self.__str__()


class BalanceWithdraw(CommonRsp):
    data: BalanceWithdrawData | None

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


if __name__ == '__main__':
    print(Sign.parse_obj({
        "code": 200,
        "businessCode": "1",
        "message": "签到成功",
        "data": {
            "signItemList": [
                {
                    "date": "2024-04-05",
                    "signed": True,
                    "integral": 40
                },
                {
                    "date": "2024-04-06",
                    "signed": False,
                    "integral": 50
                },
                {
                    "date": "2024-04-07",
                    "signed": False,
                    "integral": 60
                },
                {
                    "date": "2024-04-08",
                    "signed": False,
                    "integral": 70
                },
                {
                    "date": "2024-04-09",
                    "signed": False,
                    "integral": 80
                },
                {
                    "date": "2024-04-10",
                    "signed": False,
                    "integral": 90
                },
                {
                    "date": "2024-04-11",
                    "signed": False,
                    "integral": 100
                }
            ],
            "todayCanSign": False,
            "todaySigned": True,
            "currentIntegral": 40,
            "nextIntegral": 50
        },
        "remark": None
    }).data.print_week_sign_status())
