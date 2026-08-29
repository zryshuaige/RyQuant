from django.conf import settings
from django.db import models


class AIConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "AI 会话"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title or f"会话 #{self.pk}"


class AIMessage(models.Model):
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=20)  # "user" / "bot"
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "AI 消息"
        verbose_name_plural = verbose_name
