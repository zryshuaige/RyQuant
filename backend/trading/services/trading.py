"""交易领域服务:下单与撤单。所有资金/持仓变更必须经由本模块并在事务内执行。"""
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404

from ..models import CashAccount, Order, Position, Stock
from . import fees, matching
from .errors import BusinessError

TWO_PLACES = Decimal("0.01")
MARKET_PRICE_BUFFER = Decimal("1.01")  # 市价单按现价上浮 1% 预估冻结


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, ROUND_HALF_UP)


def get_cash_account(user) -> CashAccount:
    account, _ = CashAccount.objects.get_or_create(user=user, defaults={"balance": _initial_capital()})
    return account


def _initial_capital() -> Decimal:
    from django.conf import settings

    return getattr(settings, "INITIAL_CAPITAL", Decimal("100000.00"))


def parse_price(raw):
    """价格解析:空返回 None;非法抛 400。"""
    if raw is None or raw == "":
        return None
    try:
        price = money(raw)
    except Exception:
        raise BusinessError("委托价格格式不正确")
    return price


@transaction.atomic
def place_order(user, stock: Stock, side: str, quantity, order_type=Order.OrderType.LIMIT, price=None) -> Order:
    """
    下单流程:校验(数量/手数/涨跌停)→ 冻结资金或持仓 → 生成 PENDING 委托 → 立即尝试撮合。
    限价买单可能即时全部成交、部分成交或等待行情;市价单以当前价立即成交。
    """
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise BusinessError("下单数量必须为正整数")
    if quantity <= 0:
        raise BusinessError("下单数量必须大于 0")
    if side not in Order.Side.values:
        raise BusinessError("side 必须为 BUY 或 SELL")
    order_type = order_type if order_type in Order.OrderType.values else Order.OrderType.LIMIT
    if not stock.is_active:
        raise BusinessError("该标的当前不可交易")

    lot = stock.lot_size
    if order_type == Order.OrderType.LIMIT:
        if price is None:
            raise BusinessError("限价单必须提供委托价格")
        if price <= 0:
            raise BusinessError("委托价格必须大于 0")
        if stock.prev_close > 0:
            low, high = stock.limit_down, stock.limit_up
            if price < low or price > high:
                raise BusinessError(f"委托价 {price} 超出涨跌停范围 {low} ~ {high}")

    if side == Order.Side.BUY:
        if quantity % lot != 0:
            raise BusinessError(f"买入数量必须为 {lot} 的整数倍")
    else:
        pos = Position.objects.filter(user=user, stock=stock).first()
        available = pos.available_quantity if pos else 0
        if quantity % lot != 0 and quantity != available:
            raise BusinessError(f"卖出数量需为 {lot} 的整数倍,或一次性清仓全部可用持仓({available} 股)")

    cash = CashAccount.objects.select_for_update().get(user=user)
    order = Order(user=user, stock=stock, side=side, order_type=order_type, price=price, quantity=quantity)

    if side == Order.Side.BUY:
        ref_price = price if price is not None else (stock.price * MARKET_PRICE_BUFFER).quantize(TWO_PLACES)
        est_amount = ref_price * quantity
        if order_type == Order.OrderType.MARKET:
            est_amount *= MARKET_PRICE_BUFFER
        frozen = money(est_amount + fees.buy_fee(est_amount))
        if cash.balance < frozen:
            raise BusinessError(f"可用资金不足:需冻结 {frozen},当前可用 {cash.balance}")
        cash.balance -= frozen
        cash.frozen_cash += frozen
        cash.save(update_fields=["balance", "frozen_cash", "updated_at"])
        order.frozen_amount = frozen
    else:
        pos = Position.objects.select_for_update().filter(user=user, stock=stock).first()
        available = pos.available_quantity if pos else 0
        if quantity > available:
            raise BusinessError(f"可用持仓不足:可用 {available},委托 {quantity}(注意在途卖出挂单占用)")
        pos.available_quantity = F("available_quantity") - quantity
        pos.save(update_fields=["available_quantity", "updated_at"])
        order.frozen_quantity = quantity

    order.save()
    matching.try_match_order(order)  # 撮合引擎内部自行加锁并处理状态
    order.refresh_from_db()
    return order


@transaction.atomic
def cancel_order(user, order_id) -> Order:
    """撤单:仅本人、仅未成交/部分成交可撤;解冻剩余资金或持仓。"""
    order = get_object_or_404(Order.objects.select_for_update(), pk=order_id, user=user)
    if not order.is_active:
        raise BusinessError(f"当前状态「{order.get_status_display()}」不可撤单")

    cash = CashAccount.objects.select_for_update().get(user=user)
    if order.side == Order.Side.BUY and order.frozen_amount > 0:
        cash.balance += order.frozen_amount
        cash.frozen_cash -= order.frozen_amount
        cash.save(update_fields=["balance", "frozen_cash", "updated_at"])
        order.frozen_amount = Decimal("0.00")
    elif order.side == Order.Side.SELL and order.frozen_quantity > 0:
        pos = Position.objects.select_for_update().filter(user=user, stock=order.stock).first()
        if pos is not None:
            pos.available_quantity = F("available_quantity") + order.frozen_quantity
            pos.save(update_fields=["available_quantity", "updated_at"])
        order.frozen_quantity = 0

    order.status = Order.Status.CANCELLED
    order.save()
    order.refresh_from_db()
    return order
