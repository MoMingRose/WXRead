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
import os
import re
import subprocess
import platform
import time

import uvicorn
from fastapi import FastAPI
from uvicorn.main import Server, Config

from app import all_router

app = FastAPI()
app.include_router(all_router)


@app.get("/")
async def read_root():
    return {"message": "可以开始使用啦，那么就表示你配置好了"}


class FastAPIServer:
    def __init__(self, app, host='0.0.0.0', port=16699, app_module='read_fastapi:app', force_start=False):
        self.host = host
        self.port = port
        self.app_module = app_module
        self.app = app
        self.port_in_use = self.is_port_in_use()
        self.first_run = self.check_first_run()  # 检查是否第一次运行
        self.force_start = force_start

    def start(self):
        """
        启动 FastAPI 服务器
        """
        if not self.force_start and self.first_run:
            print("程序是第一次运行，正在检查端口是否被占用")
            if self.port_in_use:
                print(f"端口已被占用，请检查端口 {self.port} 是否正在运行重要程序, 如果不重要，请本代码文件中的 force_start=True")
                return
        else:
            if self.port_in_use:
                print("端口已被占用，尝试停止占用进程...")
                self.kill_process_by_port(self.port)
                if self.is_port_in_use():
                    print("无法停止占用进程，无法启动服务器！")
                    return
        uvicorn.run(self.app, host=self.host, port=self.port)

    def stop(self):
        """
        停止 FastAPI 服务器
        """
        config = Config(app=self.app_module, host=self.host, port=self.port, reload=True)
        server = Server(config)
        server.should_exit = True

    def is_port_in_use(self):
        """
        检查端口是否被占用
        """
        if platform.system() == 'Windows':
            output = self.get_netstat_output()
            lines = output.split('\n')
            for line in lines:
                if f":{self.port}" in line:
                    return True
            return False
        else:
            output = self.get_ss_output()
            lines = output.split('\n')
            for line in lines:
                if f":{self.port}" in line:
                    return True
            return False

    def kill_process_by_port(self, port):
        """
        根据端口号杀死进程
        """
        if platform.system() == 'Windows':
            output = self.get_netstat_output()
            lines = output.split('\n')
            for line in lines:
                if f":{port}" in line:
                    parts = line.split()
                    pid = int(parts[-1])  # 获取最后一列的 PID
                    print(f"Killing process with PID {pid} using port {port}...")
                    os.system(f'taskkill /F /PID {pid}')  # 使用 taskkill 命令杀死进程
                    time.sleep(1)  # 等待1秒确保进程已经被杀死
        elif platform.system() == 'Linux':
            output = self.get_ss_output()
            lines = output.split('\n')
            for line in lines:
                if f":{port}" in line:
                    match = re.search(r'pid=(\d+),', line)
                    if match:
                        pid = int(match.group(1))
                        print(f"Killing process with PID {pid} using port {port}...")
                        os.system(f'kill -9 {pid}')
                        time.sleep(1)  # 等待1秒确保进程已经被杀死
        else:
            print("暂未适配该操作系统")

    def get_netstat_output(self):
        """
        获取 netstat 命令的输出结果
        """
        output = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        return output.stdout

    def get_ss_output(self):
        """
        获取 ss 命令的输出结果
        """
        output = subprocess.run(['ss', '-anp'], capture_output=True, text=True)
        return output.stdout

    def check_first_run(self):
        """
        检查程序是否第一次运行
        """
        if os.path.exists('first_run.txt'):
            return False
        else:
            with open('first_run.txt', 'w') as f:
                f.write('First run')
            return True


if __name__ == '__main__':
    server = FastAPIServer(app, force_start=False)
    server.start()