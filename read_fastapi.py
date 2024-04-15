# -*- coding: utf-8 -*-
# read_fastapi.py created by MoMingLog on 15/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-15
【功能描述】
new Env("FastApi-配置自动化");
0 0 5 * * * read_fastapi.py

使用docker容器的, 请将6699端口映射出来

只要你的ip/域名+端口，可以访问，并显示“可以开始使用啦”，那么就表示你配置好了

为了简单一点，故此API程序统一使用 WxPusher 推送，请填好对应的配置项

方式一：添加环境变量（推荐: 因为拉库会覆盖此文件配置），下方被 `` 包裹的就是环境变量名
方式二：本文件下方有，按照注释内容填写即可

"""
import json
import os.path
from typing import Dict

import yaml
from fastapi import FastAPI
from pydantic import BaseModel, Field

from utils.push_utils import WxPusher

# WxPusher 配置
# `WxPusher_AppToken`
appToken = ""
# `WxPusher_TopicIds` 主题ID，可直接配置一个，也可配置多个
# 配置单个可以用 topicIds = "" 配置多个可以用 uids = ["topicId1", "topicId2"]
# 环境变量支持多行，一行一个
topicIds = []
# `WxPusher_UIDS` UIDS，可直接配置一个，也可配置多个
# 配置单个可以用 uids = "uid" 配置多个可以用 uids = ["uid1", "uid2"]
# 环境变量支持多行一行一个
uids = ""

if not appToken:
    appToken = os.getenv("WxPusher_AppToken")
    if not appToken:
        raise Exception("请配置环境变量 WxPusher_AppToken")

if not topicIds:
    topicIds = os.getenv("WxPusher_TopicIds")

if not uids:
    uids = os.getenv("WxPusher_UIDS")

if not topicIds and not uids:
    raise Exception("请配置环境变量 WxPusher_TopicIds 或 WxPusher_UIDS")

app = FastAPI()


class PostData(BaseModel):
    post_type: int = Field(..., description="上传数据的平台类型: 1:xyy 2:ltwm")
    user_id: int = Field(..., description="uid")
    user_name: str | None = Field(None, description="用户名")
    cookie: str | None = Field(None, alias="Cookie", description="Cookie")
    authorization: str | None = Field(None, alias="Authorization", description="Authorization")
    ua: str | None = Field(None, alias="User-Agent", description="User-Agent")


def push_msg(msg: str, title: str = "MoMingLog-配置更新通知"):
    WxPusher.push_msg(
        appToken,
        title,
        msg,
        topicIds=topicIds,
        uids=uids
    )


@app.get("/")
async def root():
    push_msg("可以开始使用啦")
    return "可以开始使用啦"


config_dir = os.path.join(os.path.dirname(__file__), "config")


@app.post("/config/upload")
async def _(data: PostData):
    if data.post_type == 1:
        # 小阅阅
        file_path = os.path.join(config_dir, "xyy.yaml")
        modify_name = "小阅阅阅读"
    elif data.post_type == 2:
        # 力天微盟
        file_path = os.path.join(config_dir, "ltwm.yaml")
        modify_name = "力天微盟"
    else:
        push_msg("当前平台暂不支持")
        return {"message": "当前平台暂不支持"}

    # 判断配置文件是否存在
    if not os.path.exists(file_path):
        push_msg(f"配置文件 {file_path}  不存在")
        return {"message": "配置文件不存在"}

    # 先加载对应的yaml文件
    with open(file_path, "r", encoding="utf-8") as fp:
        try:
            # 为避免存储时保存不应该显示的配置项，故这里单独加载
            config_data = yaml.safe_load(fp)
        except (IOError, yaml.YAMLError):
            push_msg(f"配置文件 {file_path} 内容有误")
            return {"message": "配置文件内容有误"}

    # 获取文件中的account_data数据
    account_data: Dict[str, Dict] = config_data.get("account_data", {})

    user_data: Dict[str, Dict] = {}
    if data.user_name:
        key = data.user_name
    else:
        key = data.user_id

    update_user_name = None

    # 筛选出user_id相同的数据
    for account_name, account_info in account_data.items():
        user_id = account_info.get("user_id")
        if user_id and user_id == data.user_id:
            update_user_name = account_name
            key = account_name
            user_data[key] = account_info
            break

    if not user_data:
        user_data[key] = {}
        old_account_data = "当前在添加新账号，故无原始数据!"
    else:
        old_account_data = json.dumps(user_data, ensure_ascii=False, indent=4)

    # 开始覆盖/添加配置
    if data.user_id:
        user_data[key]["user_id"] = data.user_id
    if data.cookie:
        user_data[key]["cookie"] = data.cookie
    if data.authorization:
        user_data[key]["authorization"] = data.authorization
    if data.ua:
        user_data[key]["ua"] = data.ua

    account_data.update(user_data)

    all_account_data = json.dumps(account_data, ensure_ascii=False, indent=4)

    update_content = json.dumps(user_data, ensure_ascii=False, indent=4)

    with open(file_path, "w", encoding="utf-8") as fp:
        try:
            yaml.safe_dump(
                config_data,
                fp,
                encoding="utf-8",
                allow_unicode=True,
                sort_keys=False
            )

            if update_user_name is None:
                header = f"{modify_name} - 新账号 添加成功!"
            else:
                header = f"{modify_name} - {update_user_name} 更新成功!"

            push_msg("\n".join([
                header,
                f"> 原始数据内容如下:\n {old_account_data}",
                f"> 更新内容数据如下:\n {update_content}",
                f"> 所有账号数据如下:\n {all_account_data}"
            ]))
            return {"message": f"{modify_name} - 更新/添加成功!"}
        except (IOError, yaml.YAMLError):

            if update_user_name is None:
                header = f"{modify_name} - 新账号 添加失败!"
            else:
                header = f"{modify_name} - {update_user_name} 更新失败!"
            push_msg("\n".join([
                header,
                f"> 原始数据内容如下:\n {old_account_data}",
                f"> 更新内容数据如下:\n {update_content}",
                f"> 所有账号数据如下:\n {all_account_data}"
            ]))

            return {"message": f"{modify_name} - 更新/添加失败!"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=6699)
