from django.conf import settings
from django.db import models


class CashAccount(models.Model):
    """资金账户:balance 为可用资金,frozen_cash 为在途买单占用的冻结资金。"""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cash_account")
    balance = models.DecimalField("可用资金", max_digits=14, decimal_places=2, default=0)
    frozen_cash = models.DecimalField("冻结资金", max_digits=14, decimal_places=2, default=0)
    is_vip = models.BooleanField("VIP", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "资金账户"
        verbose_name_plural = verbose_name

    @property
    def total_cash(self):
        return self.balance + self.frozen_cash

    def __str__(self):
        return f"{self.user.username} 的资金账户"


class Position(models.Model):
    """持仓:available_quantity = quantity - 在途卖出挂单冻结数量。"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="positions")
    stock = models.ForeignKey("trading.Stock", on_delete=models.PROTECT, related_name="positions")
    quantity = models.IntegerField("持仓数量", default=0)
    available_quantity = models.IntegerField("可用数量", default=0)
    avg_price = models.DecimalField("摊薄成本", max_digits=12, decimal_places=4, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "stock")
        verbose_name = "持仓"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} 持有 {self.stock.symbol} x {self.quantity}"
