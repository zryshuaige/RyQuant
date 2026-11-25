"""限流:注册/登录按 IP 防暴力破解;回测与 AI 按用户限流(计算/调用密集)。"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthThrottle(AnonRateThrottle):
    """注册/登录按 IP 限流,防暴力破解。"""
    scope = "auth"


class BacktestThrottle(UserRateThrottle):
    scope = "backtest"


class PreviewThrottle(UserRateThrottle):
    """策略实时预览:随参数拖动高频触发,只算指标不跑引擎,限流放宽。"""
    scope = "preview"


class AIThrottle(UserRateThrottle):
    scope = "ai"


class SearchThrottle(AnonRateThrottle):
    """标的检索按 IP 限流(远程联想请求)。"""
    scope = "search"


class ResolveThrottle(UserRateThrottle):
    """按需落库 + 抓历史行情,按用户限流。"""
    scope = "resolve"