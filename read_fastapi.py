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

from fastapi import FastAPI

from app import all_router

app = FastAPI()

app.include_router(all_router)


@app.get("/")
async def read_root():
    return {"message": "可以开始使用啦，那么就表示你配置好了"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run("read_fastapi:app", host="0.0.0.0", port=16699, reload=True)
