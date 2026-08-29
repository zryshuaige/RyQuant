"""费用计算:佣金(双边,万 2.5、最低 5 元)与印花税(仅卖出,万 5)。"""
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

TWO_PLACES = Decimal("0.01")


def _cfg(key, default):
    return Decimal(str(getattr(settings, "FEES", {}).get(key, default)))


def _to_decimal(amount) -> Decimal:
    return amount if isinstance(amount, Decimal) else Decimal(str(amount))


def commission(amount) -> Decimal:
    amount = _to_decimal(amount)
    if amount <= 0:
        return Decimal("0.00")
    fee = amount * _cfg("COMMISSION_RATE", "0.00025")
    return max(fee, _cfg("COMMISSION_MIN", "5")).quantize(TWO_PLACES, ROUND_HALF_UP)


def buy_fee(amount) -> Decimal:
    """买入费用:仅佣金。"""
    return commission(amount)


def sell_fee(amount) -> Decimal:
    """卖出费用:佣金 + 印花税。"""
    amount = _to_decimal(amount)
    stamp = (amount * _cfg("STAMP_TAX_RATE", "0.0005")).quantize(TWO_PLACES, ROUND_HALF_UP)
    return commission(amount) + stamp
