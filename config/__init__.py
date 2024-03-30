# -*- coding: utf-8 -*-
# __init__.py created by MoMingLog on 29/3/2024.
"""
【作者】MoMingLog
【创建时间】2024-03-29
【功能描述】
"""
import os.path

import yaml

from schema.mmkk import MMKKConfig

root_dir = os.path.dirname(__file__)


def load_mmkk_config() -> MMKKConfig:
    """
    加载猫猫看看阅读的配置
    :return:
    """
    path = os.path.join(root_dir, "mmkk.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"猫猫看看阅读配置文件不存在，请创建（参考example.yaml文件）：{path}")
    with open(path, "r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp)

    dynamic_config_data = MMKKConfig(**data)
    return dynamic_config_data


if __name__ == '__main__':
    print(load_mmkk_config())
