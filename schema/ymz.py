# -*- coding: utf-8 -*-
# ymz.py created by MoMingLog on 17/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-17
【功能描述】
"""
from typing import Type, Dict, List

from pydantic import create_model, BaseModel, Field

from schema.common import CommonPartConfig, CommonGlobalConfig


class CommonYMZConfig(BaseModel):
    """有米赚全局和局部的相同配置"""
    pwd: int | None = Field(None, description="有米赚提现密码")


class YMZAccount(CommonPartConfig, CommonYMZConfig):
    """有米赚（局部配置）"""
    userShowId: int


class BaseYMZGlobalConfig(CommonGlobalConfig, CommonYMZConfig):
    """有米赚（全局配置）"""
    pass


YMZConfig: Type[BaseYMZGlobalConfig] = create_model(
    "YMZConfig",
    account_data=(Dict[str | int, YMZAccount], {}),
    source=(str, "ymz.yaml"),
    __base__=BaseYMZGlobalConfig
)


class CommonRsp(BaseModel):
    code: int
    message: str
    success: bool | None = Field(None, description="是否成功")


class RspLoginInfo(BaseModel):
    accountId: int | None = Field(None, description="上级ID")
    city: str | None = Field(None, description="城市")
    country: str | None = Field(None, description="国家")
    createTime: str | None = Field(None, description="创建时间")
    createUser: int | None = Field(None, description="创建人")
    daySum: str | None = Field(None, description="日总量")
    deductNum: int | None = Field(None, description="扣量")
    delFlag: int | None = Field(None, description="删除标记")
    drawMoney: int | None = Field(None, description="提现")
    headimgurl: str | None = Field(None, description="头像")
    highQuality: int | None = Field(None, description="高清")
    id: str | None = Field(None, description="账号ID")
    isPwd: bool | None = Field(None, description="是否有密码")
    iscount: int | None = Field(None, description="是否计数")
    labelList: str | None = Field(None, description="标签")
    level: str | None = Field(None, description="等级")
    nickname: str | None = Field(None, description="昵称")
    openid: str | None = Field(None, description="openid")
    parentService: str | None = Field(None, description="父级服务")
    preService: str | None = Field(None, description="前级服务")
    privilege: str | None = Field(None, description="权限")
    province: str | None = Field(None, description="省份")
    score: int | None = Field(None, description="积分")
    sex: str | None = Field(None, description="性别")
    unionid: str | None = Field(None, description="unionid")
    updateTime: str | None = Field(None, description="更新时间")
    updateUser: str | None = Field(None, description="更新人")
    userId: str | None = Field(None, description="用户ID")
    userLabel: str | None = Field(None, description="用户标签")
    userShowId: int | None = Field(None, description="用户ID")
    wdPassword: str | None = Field(None, description="微信密码")

    def __str__(self):
        return "\n".join([
            "登录成功，信息如下",
            f"❄️>> 上级ID: {self.accountId}",
            f"❄️>> 用户ID: {self.userShowId}",
            f"❄️>> 用户昵称: {self.nickname}",
            f"❄️>> 是否有密码: {self.isPwd}",
            f"❄️>> 创建日期: {self.createTime}",
        ])


class RspLogin(CommonRsp):
    data: RspLoginInfo

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


class RspUserinfoData(BaseModel):
    activityScore: int | None = Field(None, description="文章阅读积分一轮可得")
    alreadyMoney: int | None = Field(None, description="已提金额")
    cashMoney: float | None = Field(None, description="当前余额")
    cashScore: int | None = Field(None, description="当前积分")
    cheatScore: int | None = Field(None, description="作弊积分（不知是否是这个意思）")
    consumeScore: int | None = Field(None, description="消费积分")
    drawScore: int | None = Field(None, description="提现积分")
    extendAwardScore: int | None = Field(None, description="推广奖励积分")
    extendScore: int | None = Field(None, description="推广积分")
    masterQQCrowd: str | None = Field(None, description="大佬群")
    otherScore: int | None = Field(None, description="其他积分")
    sumScore: int | None = Field(None, description="总积分")
    userShowId: int | None = Field(None, description="用户ID")

    def __str__(self):
        return "\n".join([
            "用户信息",
            f"❄️>> 用户ID: {self.userShowId}",
            f"❄️>> 当前余额: {self.cashMoney}",
            f"❄️>> 当前积分: {self.cashScore}",
            f"❄️>> 推广积分: {self.extendScore}",
            f"❄️>> 总得积分: {self.sumScore}",
        ])

    def __repr__(self):
        return self.__str__()


class RspUserInfo(CommonRsp):
    data: RspUserinfoData

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


class RspTaskInfo(BaseModel):
    btnName: str | None = Field(None, description="按钮名")
    countDown: int | None = Field(None, description="倒计时")
    createTime: str | None = Field(None, description="创建时间")
    createUser: int | None = Field(None, description="")
    dayUpperLimit: int | None = Field(None, description="每日上限")
    ico: str | None = Field(None, description="图标名称和后缀名")
    id: int | None = Field(None, description="任务ID")
    isShowBtn: int | None = Field(None, description="是否显示按钮")
    perMsg: str | None = Field(None, description="展示消息")
    perUpperLimit: int | None = Field(None, description="每次上限")
    remark: str | None = Field(None, description="备注")
    score: int | None = Field(None, description="积分")
    scoreLow: int | None = Field(None, description="积分下限")
    scoreMsg: str | None = Field(None, description="积分说明")
    scoreTall: int | None = Field(None, description="积分上限")
    sort: int | None = Field(None, description="排序")
    timeLimit: int | None = Field(None, description="时间限制")
    titleMsg: str | None = Field(None, description="标题说明")
    toAccount: str | None = Field(None, description="展示消息")
    type: int | None = Field(None, description="任务类型")
    typeName: str | None = Field(None, description="任务类型名称")
    typeStatus: int | None = Field(None, description="任务状态")
    updateTime: str | None = Field(None, description="更新时间")
    updateUser: str | None = Field(None, description="更新用户")


class RspTaskList(CommonRsp):
    """任务列表响应数据"""
    data: List[RspTaskInfo] | None = Field(None, description="任务列表")


class RspArticleData(BaseModel):
    """"""
    code: str | None = Field(None, description="响应码")
    startNum: str | None = Field(None, description="当前阅读数")
    putid: str | None = Field(None, description="ID")
    endNum: str | None = Field(None, description="最大结束的阅读数")
    url: str | None = Field(None, description="文章链接")


class RspArticleUrl(CommonRsp):
    """文章列表响应数据"""
    data: RspArticleData | None = Field(None, description="阅读文章链接信息")


class RspSignInData(BaseModel):
    code: int | None = Field(None, description="响应码")
    today: int | None = Field(None, description="今日签到，获得了多少积分")
    tomorrow: int | None = Field(None, description="明日签到，获得了多少积分")
    day: int | None = Field(None, description="今天是第几天签到")

    def __str__(self):
        return "\n".join([
            "签到成功，信息如下",
            f"❄️>> 今日签到积分: {self.today}",
            f"❄️>> 明日签到积分: {self.tomorrow}",
            f"❄️>> 今天是第{self.day}天签到",
        ])

    def __repr__(self):
        return self.__str__()


class RspSignIn(CommonRsp):
    """签到响应数据"""
    data: RspSignInData | None = Field(None, description="签到信息")

    def __str__(self):
        return self.data.__str__()

    def __repr__(self):
        return self.__str__()


class RspWithdrawOptionData(BaseModel):
    id: str | None = Field(None, description="ID")
    money: int | None = Field(None, description="提现金额")
    moneyType: int | None = Field(None, description="提现类型")
    onMoney: bool | None = Field(None, description="是否开启提现")
    status: int | None = Field(None, description="状态")


class RspWithdrawOptions(CommonRsp):
    data: List[RspWithdrawOptionData] | None = Field(None, description="提现选项列表")
