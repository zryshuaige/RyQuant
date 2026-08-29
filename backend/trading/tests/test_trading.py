"""下单校验、买卖全链路、撤单、费用与冻结资金。"""
from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from trading.models import CashAccount, Order, Trade
from trading.services import matching
from trading.services.fees import buy_fee, sell_fee

from .base import BaseAPITestCase, make_stock


def full_liquidity(stock, order):
    return 10 ** 9


class OrderValidationTests(BaseAPITestCase):
    def post_order(self, payload):
        return self.client.post("/api/order/", payload, format="json")

    def test_requires_auth(self):
        self.anon()
        resp = self.post_order({"stock_id": self.stock.pk, "side": "BUY", "quantity": 100, "price": 13.88})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_stock_ref(self):
        self.auth()
        resp = self.post_order({"side": "BUY", "quantity": 100, "price": 13.88})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", resp.data)

    def test_unknown_symbol_returns_400_not_404(self):
        self.auth()
        resp = self.post_order({"symbol": "999999", "side": "BUY", "quantity": 100, "price": 10})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lot_size_rule(self):
        self.auth()
        resp = self.post_order({"stock_id": self.stock.pk, "side": "BUY", "quantity": 150, "price": 13.88})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("100 的整数倍", str(resp.data["detail"]))

    def test_star_market_lot_200(self):
        self.auth()
        star = make_stock("688981", "中芯国际", price="99.00", prev_close="95.00")
        resp = self.post_order({"stock_id": star.pk, "side": "BUY", "quantity": 100, "price": 99})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("200 的整数倍", str(resp.data["detail"]))

    def test_price_outside_limit_band(self):
        self.auth()
        resp = self.post_order({"stock_id": self.stock.pk, "side": "BUY", "quantity": 100, "price": 20})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("涨跌停", str(resp.data["detail"]))

    def test_bad_side(self):
        self.auth()
        resp = self.post_order({"stock_id": self.stock.pk, "side": "HOLD", "quantity": 100, "price": 13.88})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_insufficient_funds(self):
        self.auth()
        resp = self.post_order({"stock_id": self.stock.pk, "side": "BUY", "quantity": 100000, "price": 13.88})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("可用资金不足", str(resp.data["detail"]))
        account = CashAccount.objects.get(user=self.user)
        self.assertEqual(account.frozen_cash, Decimal("0.00"))  # 失败不产生冻结


