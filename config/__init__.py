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

from schema.ddz import DDZConfig
from schema.klyd import KLYDConfig
from schema.ltwm import LTWMConfig
from schema.mmkk import MMKKConfig
from schema.xyy import XYYConfig
from schema.ymz import YMZConfig
from schema.yryd import YRYDConfig
from utils import md5

root_dir = os.path.dirname(__file__)


def __load_config(task_name: str, filename: str, model: Type[BaseModel], **kwargs) -> any:
    """
    从本地加载数据
    :param filename: 文件名
    :return:
    """
    common_path = os.path.join(root_dir, "common.yaml")
    path = os.path.join(root_dir, f"{filename}.yaml")

    biz_file_path = os.path.join(root_dir, "biz_data.yaml")

    biz_data = None

    if os.path.exists(biz_file_path):
        with open(biz_file_path, "r", encoding="utf-8") as fp:
            try:
                biz_data = yaml.safe_load(fp)
            except  (IOError, yaml.YAMLError):
                pass

    example_file_path = os.path.join(root_dir, f"{filename}_example.yaml")

    if not os.path.exists(common_path):
        # 复制common_example.yaml, 作为common.yaml的模板
        shutil.copyfile(os.path.join(root_dir, f"common_example.yaml"), common_path)

    if not os.path.exists(path):
        msg = f"【{task_name}任务】配置文件不存在\n> 提示: 请在config文件夹下创建{filename}.yaml（参考{filename}_example.yaml文件）\n> 路径：{example_file_path}"
        raise FileNotFoundError(msg)

    with open(common_path, "r", encoding="utf-8") as fp:
        try:
            config_data = yaml.safe_load(fp)
        except (IOError, yaml.YAMLError):
            msg = f"【{task_name}任务】配置文件内容有误\n> 参考内容：{filename}_example.yaml\n> 路径：{example_file_path}"
            raise ValueError(msg)

    with open(path, "r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp)

    if data is None:
        msg = f"【{task_name}任务】配置文件内容为空\n> 参考内容：{filename}_example.yaml\n> 路径：{example_file_path}"
        raise ValueError(msg)
    else:
        config_data = data if config_data is None else config_data
        config_data.update(data)
        if (old_biz_data := config_data.get("biz_data")) and biz_data is not None:
            old_biz_data.extend(biz_data)
            config_data['biz_data'] = list(set(old_biz_data))
        else:
            config_data['biz_data'] = biz_data

    return model(**config_data, source=path, **kwargs)


def load_mmkk_config() -> MMKKConfig:
    """
    加载猫猫看看阅读的配置
    :return:
    """
    return __load_config("猫猫看看", "mmkk", MMKKConfig)


def load_klyd_config() -> KLYDConfig:
    """
    加载可乐阅读的配置
    :return:
    """
    return __load_config("可乐阅读", "klyd", KLYDConfig)
    # if data.biz_data is None:
    #     data.biz_data = ["MzkwNTY1MzYxOQ=="]
    #     # 给yaml中没有配置biz_data的自动添加
    #     with open(os.path.join(root_dir, "klyd.yaml"), "a", encoding="utf-8") as fp:
    #         fp.write("\nbiz_data:\n")
    #         for i in data.biz_data:
    #             fp.write(f"  - \"{i}\"\n")
    # return data


def load_yryd_config() -> YRYDConfig:
    """
    加载鱼儿阅读的配置
    :return:
    """
    return __load_config("鱼儿阅读", "yryd", YRYDConfig)


def load_ltwm_config() -> LTWMConfig:
    """
    加载力天微盟阅读的配置
    :return:
    """
    return __load_config("力天微盟", "ltwm", LTWMConfig)


def load_xyy_config() -> XYYConfig:
    """
    加载 小阅阅 阅读的配置
    :return:
    """
    return __load_config("小阅阅", "xyy", XYYConfig)


def load_ddz_config() -> DDZConfig:
    """
    加载 点点赚 阅读的配置
    :return:
    """
    return __load_config("点点赚", "ddz", DDZConfig)


def load_ymz_config() -> YMZConfig:
    """
    加载 有米赚 阅读的配置
    :return:
    """
    return __load_config("有米赚", "ymz", YMZConfig)


cache_dir = os.path.join(root_dir, "cache")

if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

cache_file_path = os.path.join(root_dir, "cache", "cache.yaml")


def storage_cache_config(cache_data: dict, file_path: str = None) -> None:
    """
    将新的缓存数据与现有数据合并后写入缓存配置文件中

    :param cache_data: 要合并的缓存数据
    :param file_path: 缓存配置文件的路径
    :return: None
    """
    if file_path is None:
        file_path = cache_file_path
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing_data = yaml.safe_load(f) or {}
            existing_data.update(cache_data)

        with open(file_path, "w", encoding="utf-8") as fp:
            yaml.dump(existing_data, fp)
    except (IOError, yaml.YAMLError) as e:
        print(f"缓存文件更新失败: {e}")


def load_wx_business_access_token(corp_id: int, agent_id: int, file_path: str = None) -> str:
    """
    从缓存配置文件中加载指定corp_id和agent_id的access_token

    :param corp_id: 企业ID
    :param agent_id: 应用ID
    :param file_path: 缓存配置文件的路径
    :return: access_token
    """
    try:
        if file_path is None:
            file_path = cache_file_path

        with open(file_path, "r", encoding="utf-8") as fp:
            cache_data = yaml.safe_load(fp) or {}

        key = md5(f"{corp_id}_{agent_id}")

        access_token = cache_data["wxBusiness"][key].get("accessToken")

        if access_token is None:
            raise KeyError(f"未找到对应配置项数据 corp_id={corp_id}, agent_id={agent_id}")

        return access_token
    except (IOError, yaml.YAMLError) as e:
        # 这里抛出KeyError异常，方便 推送方法 中的 在线获取token
        raise KeyError(f"缓存文件读取失败: {e}")


detected_file_path = os.path.join(cache_dir, "detected.yaml")


def load_detected_data() -> set:
    """读取检测数据，返回去重后的数据"""
    if not os.path.exists(detected_file_path):
        return set()
    try:
        with open(detected_file_path, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
        return set(data)
    except (IOError, yaml.YAMLError) as e:
        print(f"检测数据加载失败: {e}")
    except TypeError:
        print("配置文件内容有误，请检查")


def store_detected_data(new_data: set, old_data: set = None):
    if old_data is not None:
        old_data.update(new_data)
    else:
        old_data = new_data
    try:
        with open(detected_file_path, "w", encoding="utf-8") as fp:
            yaml.dump(list(old_data), fp)
        return True
    except (IOError, yaml.YAMLError) as e:
        print(f"检测数据更新失败: {e}")
