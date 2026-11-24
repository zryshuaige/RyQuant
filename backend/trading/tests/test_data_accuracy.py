"""数据准确性:腾讯完整格式 parser / 真实报价 tick / 离线回退 / 日 K 增量刷新 / AI 上下文 / 板块真实计算 / 来源标注。"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from trading.models import AIConversation, AIMessage, Candle, Stock
from trading.services import market_sim
from trading.services.trading import get_cash_account

from .base import BaseAPITestCase, make_stock, seed_daily_candles

# 2026-11-24 录制的腾讯完整格式真实响应(字段位:3现价 4昨收 6量(手) 31涨跌 32涨跌% 33高 34低)
FIXTURE_SH600519 = (
    'v_sh600519="1~贵州茅台~600519~1460.00~1439.00~1425.00~42924~23737~19187~1458.88~5~'
    '1458.51~1~1458.50~1~1458.47~1~1458.11~1~1460.00~108~1460.11~1~1460.26~1~1460.28~1~'
    '1460.50~1~~20261124161452~21.00~1.46~1463.26~1420.00~1460.00/42924/6214192454~42924~'
    '621419~0.34~22.21~~1463.26~1420.00~3.01~18251.19~18251.19~6.73~1582.90~1295.10~0.93~'
    '-103~1447.72~21.23~22.17~~~-0.07~621419.2454~87.6000~6~   A~GP-A~8.22~0.'
)
FIXTURE_SH000001 = (
    'v_sh000001="1~上证指数~000001~3548.37~3538.95~3567.84~493526296~0~0~0.00~0~0.00~0~'
    '0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~~20261124161427~9.42~0.27~'
    '3585.22~3539.01~3548.37/493526296/771861010309~493526296~77186101~1.01~16.24~~'
    '3585.22~3539.01~1.31~559279.51~620219.97~0.00~-1~-1~1.08~0~3561.59~~~~~~'
    '77186101.0309~0.0000~0~ ~ZS~-10.59~-1.01~~~~4258.86~3476.65~-3.15~-2.74~-8.59~486618663162'
)


def _resp(text):
    r = mock.Mock()
    r.text = text
    return r


class QuoteParserTests(SimpleTestCase):
    def test_full_format_fields(self):
        with mock.patch("requests.get", return_value=_resp(FIXTURE_SH600519 + ";" + FIXTURE_SH000001)):
            quotes = market_sim.fetch_realtime_quotes(["600519", "sh000001"])
        q = quotes["600519"]
        self.assertEqual(q["current"], Decimal("1460.00"))
        self.assertEqual(q["prev_close"], Decimal("1439.00"))  # 旧 s_ 映射曾把涨跌额当昨收
        self.assertEqual(q["change"], Decimal("21.00"))
        self.assertEqual(q["change_pct"], Decimal("1.46"))
        self.assertEqual(q["high"], Decimal("1463.26"))
        self.assertEqual(q["low"], Decimal("1420.00"))
        self.assertEqual(q["volume"], 4292400)  # 手 → 股
        self.assertEqual(quotes["sh000001"]["prev_close"], Decimal("3538.95"))
        self.assertEqual(quotes["sh000001"]["change_pct"], Decimal("0.27"))

    def test_inconsistent_pct_rejected(self):
        bad = FIXTURE_SH600519.replace("~1.46~", "~9.99~")
        with mock.patch("requests.get", return_value=_resp(bad)):
            self.assertEqual(market_sim.fetch_realtime_quotes(["600519"]), {})

    def test_network_failure_returns_empty(self):
        with mock.patch("requests.get", side_effect=OSError("boom")):
            self.assertEqual(market_sim.fetch_realtime_quotes(["600519"]), {})


class RealTickTests(BaseAPITestCase):
    def tearDown(self):
        market_sim._last_refresh_date = None

    def test_stock_tick_uses_real_quote(self):
        quote = {
            "current": Decimal("14.00"), "prev_close": Decimal("13.88"),
            "change": Decimal("0.12"), "change_pct": Decimal("0.86"),
            "high": Decimal("14.10"), "low": Decimal("13.80"), "volume": 100000,
        }
        with mock.patch.object(market_sim, "fetch_realtime_quotes", return_value={"000001": quote}), \
                mock.patch.object(market_sim, "_maybe_refresh_daily"):
            market_sim.tick()
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.price, Decimal("14.00"))
        self.assertEqual(self.stock.prev_close, Decimal("13.88"))
        self.assertEqual(self.stock.quote_source, Stock.QuoteSource.REAL)
        self.assertIsNotNone(self.stock.real_quote_at)
        day = Candle.objects.get(stock=self.stock, period=Candle.Period.DAY,
                                 time=market_sim._day_start(timezone.localtime()))
        self.assertEqual(day.source, Candle.Source.REAL)
        self.assertEqual(day.high, Decimal("14.10"))
        self.assertEqual(day.low, Decimal("13.80"))

    def test_stock_tick_fallback_sim(self):
        with mock.patch.object(market_sim, "fetch_realtime_quotes", return_value={}), \
                mock.patch.object(market_sim, "_maybe_refresh_daily"):
            market_sim.tick()
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quote_source, Stock.QuoteSource.SIM)

    def test_daily_refresh_upserts_real_bar(self):
        now = timezone.make_aware(datetime(2026, 11, 24, 10, 0))  # 周二
        yesterday = (now.date() - timedelta(days=1)).strftime("%Y-%m-%d")
        rows = [(yesterday, Decimal("13.5"), Decimal("13.8"), Decimal("13.9"), Decimal("13.4"), 12345)]
        with mock.patch.object(market_sim, "fetch_real_daily_tencent", return_value=rows) as fetch:
            market_sim._maybe_refresh_daily(now, [self.stock])
            self.assertEqual(fetch.call_count, 1)
            # 同日再次 tick 不重复抓取
            market_sim._maybe_refresh_daily(now, [self.stock])
            self.assertEqual(fetch.call_count, 1)
        c = Candle.objects.get(stock=self.stock, period=Candle.Period.DAY,
                               time=timezone.make_aware(datetime(2026, 11, 23)))
        self.assertEqual(c.source, Candle.Source.REAL)
        self.assertEqual(c.close, Decimal("13.8"))

    def test_daily_refresh_skips_weekend(self):
        now = timezone.make_aware(datetime(2026, 11, 22, 10, 0))  # 周日
        with mock.patch.object(market_sim, "fetch_real_daily_tencent", side_effect=AssertionError("weekend")) as fetch:
            market_sim._maybe_refresh_daily(now, [self.stock])
            fetch.assert_not_called()


class AiContextTests(BaseAPITestCase):
    def test_history_uses_latest_messages(self):
        cash = get_cash_account(self.user)
        cash.is_vip = True
        cash.save(update_fields=["is_vip"])
        conv = AIConversation.objects.create(user=self.user, title="t")
        for i in range(25):
            AIMessage.objects.create(conversation=conv, sender="user" if i % 2 == 0 else "bot",
                                     content=f"msg{i}")
        captured = {}

        def fake_reply(user, text, history=None):
            captured["history"] = history
            return "ok"

        self.auth()
        with mock.patch("trading.api.ai.get_ai_reply", side_effect=fake_reply):
            resp = self.client.post("/api/ai/query/",
                                    {"text": "新问题", "conversation_id": conv.id}, format="json")
        self.assertEqual(resp.status_code, 200)
        h = captured["history"]
        self.assertEqual(len(h), 20)
        self.assertEqual(h[0]["content"], "msg5")   # 最旧 20 条的 bug 曾从 msg0 开始
        self.assertEqual(h[-1]["content"], "msg24")


class SectorTests(BaseAPITestCase):
    def test_sectors_computed_from_members(self):
        other = make_stock(symbol="601318", name="中国平安", price="42.30", prev_close="42.00")
        seed_daily_candles(self.stock, count=10)
        seed_daily_candles(other, count=10)
        self.anon()
        resp = self.client.get("/api/sectors/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        fin = next(s for s in data["sectors"] if s["name"] == "金融")
        expect = round((float(self.stock.change_pct) + float(other.change_pct)) / 2, 2)
        self.assertEqual(fin["change_pct"], expect)
        self.assertEqual(len(fin["values"]), 10)
        self.assertEqual(len(data["labels"]), 10)


class SourceLabelTests(BaseAPITestCase):
    def test_stocks_and_kline_expose_source(self):
        seed_daily_candles(self.stock, count=5)
        self.anon()
        r = self.client.get("/api/stocks/")
        self.assertEqual(r.json()[0]["quote_source"], "sim")
        k = self.client.get("/api/kline/", {"symbol": "000001", "period": "1day"})
        self.assertEqual(k.json()["sources"], ["sim"] * 5)
        self.assertEqual(k.json()["quote_source"], "sim")