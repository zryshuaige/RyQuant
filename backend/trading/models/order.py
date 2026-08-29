from decimal import Decimal

from django.conf import settings
from django.db import models


class Order(models.Model):
    """委托订单。买单在报单时冻结资金(下单即扣),卖单冻结可用持仓;成交/撤单时解冻。"""

    class Status(models.TextChoices):
        PENDING = "PENDING", "未成交"
        PARTIAL_FILLED = "PARTIAL_FILLED", "部分成交"
        FILLED = "FILLED", "已成交"
        CANCELLED = "CANCELLED", "已撤单"
        REJECTED = "REJECTED", "已废单"

    class Side(models.TextChoices):
        BUY = "BUY", "买入"
        SELL = "SELL", "卖出"

    class OrderType(models.TextChoices):
        LIMIT = "LIMIT", "限价"
        MARKET = "MARKET", "市价"

    ACTIVE_STATUSES = (Status.PENDING, Status.PARTIAL_FILLED)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    stock = models.ForeignKey("trading.Stock", on_delete=models.PROTECT, related_name="orders")
    side = models.CharField("方向", max_length=4, choices=Side.choices)
    order_type = models.CharField("类型", max_length=8, choices=OrderType.choices, default=OrderType.LIMIT)
    price = models.DecimalField("委托价", max_digits=12, decimal_places=2, null=True, blank=True)  # 市价单为空
    quantity = models.IntegerField("委托数量")
    filled_quantity = models.IntegerField("已成交数量", default=0)
    avg_fill_price = models.DecimalField("成交均价", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.PENDING)
    frozen_amount = models.DecimalField("冻结资金", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    frozen_quantity = models.IntegerField("冻结持仓", default=0)
    reject_reason = models.CharField("废单原因", max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "委托"
        verbose_name_plural = verbose_name

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    def __str__(self):
        return f"#{self.pk} {self.user.username} {self.get_side_display()} {self.stock.symbol} x {self.quantity}"


class Trade(models.Model):
    """成交回报(逐笔)。fee 已含佣金与印花税。"""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="trades")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trades")
    stock = models.ForeignKey("trading.Stock", on_delete=models.PROTECT, related_name="trades")
    side = models.CharField("方向", max_length=4, choices=Order.Side.choices)
    quantity = models.IntegerField("成交数量")
    price = models.DecimalField("成交价", max_digits=12, decimal_places=2)
    amount = models.DecimalField("成交金额", max_digits=14, decimal_places=2)
    fee = models.DecimalField("费用", max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "成交"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.get_side_display()} {self.stock.symbol} x {self.quantity} @ {self.price}"
