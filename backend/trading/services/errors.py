"""业务校验异常:统一渲染为 {"detail": message},HTTP 400。"""
from rest_framework.exceptions import ValidationError


class BusinessError(ValidationError):
    """业务规则错误(下单校验、权限、参数等),响应形状与旧接口一致:{detail: str}。"""

    status_code = 400
    default_detail = "请求不合法"

    def __init__(self, detail=None, code=None):
        super().__init__({"detail": detail or self.default_detail}, code)