class BuyFlowTests(BaseAPITestCase):
    def test_limit_buy_at_market_fills_immediately(self):
        self.auth()
        with patch("trading.services.matching._liquidity", full_liquidity):
            resp = self.post_order_buy()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        order = resp.data["order"]
        self.assertEqual(order["status"], "FILLED")
        self.assertEqual(order["filled_quantity"], 200)
        account = CashAccount.objects.get(user=self.user)
        cost = Decimal("13.88") * 200
        self.assertEqual(account.balance, Decimal("100000.00") - cost - buy_fee(cost))
        self.assertEqual(account.frozen_cash, Decimal("0.00"))

    def post_order_buy(self, **over):
        payload = {"stock_id": self.stock.pk, "side": "BUY", "quantity": 200, "price": 13.88}
        payload.update(over)
        return self.client.post("/api/order/", payload, format="json")

    def test_limit_buy_below_market_stays_pending_and_freezes(self):
        self.auth()
        resp = self.post_order_buy(price=13.00)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        order = resp.data["order"]
        self.assertEqual(order["status"], "PENDING")
        account = CashAccount.objects.get(user=self.user)
        est = Decimal("13.00") * 200
        self.assertEqual(account.frozen_cash, est + buy_fee(est))
        self.assertEqual(order["frozen_amount"], float(est + buy_fee(est)))
        self.assertEqual(account.balance, Decimal("100000.00") - est - buy_fee(est))

    def test_response_shape_contract(self):
        self.auth()
        with patch("trading.services.matching._liquidity", full_liquidity):
            resp = self.post_order_buy()
        self.assertEqual(set(resp.data.keys()), {"order", "cash"})
        self.assertEqual(set(resp.data["cash"].keys()), {"balance", "frozen_cash", "is_vip"})
        self.assertIn("status", resp.data["order"])
        import json
        body = json.loads(resp.content)
        self.assertIsInstance(body["cash"]["balance"], float)  # 线上 JSON 保持数字类型

    def test_market_order_fills_at_current_price(self):
        self.auth()
        resp = self.client.post("/api/order/", {
            "stock_id": self.stock.pk, "side": "BUY", "quantity": 100, "order_type": "MARKET",
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["order"]["status"], "FILLED")
        self.assertEqual(resp.data["order"]["price"], None)


class SellFlowTests(BaseAPITestCase):
    def test_sell_full_cycle(self):
        self.give_position(self.user, self.stock, quantity=200, price="13.00")
        self.auth()
        with patch("trading.services.matching._liquidity", full_liquidity):
            resp = self.client.post("/api/order/", {
                "stock_id": self.stock.pk, "side": "SELL", "quantity": 200, "price": 13.88,
            }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["order"]["status"], "FILLED")
        account = CashAccount.objects.get(user=self.user)
        amount = Decimal("13.88") * 200
        self.assertEqual(account.balance, Decimal("100000.00") + amount - sell_fee(amount))

    def test_sell_freezes_available(self):
        self.give_position(self.user, self.stock, quantity=300)
        # 200 股卖单在途(价格高于市价,未成交),再卖 200 应被拒(可用只剩 100)
        self.sell(self.user, self.stock, 200, price=Decimal("14.00"))
        self.auth()
        resp = self.client.post("/api/order/", {
            "stock_id": self.stock.pk, "side": "SELL", "quantity": 200, "price": 13.88,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("可用持仓不足", str(resp.data["detail"]))

    def test_odd_lot_only_full_close(self):
        self.give_position(self.user, self.stock, quantity=150)
        self.auth()
        # 非整手且非清仓 → 拒绝
        resp = self.client.post("/api/order/", {
            "stock_id": self.stock.pk, "side": "SELL", "quantity": 50, "price": 13.88,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # 一次性清仓 150 股 → 允许
        with patch("trading.services.matching._liquidity", full_liquidity):
            resp = self.client.post("/api/order/", {
                "stock_id": self.stock.pk, "side": "SELL", "quantity": 150, "price": 13.88,
            }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["order"]["status"], "FILLED")


class CancelTests(BaseAPITestCase):
    def test_cancel_pending_buy_refunds_frozen(self):
        self.auth()
        with patch("trading.services.matching._liquidity", full_liquidity):
            resp = self.client.post("/api/order/", {
                "stock_id": self.stock.pk, "side": "BUY", "quantity": 200, "price": 13.00,
            }, format="json")
        order_id = resp.data["order"]["id"]
        resp = self.client.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["order"]["status"], "CANCELLED")
        account = CashAccount.objects.get(user=self.user)
        self.assertEqual(account.balance, Decimal("100000.00"))
        self.assertEqual(account.frozen_cash, Decimal("0.00"))

    def test_cancel_filled_order_rejected(self):
        self.auth()
        with patch("trading.services.matching._liquidity", full_liquidity):
            resp = self.client.post("/api/order/", {
                "stock_id": self.stock.pk, "side": "BUY", "quantity": 200, "price": 13.88,
            }, format="json")
        order_id = resp.data["order"]["id"]
        resp = self.client.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_cancel_others_order(self):
        self.auth(user=self.other)
        resp = self.client.post("/api/order/", {
            "stock_id": self.stock.pk, "side": "BUY", "quantity": 200, "price": 13.00,
        }, format="json")
        # other 用户自己下的单;切换回 user 无法撤销
        other_order_id = resp.data["order"]["id"]
        self.auth(user=self.user)
        resp = self.client.post(f"/api/orders/{other_order_id}/cancel/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_sell_unfreezes_position(self):
        self.give_position(self.user, self.stock, quantity=300)
        order = self.sell(self.user, self.stock, 200, price=Decimal("14.00"))  # 高于市价,保持挂单
        self.assertTrue(order.is_active)
        self.auth()
        resp = self.client.post(f"/api/orders/{order.pk}/cancel/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        from trading.models import Position

        pos = Position.objects.get(user=self.user, stock=self.stock)
        self.assertEqual(pos.available_quantity, 300)
