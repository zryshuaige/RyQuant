"""持仓汇总与行情接口契约。"""
from decimal import Decimal

from rest_framework import status

from trading.models import NewsItem

from .base import BaseAPITestCase, make_stock, seed_daily_candles
from django.utils import timezone


class PositionsTests(BaseAPITestCase):
    def test_positions_envelope_and_math(self):
        self.give_position(self.user, self.stock, quantity=200, price="13.00")
        self.auth()
        resp = self.client.get("/api/positions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        for key in ("cash", "total_market_value", "total_unrealized_pl", "details"):
            self.assertIn(key, data)
        self.assertEqual(set(data["cash"].keys()), {"balance", "frozen_cash", "is_vip"})
        detail = data["details"][0]
        for key in ("position_id", "stock_id", "symbol", "name", "quantity", "available_quantity",
                    "avg_price", "market_price", "market_value", "unrealized_pl"):
            self.assertIn(key, detail)
        self.assertEqual(detail["market_value"], 13.88 * 200)
        self.assertEqual(detail["unrealized_pl"], round((13.88 - 13.00) * 200, 2))
        self.assertEqual(data["total_market_value"], 2776.0)
        self.assertEqual(data["total_unrealized_pl"], 176.0)

    def test_positions_requires_auth(self):
        self.anon()
        resp = self.client.get("/api/positions/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class MarketApiTests(BaseAPITestCase):
    def test_stocks_contract(self):
        resp = self.client.get("/api/stocks/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        stock = resp.data[0]
        for key in ("id", "symbol", "name", "price", "prev_close", "change", "change_pct",
                    "limit_pct", "lot_size", "is_active"):
            self.assertIn(key, stock)

    def test_stocks_exclude_indices(self):
        make_stock("sh000001", "上证指数", price="3950.00", prev_close="3956.00",
                   active=False, kind="index")
        resp = self.client.get("/api/stocks/")
        symbols = {s["symbol"] for s in resp.data}
        self.assertNotIn("sh000001", symbols)
        self.assertIn(self.stock.symbol, symbols)

    def test_indices_shape(self):
        resp = self.client.get("/api/indices/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        indices = resp.data["indices"]
        self.assertEqual(len(indices), 3)
        for idx in indices:
            for key in ("name", "current", "prev_close", "change", "change_pct"):
                self.assertIn(key, idx)
        names = {i["name"] for i in indices}
        self.assertEqual(names, {"上证指数", "深证成指", "创业板指"})

    def test_indices_from_real_index_rows(self):
        make_stock("sh000001", "上证指数", price="3952.18", prev_close="3956.57",
                   active=False, kind="index")
        resp = self.client.get("/api/indices/")
        indices = resp.data["indices"]
        real = next(i for i in indices if i["symbol"] == "sh000001")
        self.assertEqual(real["name"], "上证指数")
        self.assertEqual(real["current"], 3952.18)
        self.assertEqual(real["prev_close"], 3956.57)
        self.assertEqual(real["change_pct"], round((3952.18 - 3956.57) / 3956.57 * 100, 2))

    def test_cannot_order_index(self):
        from trading.services.errors import BusinessError

        index = make_stock("sh000001", "上证指数", price="3952.00", prev_close="3956.00",
                           active=False, kind="index")
        with self.assertRaises(BusinessError):
            self.buy(self.user, index, 100, price=Decimal("3952.00"))

    def test_kline_contract(self):
        seed_daily_candles(self.stock, count=80, seed="kline")
        resp = self.client.get("/api/kline/", {"symbol": self.stock.symbol, "limit": 30})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertIn("timestamps", data)
        self.assertIn("klines", data)
        self.assertEqual(len(data["klines"]), 30)
        candle = data["klines"][0]
        self.assertEqual(len(candle), 4)  # [open, close, low, high]
        self.assertEqual(data["timestamps"][0] < data["timestamps"][-1], True)

    def test_kline_unknown_symbol_400(self):
        resp = self.client.get("/api/kline/", {"symbol": "nope"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kline_bad_limit_400(self):
        resp = self.client.get("/api/kline/", {"symbol": self.stock.symbol, "limit": "abc"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sectors_deterministic(self):
        r1 = self.client.get("/api/sectors/").data
        r2 = self.client.get("/api/sectors/").data
        self.assertEqual(r1, r2)  # 同一天内稳定
        self.assertEqual(len(r1["sectors"]), 3)

    def test_news_contract(self):
        now = timezone.now()
        NewsItem.objects.create(title="标题", summary="摘要", published_at=now)
        resp = self.client.get("/api/news/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)
        self.assertEqual(resp.data[0]["title"], "标题")


class FavoritesTests(BaseAPITestCase):
    def test_favorite_crud(self):
        self.auth()
        resp = self.client.post("/api/favorites/", {"stock_id": self.stock.pk}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        fav_id = resp.data["id"]
        self.assertEqual(resp.data["stock"]["symbol"], self.stock.symbol)

        resp = self.client.get("/api/favorites/")
        self.assertEqual(len(resp.data), 1)

        resp = self.client.delete(f"/api/favorites/{fav_id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_delete_others_favorite(self):
        self.auth(user=self.other)
        resp = self.client.post("/api/favorites/", {"stock_id": self.stock.pk}, format="json")
        fav_id = resp.data["id"]
        self.auth(user=self.user)
        resp = self.client.delete(f"/api/favorites/{fav_id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
