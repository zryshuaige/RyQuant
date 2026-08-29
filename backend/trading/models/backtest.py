from decimal import Decimal

from django.conf import settings
from django.db import models


class BacktestRun(models.Model):
    """量化策略回测记录:结果以 JSON 持久化,支持历史回看。"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="backtests")
    strategy = models.CharField("策略", max_length=32)
    stock = models.ForeignKey("trading.Stock", on_delete=models.SET_NULL, null=True, blank=True, related_name="backtests")
    symbol = models.CharField("标的代码", max_length=32)
    params = models.JSONField("策略参数", default=dict)
    days = models.IntegerField("回测天数", default=120)
    initial_capital = models.DecimalField("初始资金", max_digits=14, decimal_places=2, default=Decimal("100000.00"))
    metrics = models.JSONField("绩效指标", default=dict)
    equity_curve = models.JSONField("资金曲线", default=list)
    candles = models.JSONField("K线数据", default=list)
    markers = models.JSONField("买卖点", default=list)
    trades = models.JSONField("逐笔交易", default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "回测记录"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} {self.strategy} x {self.symbol}"
