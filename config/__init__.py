# -*- coding: utf-8 -*-
# __init__.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
import os.path
import shutil
from typing import Type

import yaml
from pydantic import BaseModel

from schema.klyd import KLYDConfig
from schema.mmkk import MMKKConfig

root_dir = os.path.dirname(__file__)


def load_mmkk_config() -> MMKKConfig:
    """
    加载猫猫看看阅读的配置
    :return:
    """
    return __load_config("猫猫看看", "mmkk", MMKKConfig)


def load_klyd_config() -> KLYDConfig:
    """
    加载猫猫看看阅读的配置
    :return:
    """
    data: KLYDConfig = __load_config("可乐阅读", "klyd", KLYDConfig)
    if data.biz_data is None:
        data.biz_data = ["MzkwNTY1MzYxOQ=="]
        # 给yaml中没有配置biz_data的自动添加
        with open(os.path.join(root_dir, "klyd.yaml"), "a", encoding="utf-8") as fp:
            fp.write("\nbiz_data:\n")
            for i in data.biz_data:
                fp.write(f"  - \"{i}\"\n")
    return data


def __load_config(task_name: str, filename: str, model: Type[BaseModel], **kwargs) -> any:
    """
    从本地加载数据
    :param filename: 文件名
    :return:
    """
    common_path = os.path.join(root_dir, "common.yaml")
    path = os.path.join(root_dir, f"{filename}.yaml")

    example_file_path = os.path.join(root_dir, f"{filename}_example.yaml")

    if not os.path.exists(common_path):
        # 复制common_example.yaml, 作为common.yaml的模板
        shutil.copyfile(os.path.join(root_dir, f"common_example.yaml"), common_path)

    if not os.path.exists(path):
        msg = f"【{task_name}任务】配置文件不存在\n> 提示: 请在config文件夹下创建{filename}.yaml（参考{filename}_example.yaml文件）\n> 路径：{example_file_path}"
        raise FileNotFoundError(msg)

    with open(common_path, "r", encoding="utf-8") as fp:
        config_data = yaml.safe_load(fp)

    with open(path, "r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp)

    if data is None:
        msg = f"【{task_name}任务】配置文件内容为空\n> 参考内容：{filename}_example.yaml\n> 路径：{example_file_path}"
        raise ValueError(msg)
    else:
        config_data = data if config_data is None else config_data
        config_data.update(data)

    return model(**config_data, source=path, **kwargs)


if __name__ == '__main__':
    print(load_klyd_config())
