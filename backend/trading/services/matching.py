"""
撮合引擎:用户挂单与合成流动性撮合。
规则:限价单价格穿越当前市价即撮合(成交价=市价,对用户有利);每个 tick 提供随机深度,
成交量不足时部分成交,余量继续等待。市价单以当前价立即全额成交。
"""
import logging
import random
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.utils import IntegrityError

from ..models import CashAccount, Order, Position, Stock, Trade
from . import fees

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
AVG_FOUR_PLACES = Decimal("0.0001")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, ROUND_HALF_UP)


def _liquidity(stock: Stock, order: Order) -> int:
    """合成市场深度(股数):每 tick 随机 1~10 手。测试可通过注入替换。"""
    return random.randint(1, 10) * stock.lot_size


def _crossed(order: Order, market_price: Decimal) -> bool:
    if order.order_type == Order.OrderType.MARKET:
        return True
    if order.side == Order.Side.BUY:
        return market_price <= order.price
    return market_price >= order.price


@transaction.atomic
def try_match_order(order) -> Order:
    """尝试撮合单笔订单(下单时与行情 tick 时调用)。返回刷新后的订单。"""
    order = Order.objects.select_for_update().select_related("stock").get(pk=order.pk)
    if not order.is_active:
        return order
    stock = Stock.objects.select_for_update().get(pk=order.stock_id)
    market_price = stock.price
    if market_price <= 0 or not _crossed(order, market_price):
        return order

    remaining = order.remaining_quantity
    if order.order_type == Order.OrderType.MARKET:
        fill_qty = remaining  # 市价单按当前价全额成交
    else:
        fill_qty = min(remaining, _liquidity(stock, order))
    if fill_qty <= 0:
        return order

    _settle_fill(order, stock, fill_qty, market_price)
    order.refresh_from_db()
    return order


def match_pending_orders(stock) -> None:
    """行情 tick 后驱动:按时间先后撮合该标的的全部在途订单。单笔失败不影响其他。"""
    pks = list(
        Order.objects.filter(stock=stock, status__in=Order.ACTIVE_STATUSES)
        .order_by("created_at")
        .values_list("pk", flat=True)
    )
    for pk in pks:
        try:
            try_match_order(Order(pk=pk))
        except Exception:
            logger.exception("撮合订单 #%s 失败", pk)


def _settle_fill(order: Order, stock: Stock, fill_qty: int, fill_price: Decimal) -> None:
    """结算一笔成交:更新订单、写成交回报、调整资金与持仓。须在事务与行锁内调用。"""
    fill_price = Decimal(fill_price).quantize(TWO_PLACES)
    amount = fill_price * fill_qty
    cash = CashAccount.objects.select_for_update().get(user=order.user)

    remaining_after = order.remaining_quantity - fill_qty
    new_frozen = Decimal("0.00")

    if order.side == Order.Side.BUY:
        fee = fees.buy_fee(amount)
        cost = amount + fee
        old_frozen = order.frozen_amount
        if remaining_after > 0 and order.order_type == Order.OrderType.LIMIT:
            rest_amount = order.price * remaining_after
            new_frozen = money(rest_amount + fees.buy_fee(rest_amount))
        # 成交价不劣于委托价,退款恒 >= 0;防御性下限保护
        refund = max(old_frozen - cost - new_frozen, Decimal("0.00"))
        cash.balance += refund
        cash.frozen_cash = max(cash.frozen_cash - old_frozen + new_frozen, Decimal("0.00"))
        _apply_buy_fill(order.user, stock, fill_qty, fill_price)
    else:
        fee = fees.sell_fee(amount)
        cash.balance += amount - fee
        _apply_sell_fill(order.user, stock, fill_qty)

    cash.save(update_fields=["balance", "frozen_cash", "updated_at"])
    Trade.objects.create(
        order=order, user=order.user, stock=stock, side=order.side,
        quantity=fill_qty, price=fill_price, amount=amount, fee=fee,
    )

    total_filled = order.filled_quantity + fill_qty
    total_amount = order.avg_fill_price * order.filled_quantity + fill_price * fill_qty
    order.filled_quantity = total_filled
    order.avg_fill_price = (total_amount / total_filled).quantize(TWO_PLACES, ROUND_HALF_UP)

    if total_filled >= order.quantity:
        order.status = Order.Status.FILLED
        order.frozen_amount = Decimal("0.00")
        order.frozen_quantity = 0
    else:
        order.status = Order.Status.PARTIAL_FILLED
        if order.side == Order.Side.BUY:
            order.frozen_amount = new_frozen
        else:
            order.frozen_quantity = order.quantity - total_filled
    order.save()


def _apply_buy_fill(user, stock, qty: int, price: Decimal) -> None:
    """买入成交:更新/创建持仓并重算摊薄成本。"""
    try:
        pos = Position.objects.select_for_update().get(user=user, stock=stock)
    except Position.DoesNotExist:
        try:
            Position.objects.create(
                user=user, stock=stock, quantity=qty, available_quantity=qty, avg_price=price,
            )
            return
        except IntegrityError:  # 并发首买兜底
            pos = Position.objects.select_for_update().get(user=user, stock=stock)

    old_qty = pos.quantity
    pos.quantity = old_qty + qty
    pos.available_quantity = pos.available_quantity + qty
    pos.avg_price = ((pos.avg_price * old_qty + price * qty) / pos.quantity).quantize(AVG_FOUR_PLACES, ROUND_HALF_UP)
    pos.save(update_fields=["quantity", "available_quantity", "avg_price", "updated_at"])


def _apply_sell_fill(user, stock, qty: int) -> None:
    """卖出成交:扣减持仓(available 在报单时已冻结,成交即消化冻结额度)。"""
    pos = Position.objects.select_for_update().get(user=user, stock=stock)
    pos.quantity -= qty
    if pos.quantity <= 0:
        pos.delete()
    else:
        pos.save(update_fields=["quantity", "updated_at"])
