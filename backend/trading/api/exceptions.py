"""统一异常处理:DRF 校验错误保持原样(400 字段字典 / detail),其余兜底为 500 JSON。"""
import logging

from django.db import IntegrityError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, IntegrityError):
        return Response({"detail": "数据冲突,请重试"}, status=400)
    logger.exception("未处理异常: %s", exc)
    return Response({"detail": "服务器内部错误,请稍后重试"}, status=500)
