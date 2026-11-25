"""自选跟踪:加入以来收益、同期上证、超额收益与周末吸附。"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from trading.models import Candle, Favorite, Stock
from trading.services.watchlist import favorites_summary

from .base import BaseAPITestCase, make_stock


def _candle(stock, day, close):
    Candle.objects.create(
        stock=stock, period=Candle.Period.DAY,
        time=timezone.make_aware(datetime(day.year, day.month, day.day)),
        open=Decimal(str(close)), high=Decimal(str(close)),
        low=Decimal(str(close)), close=Decimal(str(close)), volume=1000,
        source=Candle.Source.REAL,
    )


class FavoritesSummaryTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.today = timezone.localdate()
        self.index = make_stock(symbol="sh000001", name="上证指数", price="3030.00",
                                prev_close="3000.00", active=False, kind=Stock.Kind.INDEX)
        self.stock.price = Decimal("110.00")
        self.stock.prev_close = Decimal("100.00")
        self.stock.save()
        self.joined = self.today - timedelta(days=10)
        _candle(self.stock, self.joined, 100)
        _candle(self.stock, self.today, 110)
        _candle(self.index, self.joined, 3000)
        _candle(self.index, self.today, 3030)
        self.fav = Favorite.objects.create(user=self.user, stock=self.stock)
        Favorite.objects.filter(pk=self.fav.pk).update(
            created_at=timezone.make_aware(datetime.combine(self.joined, time(12)))
        )

    def test_summary_returns_since_join_and_excess(self):
        self.auth()
        resp = self.client.get("/api/favorites/summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        item = data["items"][0]
        self.assertAlmostEqual(item["return_pct"], 10.0, places=2)
        self.assertAlmostEqual(item["benchmark_return_pct"], 1.0, places=2)
        self.assertAlmostEqual(item["excess_pct"], 9.0, places=2)
        self.assertEqual(item["stock"]["symbol"], "000001")
        self.assertEqual(data["beat_count"], 1)
        self.assertEqual(data["best"]["name"], "平安银行")
        self.assertTrue(item["series"])
        self.assertIn("stock_pct", item["series"][0])

    def test_empty_favorites(self):
        self.auth(user=self.other)
        data = self.client.get("/api/favorites/summary/").json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["items"], [])
        self.assertIsNone(data["best"])

    def test_requires_auth(self):
        self.anon()
        resp = self.client.get("/api/favorites/summary/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_weekend_join_snaps_to_next_trading_day(self):
        # 找一个周六作为加入日,加入价取其后首个交易日(周一)收盘
        saturday = self.today - timedelta(days=10)
        while saturday.weekday() != 5:
            saturday -= timedelta(days=1)
        monday = saturday + timedelta(days=2)
        Candle.objects.filter(stock=self.stock).delete()
        Candle.objects.filter(stock=self.index).delete()
        _candle(self.stock, monday, 101)
        _candle(self.stock, self.today, 111)
        _candle(self.index, monday, 3000)
        _candle(self.index, self.today, 3030)
        Favorite.objects.filter(pk=self.fav.pk).update(
            created_at=timezone.make_aware(datetime.combine(saturday, time(12)))
        )
        data = favorites_summary(self.user)
        item = data["items"][0]
        self.assertEqual(item["joined_at"], saturday.isoformat())
        self.assertEqual(item["join_date"], monday.isoformat())
        self.assertAlmostEqual(item["join_price"], 101.0, places=2)