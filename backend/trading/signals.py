"""用户创建时自动开立资金账户,根治 DoesNotExist→500。"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CashAccount


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="ensure-cash-account")
def ensure_cash_account(sender, instance, created, **kwargs):
    if created:
        from django.conf import settings as s

        CashAccount.objects.get_or_create(user=instance, defaults={"balance": s.INITIAL_CAPITAL})
