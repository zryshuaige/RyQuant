from django.conf import settings
from django.db import models


class Favorite(models.Model):
    """自选股(关注列表)。"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    stock = models.ForeignKey("trading.Stock", on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "stock")
        ordering = ["-created_at"]
        verbose_name = "自选股"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} 自选 {self.stock.symbol}"
