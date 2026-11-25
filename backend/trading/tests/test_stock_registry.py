"""标的注册表:本地/远程检索、按需落库、历史行情真实与模拟回退。"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from trading.models import Candle, Stock
from trading.services import stock_registry
from trading.services.errors import BusinessError

from .base import BaseAPITestCase, make_stock


def _real_rows(count=70, base=100.0):
    today = timezone.localdate()
    rows = []
    for i in range(count):
        day = today - timedelta(days=count - i)
        price = base + i * 0.1
        rows.append((day.strftime("%Y%m%d"), Decimal(str(price)), Decimal(str(price + 0.2)),
                     Decimal(str(price + 0.4)), Decimal(str(price - 0.2)), 100_000))
    return rows


class SearchTests(BaseAPITestCase):
    def test_local_search_by_name_and_code(self):
        self.anon()
        by_code = self.client.get("/api/stocks/search/", {"q": "000001"}).json()
        self.assertTrue(by_code["results"])
        self.assertEqual(by_code["results"][0]["name"], "平安银行")
        self.assertTrue(by_code["results"][0]["in_db"])

        by_name = self.client.get("/api/stocks/search/", {"q": "平安"}).json()
        self.assertTrue(any(item["symbol"] == "000001" for item in by_name["results"]))

    def test_local_search_supports_prefixed_code(self):
        self.anon()
        data = self.client.get("/api/stocks/search/", {"q": "sz000001"}).json()
        self.assertTrue(any(item["symbol"] == "000001" for item in data["results"]))

    @patch("requests.get")
    def test_remote_search_parses_smartbox(self, get):
        self.anon()
        resp = Mock()
        resp.text = r'v_hint="sh~600036~招商银行~zsyh~GP-A~...^sz~000858~五粮液~wly~GP-A~..."'
        resp.encoding = "gbk"
        get.return_value = resp
        data = self.client.get("/api/stocks/search/", {"q": "招商"}).json()
        item = next(x for x in data["results"] if x["code"] == "600036")
        self.assertEqual(item["name"], "招商银行")
        self.assertEqual(item["symbol"], "sh600036")
        self.assertFalse(item["in_db"])
        self.assertTrue(data["remote_available"])

    @patch("requests.get", side_effect=RuntimeError("offline"))
    def test_remote_failure_keeps_local_and_flags(self, _get):
        self.anon()
        data = self.client.get("/api/stocks/search/", {"q": "平安"}).json()
        self.assertTrue(data["results"])
        self.assertFalse(data["remote_available"])


class ResolveTests(BaseAPITestCase):
    def test_resolve_requires_auth(self):
        self.anon()
        resp = self.client.post("/api/stocks/resolve/", {"symbol": "600036"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch.object(stock_registry, "ensure_daily_history", return_value="existing")
    def test_resolve_existing_is_idempotent(self, _ensure):
        self.auth()
        before = Stock.objects.count()
        resp = self.client.post("/api/stocks/resolve/", {"symbol": "000001"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.json()["created"])
        self.assertEqual(Stock.objects.count(), before)

    @patch.object(stock_registry, "ensure_daily_history", return_value="real")
    @patch.object(stock_registry, "_fetch_quote")
    def test_resolve_new_code_creates_stock(self, quote, _ensure):
        quote.return_value = {
            "name": "招商银行", "current": Decimal("38.50"), "prev_close": Decimal("38.00"),
        }
        self.auth()
        resp = self.client.post("/api/stocks/resolve/", {"symbol": "600036"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.json()
        self.assertTrue(data["created"])
        self.assertEqual(data["name"], "招商银行")
        self.assertEqual(data["history_source"], "real")
        self.assertTrue(Stock.objects.filter(symbol="600036").exists())

    @patch.object(stock_registry, "_fetch_quote", return_value={})
    def test_resolve_unknown_code_rejected(self, _quote):
        self.auth()
        resp = self.client.post("/api/stocks/resolve/", {"symbol": "600999"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_symbol_rejected(self):
        with self.assertRaises(BusinessError):
            stock_registry.resolve_stock("not-a-code")

    def test_index_resolve_rejected(self):
        make_stock(symbol="sh000001", name="上证指数", price="3000.00",
                   prev_close="2990.00", active=False, kind=Stock.Kind.INDEX)
        with self.assertRaises(BusinessError):
            stock_registry.resolve_stock("上证指数")


class HistoryTests(TestCase):
    @patch.object(stock_registry, "fetch_real_daily_tencent", return_value=None)
    @patch.object(stock_registry, "fetch_real_daily_netease", return_value=None)
    def test_sim_fallback_creates_business_days(self, _netease, _tencent):
        stock = make_stock(symbol="600036", name="招商银行", price="38.50", prev_close="38.00")
        source = stock_registry.ensure_daily_history(stock)
        self.assertEqual(source, "sim")
        candles = Candle.objects.filter(stock=stock, period=Candle.Period.DAY)
        self.assertEqual(candles.count(), 250)
        self.assertTrue(all(c.source == Candle.Source.SIM for c in candles))
        self.assertEqual(Candle.objects.filter(stock=stock, time__week_day=7).count(), 0)

    @patch.object(stock_registry, "fetch_real_daily_netease", return_value=None)
    @patch.object(stock_registry, "fetch_real_daily_tencent")
    def test_real_history_written_with_real_source(self, tencent, _netease):
        tencent.return_value = _real_rows()
        stock = make_stock(symbol="600036", name="招商银行", price="0.00", prev_close="0.00")
        source = stock_registry.ensure_daily_history(stock)
        self.assertEqual(source, "real")
        stock.refresh_from_db()
        self.assertGreater(stock.price, 0)
        self.assertGreater(stock.prev_close, 0)
        candles = Candle.objects.filter(stock=stock, period=Candle.Period.DAY)
        self.assertEqual(candles.count(), 70)
        self.assertTrue(all(c.source == Candle.Source.REAL for c in candles))