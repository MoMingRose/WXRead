# -*- coding: utf-8 -*-
# logger_utils.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
import logging
import os

import httpx
from httpx import Response

from utils import get_date

try:
    import ujson as json
except ModuleNotFoundError:
    import json

logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


class Logger:
    def __init__(self, name: str, fh_level=logging.DEBUG, ch_level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        path_dir = os.path.join(logs_dir, name)
        # 建立一个FileHandler,用于写入日志文件
        if not os.path.exists(path_dir):
            os.makedirs(path_dir)
        # 建立一个FileHandler,用于写入日志文件
        fh = logging.FileHandler(f"{path_dir}/{get_date()}.log", encoding="utf-8")
        fh.setLevel(fh_level)
        # 建立一个StreamHandler,用于输出到控制台
        ch = logging.StreamHandler()
        ch.setLevel(ch_level)
        # 设置文件日志格式
        fh_formatter = logging.Formatter('%(asctime)s - %(name)s \n=> %(levelname)s \n=> %(message)s \n')
        fh.setFormatter(fh_formatter)
        # 设置控制台日志格式
        ch_formatter = logging.Formatter(f'%(message)s')
        ch.setFormatter(ch_formatter)
        # 给logger添加handler
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def set_tag(self, tag):
        self.logger.handlers[0].setFormatter(
            logging.Formatter(f'%(asctime)s - %(name)s \n=> %(levelname)s \n=> {tag} \n=> %(message)s \n'))
        self.logger.handlers[1].setFormatter(logging.Formatter(f'{tag}[%(levelname)s] -> %(message)s'))

    def set_console_level(self, level):
        self.logger.handlers[1].setLevel(level)

    def set_file_level(self, level):
        self.logger.handlers[0].setLevel(level)

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def war(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def cri(self, message):
        self.logger.critical(message)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        self.logger.exception(msg, *args, exc_info=exc_info, **kwargs)

    def response(
            self,
            prefix: str,
            response: Response,
            *args,
            print_request_url=True,
            print_request_method=True,
            print_request_headers=True,
            print_request_cookies=True,
            print_request_body=True,
            print_response_headers=True,
            print_response_body=True,
            print_text_all=False,
            print_text_limit=1000,
            **kwargs
    ):
        prefix = prefix.center(30, "*")

        msg_list = [prefix, f"==> 【响应状态码】{response.status_code}"]

        if print_request_url:
            msg_list.append(f"==> 【请求地址】{response.url}")
        if print_request_method:
            msg_list.append(f"==> 【请求方法】{response.request.method}")
        if print_request_headers:
            msg_list.append(f"==> 【请求头】")
            for key, value in response.request.headers.items():
                msg_list.append(f"{key}: {value}")
        if print_request_body:
            body = response.request.content.decode(encoding='utf-8')
            if body:
                msg_list.append(f"==> 【请求数据】")
                msg_list.append(body)
        if print_response_headers:
            msg_list.append(f"==> 【响应头】")
            for key, value in response.headers.items():
                msg_list.append(f"{key}: {value}")
        if print_response_body:
            content = response.text
            if content:
                msg_list.append(f"==> 【响应数据】")
                # 判断是否为json
                try:
                    content = json.loads(content)
                    content = json.dumps(content, ensure_ascii=False, indent=2)
                except json.decoder.JSONDecodeError:
                    if not print_text_all:
                        # 判断长度是否超过1000
                        if len(content) > print_text_limit:
                            content = content[:print_text_limit] + f"...（超过{print_text_limit}，已省略）"

                msg_list.append(content)

        suffix = prefix.center(30, "*")
        msg_list.append(suffix)

        self.logger.debug("\n".join(msg_list))


if __name__ == '__main__':
    # logyyx = Logger('yyx.log', logging.ERROR, logging.DEBUG)
    logyyx = Logger("😸阅读")
    logyyx.set_console_level(logging.DEBUG)
    # logyyx.set_tag("测试")
    # logyyx.set_console_level(logging.DEBUG)
    # # logyyx.set_file_level(logging.DEBUG)
    # logyyx.debug('一个debug信息')
    # logyyx.info('一个info信息')
    # logyyx.war('一个warning信息')
    # logyyx.error('一个error信息')
    # logyyx.cri('一个致命critical信息')
    # logyyx.exception('一个异常信息')
    cookies = {"a": "b"}
    response = httpx.post("https://httpbin.org/anything", headers={"User-Agent": "Mozilla/5.0"},
                          cookies=cookies)
    logyyx.response("【增加金币，read_client】", response)
