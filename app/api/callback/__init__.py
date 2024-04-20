# -*- coding: utf-8 -*-
# __init__.py.py created by MoMingLog on 19/4/2024.
"""
【作者】MoMingLog
【创建时间】2024-04-19
【功能描述】
"""
from fastapi import APIRouter

from .customize import customize_router

callback_router = APIRouter()

callback_router.include_router(customize_router, prefix="/ct", tags=["“回调”API"])



