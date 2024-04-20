# -*- coding: utf-8 -*-
# __init__.py.py created by MoMingLog on 19/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-19
【功能描述】
"""
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from app.callback.wx_bussiness.WXBizMsgCrypt3 import WXBizMsgCrypt

sToken = "hJqcu3uJ9Tn2gXPmxx2w9kkCkCE2EPYo"
sEncodingAESKey = "6qkdMrq68nTKduznJYO1A37W2oEgpkMUvkttRToqhUt"
sCorpID = "ww1436e0e65a779aee"

router = APIRouter(prefix="/wxchat")


@router.get("/wxchat")
async def wxBizMsgDetected(msg_signature, timestamp, nonce, echostr):
    wxcpt = WXBizMsgCrypt(sToken, sEncodingAESKey, sCorpID)
    ret, sEchoStr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
    if ret != 0:
        print(f"错误: VerifyURL 返回值: {ret}")
    else:
        print("URL验证成功, 回声字符串:", sEchoStr)
        return Response(sEchoStr)


@router.post("/wxchat")
async def wxBizMsgDetected(msg_signature, timestamp, nonce, request: Request):
    wxcpt = WXBizMsgCrypt(sToken, sEncodingAESKey, sCorpID)
    body = await request.body()
    ret, sMsg = wxcpt.DecryptMsg(body, msg_signature, timestamp, nonce)
    if ret != 0:
        print(f"错误: DecryptMsg 返回值: {ret}")
    else:
        print("消息解密成功, 消息内容:", sMsg)
