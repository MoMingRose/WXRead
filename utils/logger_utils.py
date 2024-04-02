# -*- coding: utf-8 -*-
# logger_utils.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from colorama import Fore, Style
from httpx import Response
from pydantic import BaseModel

from utils import get_date

try:
    import ujson as json
except ModuleNotFoundError:
    import json

logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

lock = threading.Lock()


class LogColors:
    DEBUG = Fore.WHITE
    INFO = Fore.GREEN
    WARNING = Fore.YELLOW
    ERROR = Fore.RED
    CRITICAL = Fore.RED


class NestedLogColors:
    @staticmethod
    def blue(content: str):
        return Fore.BLUE + content + Style.RESET_ALL + "{{log-color}}"

    @staticmethod
    def red(content: str):
        return Fore.RED + content + Style.RESET_ALL + "{{log-color}}"

    @staticmethod
    def green(content: str):
        return Fore.GREEN + content + Style.RESET_ALL + "{{log-color}}"

    @staticmethod
    def yellow(content: str):
        return Fore.YELLOW + content + Style.RESET_ALL + "{{log-color}}"

    @staticmethod
    def white(content: str):
        return Fore.WHITE + content + Style.RESET_ALL + "{{log-color}}"

    @staticmethod
    def black(content: str):
        return Fore.BLACK + content + Style.RESET_ALL + "{{log-color}}"

    @staticmethod
    def cyan(content: str):
        return Fore.CYAN + content + Style.RESET_ALL + "{{log-color}"

    @staticmethod
    def magenta(content: str):
        return Fore.MAGENTA + content + Style.RESET_ALL + "{{log-color}"


class Logger:
    def __init__(self, name: str, fh_level=logging.DEBUG, ch_level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        path_dir = os.path.join(logs_dir, name)
        # 建立一个FileHandler,用于写入日志文件
        try:
            lock.acquire()
            if not os.path.exists(path_dir):
                os.makedirs(path_dir)
        except Exception as e:
            print(e)
        finally:
            lock.release()
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
        self.is_set_prefix = False
        self.current_prefix_tag = ""

    def set_tag(self, tag):
        self.logger.handlers[0].setFormatter(
            logging.Formatter(f'%(asctime)s - %(name)s \n=> %(levelname)s \n=> {tag} \n=> %(message)s \n'))
        self.logger.handlers[1].setFormatter(logging.Formatter(f'{tag}[%(levelname)s] -> %(message)s'))

    def set_console_level(self, level):
        self.logger.handlers[1].setLevel(level)

    def set_file_level(self, level):
        self.logger.handlers[0].setLevel(level)

    def debug(self, msg, *args, prefix="", **kwargs):
        self.log(logging.DEBUG, msg, *args, prefix_tag=prefix, **kwargs)

    def info(self, msg, *args, prefix="", **kwargs):
        self.log(logging.INFO, msg, *args, prefix_tag=prefix, **kwargs)

    def war(self, msg, *args, prefix="", **kwargs):
        self.log(logging.WARNING, msg, *args, prefix_tag=prefix, **kwargs)

    def error(self, msg, *args, prefix="", **kwargs):
        self.log(logging.ERROR, msg, *args, prefix_tag=prefix, **kwargs)

    def cri(self, msg, *args, prefix="", **kwargs):
        self.log(logging.CRITICAL, msg, *args, prefix_tag=prefix, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        self.log(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)

    def log(self, level, msg, *args, prefix_tag="", **kwargs):
        lock.acquire()
        if isinstance(msg, BaseModel):
            msg = msg.__str__()
        level_name = logging.getLevelName(level)
        level_color = getattr(LogColors, level_name)
        msg = msg.replace("{{log-color}}", level_color)
        msg = f"{level_color}{msg}{Style.RESET_ALL}"
        # if prefix and not self.is_set_prefix:
        if prefix_tag and prefix_tag != self.current_prefix_tag:
            # print(f"开始重置前缀 {prefix_tag}: {self.current_prefix_tag}")
            self.current_prefix_tag = prefix_tag
            color_prefix_tag = f"{Fore.BLACK}{prefix_tag}{Style.RESET_ALL}"
            self.logger.handlers[0].setFormatter(
                logging.Formatter(f'%(asctime)s - %(name)s \n=> %(levelname)s \n=> {prefix_tag} \n=> %(message)s \n'))
            self.logger.handlers[1].setFormatter(logging.Formatter(f'{color_prefix_tag}[%(levelname)s] -> %(message)s'))
        # else:
        # print(f"前缀未变化：{prefix_tag}: {self.current_prefix_tag}")
        self.logger.log(level, msg, *args, **kwargs)
        lock.release()

    def response(
            self,
            prefix: str,
            response: Response,
            *args,
            prefix_tag="",
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

        self.logger.debug(Fore.WHITE + "\n".join(msg_list) + Style.RESET_ALL)


class ThreadLogger(Logger):
    def __init__(self, name: str, thread2name: dict = None):
        super().__init__(name)
        self.thread2name = thread2name

    @property
    def name(self):
        try:
            lock.acquire()
            thread_name = threading.current_thread().name
            if thread_name == "MainThread":
                return ""
            else:
                thread_name = self.thread2name[threading.current_thread().ident]
                return thread_name
        finally:
            lock.release()

    def info(self, msg, *args, **kwargs):
        super().info(msg, *args, prefix=self.name, **kwargs)

    def debug(self, msg, *args, **kwargs):
        super().debug(msg, *args, prefix=self.name, **kwargs)

    def war(self, msg, *args, **kwargs):
        super().war(msg, *args, prefix=self.name, **kwargs)

    def error(self, msg, *args, **kwargs):
        super().error(msg, *args, prefix=self.name, **kwargs)

    def cri(self, msg, *args, **kwargs):
        super().cri(msg, *args, prefix=self.name, **kwargs)

    def response(self, prefix: str, response: Response, *args, **kwargs):
        super().response(
            prefix,
            response,
            *args,
            prefix_tag=self.name,
            **kwargs
        )