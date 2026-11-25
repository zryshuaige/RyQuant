from django.conf import settings
from django.db import models


class CustomStrategy(models.Model):
    """用户自建策略(可视化规则搭建器产物,rule 为声明式 JSON,不存代码)。"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="custom_strategies")
    name = models.CharField("策略名", max_length=20)
    rule = models.JSONField("规则", default=dict)
    fits = models.JSONField("适合行情", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["-created_at"]
        verbose_name = "自定义策略"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} 自定义 {self.name}"