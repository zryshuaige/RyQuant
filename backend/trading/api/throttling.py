from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthThrottle(AnonRateThrottle):
    """注册/登录按 IP 限流,防暴力破解。"""
    scope = "auth"


class OrderThrottle(UserRateThrottle):
    scope = "order"


class BacktestThrottle(UserRateThrottle):
    scope = "backtest"


class AIThrottle(UserRateThrottle):
    scope = "ai"
