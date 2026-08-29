"""撮合引擎:价格穿越、部分成交、tick 驱动、冻结结算。"""
from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from trading.models import CashAccount, Order
from trading.services import matching
from trading.services.fees import buy_fee

from .base import BaseAPITestCase


def lots(n):
    def _liq(stock, order):
        return n * stock.lot_size
    return _liq


class MatchingEngineTests(BaseAPITestCase):
    def test_uncrossed_order_stays_pending(self):
        order = self.buy(self.user, self.stock, 200, price=Decimal("13.00"))  # 低于市价
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_crossed_order_fills_at_market_price(self):
        with patch("trading.services.matching._liquidity", lambda s, o: 10 ** 9):
            order = self.buy(self.user, self.stock, 200, price=Decimal("14.50"))  # 高于市价
        self.assertEqual(order.status, Order.Status.FILLED)
        self.assertEqual(order.avg_fill_price, Decimal("13.88"))  # 成交价=市价(优于委托价)
        account = CashAccount.objects.get(user=self.user)
        cost = Decimal("13.88") * 200
        self.assertEqual(account.balance, Decimal("100000.00") - cost - buy_fee(cost))

    def test_partial_fill_then_complete_on_next_tick(self):
        with patch("trading.services.matching._liquidity", lots(1)):  # 只有 1 手深度
            order = self.buy(self.user, self.stock, 300, price=Decimal("13.88"))
        self.assertEqual(order.status, Order.Status.PARTIAL_FILLED)
        self.assertEqual(order.filled_quantity, 100)
        self.assertEqual(order.trades.count(), 1)

        account = CashAccount.objects.get(user=self.user)
        frozen_after_partial = account.frozen_cash
        self.assertGreater(frozen_after_partial, 0)  # 剩余 200 股仍在冻结

        # 行情 tick 驱动剩余撮合
        with patch("trading.services.matching._liquidity", lots(10)):
            matching.match_pending_orders(self.stock)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.FILLED)
        self.assertEqual(order.filled_quantity, 300)
        account.refresh_from_db()
        self.assertEqual(account.frozen_cash, Decimal("0.00"))
        self.assertEqual(order.trades.count(), 2)

    def test_sell_partial_fill_keeps_frozen_quantity(self):
        self.give_position(self.user, self.stock, quantity=500)
        with patch("trading.services.matching._liquidity", lots(1)):
            order = self.sell(self.user, self.stock, 500, price=Decimal("13.88"))
        self.assertEqual(order.status, Order.Status.PARTIAL_FILLED)
        self.assertEqual(order.frozen_quantity, 400)

    def test_match_skips_crossed_direction(self):
        # 卖单价格高于市价(且在涨跌停范围内)→ 不成交
        self.give_position(self.user, self.stock, quantity=200)
        order = self.sell(self.user, self.stock, 200, price=Decimal("14.20"))
        self.assertEqual(order.status, Order.Status.PENDING)


class OrdersApiTests(BaseAPITestCase):
    def test_orders_list_filters(self):
        with patch("trading.services.matching._liquidity", lambda s, o: 10 ** 9):
            self.buy(self.user, self.stock, 200, price=Decimal("13.88"))
        self.buy(self.user, self.stock, 200, price=Decimal("12.00"))  # PENDING
        self.auth()
        resp = self.client.get("/api/orders/?status=PENDING")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        orders = resp.data["orders"]
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["status"], "PENDING")
        resp = self.client.get("/api/orders/?active=1")
        self.assertEqual(len(resp.data["orders"]), 1)

    def test_trades_list(self):
        self.buy(self.user, self.stock, 200, price=Decimal("13.88"))
        self.auth()
        resp = self.client.get("/api/trades/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["trades"]), 1)
        trade = resp.data["trades"][0]
        for key in ("id", "order", "stock", "side", "quantity", "price", "amount", "fee", "created_at"):
            self.assertIn(key, trade)
