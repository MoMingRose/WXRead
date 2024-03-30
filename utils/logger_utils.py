# -*- coding: utf-8 -*-
# logger_utils.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
import logging
import os

from utils import get_date

logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


class Logger:
    def __init__(self, name: str, fh_level=logging.DEBUG, ch_level=logging.INFO):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
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
        logger.addHandler(fh)
        logger.addHandler(ch)
        self.logger = logger

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


if __name__ == '__main__':
    # logyyx = Logger('yyx.log', logging.ERROR, logging.DEBUG)
    logyyx = Logger("😸阅读")
    logyyx.set_tag("测试")
    logyyx.set_console_level(logging.DEBUG)
    # logyyx.set_file_level(logging.DEBUG)
    logyyx.debug('一个debug信息')
    logyyx.info('一个info信息')
    logyyx.war('一个warning信息')
    logyyx.error('一个error信息')
    logyyx.cri('一个致命critical信息')
