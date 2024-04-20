# -*- coding: utf-8 -*-
# __init__.py.py created by MoMingLog on 19/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-19
【功能描述】
"""

from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.requests import Request
from starlette.responses import HTMLResponse

customize_router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        try:
            del self.active_connections[client_id]
        except KeyError:
            pass

    async def send_personal_message(self, message: str, client_id: str):
        websocket = self.active_connections.get(client_id)
        if websocket:
            await websocket.send_text(message)

    async def broadcast(self, message: str):
        for websocket in self.active_connections.values():
            await websocket.send_text(message)


manager = ConnectionManager()


@customize_router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    # 连接客户端
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            # 假设数据格式为 "target_id:message"
            target_id, message = data.split(":")
            await manager.send_personal_message(message, target_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(f"Client #{client_id} has left.")


@customize_router.get("/get-link", response_class=HTMLResponse)
def get_link(redirect: str, client_id: str, target_id: str, request: Request):
    domain = request.base_url.hostname  # 获取当前请求的主机名或 IP 地址
    port = request.base_url.port  # 获取当前请求的端口
    if port is not None:
        domain = f"{domain}:{port}"
    wx_url = f"ws://{domain}/mmlg/callback/ct/ws/{client_id}"

    return f"""
<!DOCTYPE html>
<html>
    <head>
        <title>自动回调并跳转</title>
    </head>
    <body>
        <h2>client_id: <span id="ws-id">{client_id}</span></h2>
        <h2>target_id: <span id="ws-id">{target_id}</span></h2>
        <p id="message"></p>
        <script>
            var ws = new WebSocket(`{wx_url}`);
            ws.onopen = () => {{
                console.log("WebSocket connection opened.");
                ws.send("{target_id}:true");
                console.log("Message sent immediately after opening.");
            }};
            ws.onmessage = (event) => {{
                console.log("Received message:", event.data);
                document.getElementById("message").innerHTML += event.data + "<br>";
                // 判断消息中是否包含"记录成功"
                if (event.data.includes("记录成功")) {{
                    window.location.href = "{redirect}";
                }}
            }};
        </script>
    </body>
</html>
"""
