from django.db import models

from .stock import Stock


class Candle(models.Model):
    """K 线(由行情模拟器聚合维护),供图表与量化回测共用。"""

    class Period(models.TextChoices):
        MINUTE = "1min", "分钟"
        DAY = "1day", "日线"

    class Source(models.TextChoices):
        REAL = "real", "真实"
        SIM = "sim", "模拟"

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="candles")
    period = models.CharField("周期", max_length=8, choices=Period.choices)
    time = models.DateTimeField("时间")  # 分钟线为分钟起点;日线为当日 00:00(本地)
    open = models.DecimalField("开盘", max_digits=12, decimal_places=2)
    high = models.DecimalField("最高", max_digits=12, decimal_places=2)
    low = models.DecimalField("最低", max_digits=12, decimal_places=2)
    close = models.DecimalField("收盘", max_digits=12, decimal_places=2)
    volume = models.BigIntegerField("成交量", default=0)
    source = models.CharField("数据来源", max_length=8, choices=Source.choices, default=Source.SIM)

    class Meta:
        unique_together = ("stock", "period", "time")
        ordering = ["time"]
        verbose_name = "K线"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.stock.symbol} {self.period} {self.time:%Y-%m-%d %H:%M} C:{self.close}"


