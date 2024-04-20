#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#########################################################################
# 作者: jonyqin
# 创建时间: Thu 11 Sep 2014 03:55:41 PM CST
# 文件名: Sample.py
# 描述: WXBizMsgCrypt 使用示例文件
#########################################################################
from WXBizMsgCrypt3 import WXBizMsgCrypt
import xml.etree.ElementTree as ET
import sys

if __name__ == "__main__":
    # 假设企业在企业微信后台设置的参数如下
    sToken = "hJqcu3uJ9Tn2gXPmxx2w9kkCkCE2EPYo"
    sEncodingAESKey = "6qkdMrq68nTKduznJYO1A37W2oEgpkMUvkttRToqhUt"
    sCorpID = "ww1436e0e65a779aee"

    # 使用示例一：验证回调URL
    # 当企业开启回调模式时，企业号会向验证URL发送一个GET请求
    wxcpt = WXBizMsgCrypt(sToken, sEncodingAESKey, sCorpID)
    sVerifyMsgSig = "012bc692d0a58dd4b10f8dfe5c4ac00ae211ebeb"
    sVerifyTimeStamp = "1476416373"
    sVerifyNonce = "47744683"
    sVerifyEchoStr = "fsi1xnbH4yQh0+PJxcOdhhK6TDXkjMyhEPA7xB2TGz6b+g7xyAbEkRxN/3cNXW9qdqjnoVzEtpbhnFyq6SVHyA=="
    ret, sEchoStr = wxcpt.VerifyURL(sVerifyMsgSig, sVerifyTimeStamp, sVerifyNonce, sVerifyEchoStr)
    if ret != 0:
        print(f"错误: VerifyURL 返回值: {ret}")
        sys.exit(1)
    print("URL验证成功, 回声字符串:", sEchoStr)

    # 使用示例二：解密用户的回复
    sReqMsgSig = "0c3914025cb4b4d68103f6bfc8db550f79dcf48e"
    sReqTimeStamp = "1476422779"
    sReqNonce = "1597212914"
    sReqData = """<xml><ToUserName><![CDATA[ww1436e0e65a779aee]]></ToUserName>
<Encrypt><![CDATA[Kl7kjoSf6DMD1zh7rtrHjFaDapSCkaOnwu3bqLc5tAybhhMl9pFeK8NslNPVdMwmBQTNoW4mY7AIjeLvEl3NyeTkAgGzBhzTtRLNshw2AEew+kkYcD+Fq72Kt00fT0WnN87hGrW8SqGc+NcT3mu87Ha3dz1pSDi6GaUA6A0sqfde0VJPQbZ9U+3JWcoD4Z5jaU0y9GSh010wsHF8KZD24YhmZH4ch4Ka7ilEbjbfvhKkNL65HHL0J6EYJIZUC2pFrdkJ7MhmEbU2qARR4iQHE7wy24qy0cRX3Mfp6iELcDNfSsPGjUQVDGxQDCWjayJOpcwocugux082f49HKYg84EpHSGXAyh+/oxwaWbvL6aSDPOYuPDGOCI8jmnKiypE+]]></Encrypt>
<AgentID><![CDATA[1000002]]></AgentID>
</xml>"""
    ret, sMsg = wxcpt.DecryptMsg(sReqData, sReqMsgSig, sReqTimeStamp, sReqNonce)
    if ret != 0:
        print(f"错误: DecryptMsg 返回值: {ret}")
        sys.exit(1)
    print("解密成功, 消息内容:", sMsg)

    # 使用示例三：加密回复用户的消息
    sRespData = """<xml><ToUserName>ww1436e0e65a779aee</ToUserName><FromUserName>ChenJiaShun</FromUserName>
<CreateTime>1476422779</CreateTime><MsgType>text</MsgType><Content>你好</Content><MsgId>1456453720</MsgId>
<AgentID>1000002</AgentID></xml>"""
    ret, sEncryptMsg = wxcpt.EncryptMsg(sRespData, sReqNonce, sReqTimeStamp)
    if ret != 0:
        print(f"错误: EncryptMsg 返回值: {ret}")
        sys.exit(1)
    print("加密成功, 加密消息:", sEncryptMsg)
