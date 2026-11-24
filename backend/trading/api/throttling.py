"""限流:注册/登录按 IP 防暴力破解;回测与 AI 按用户限流(计算/调用密集)。"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthThrottle(AnonRateThrottle):
    """注册/登录按 IP 限流,防暴力破解。"""
    scope = "auth"


class BacktestThrottle(UserRateThrottle):
    scope = "backtest"


class AIThrottle(UserRateThrottle):
    scope = "ai"