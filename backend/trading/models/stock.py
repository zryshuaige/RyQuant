from decimal import Decimal

from django.db import models


class Stock(models.Model):
    """交易标的。price 由行情模拟器维护;prev_close 用于涨跌停校验与涨跌幅计算。
    kind=index 时为真实指数(不可交易),仅用于行情展示与量化回测。"""

    class Kind(models.TextChoices):
        STOCK = "stock", "股票"
        INDEX = "index", "指数"

    symbol = models.CharField("代码", max_length=32, unique=True)
    name = models.CharField("名称", max_length=128)
    kind = models.CharField("类型", max_length=8, choices=Kind.choices, default=Kind.STOCK)
    price = models.DecimalField("现价", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    prev_close = models.DecimalField("昨收", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    limit_pct = models.DecimalField("涨跌停幅度%", max_digits=5, decimal_places=2, default=Decimal("10"))
    lot_size = models.IntegerField("每手股数", default=100)
    is_active = models.BooleanField("可交易", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol"]
        verbose_name = "股票"
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        # 板块规则自动推导:科创板 688 每手 200 股,其余 100 股;创业板 300 / 科创板 688 涨跌幅 20%
        if self.kind == self.Kind.INDEX:
            self.lot_size, self.limit_pct = 100, Decimal("10")
        else:
            self.lot_size = 200 if self.symbol.startswith("688") else 100
            self.limit_pct = Decimal("20") if self.symbol.startswith(("300", "688")) else Decimal("10")
        super().save(*args, **kwargs)

    @property
    def change(self) -> Decimal:
        return self.price - self.prev_close

    @property
    def change_pct(self) -> Decimal:
        if self.prev_close <= 0:
            return Decimal("0")
        return (self.change / self.prev_close * 100).quantize(Decimal("0.01"))

    @property
    def limit_up(self) -> Decimal:
        return (self.prev_close * (1 + self.limit_pct / 100)).quantize(Decimal("0.01"))

    @property
    def limit_down(self) -> Decimal:
        return (self.prev_close * (1 - self.limit_pct / 100)).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.symbol} {self.name}"
