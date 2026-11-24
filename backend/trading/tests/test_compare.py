"""策略有效性:引擎风险指标数学 / 跨策略对比排名与 OOS / 对比端点权限与契约。"""
import math
from datetime import timedelta

from django.utils import timezone

from trading.models import Stock
from trading.services.quant.compare import compare_strategies
from trading.services.quant.engine import run_backtest

from .base import BaseAPITestCase, make_stock, seed_daily_candles


def _payload(closes):
    day = timezone.localdate() - timedelta(days=len(closes))
    out = []
    for i, c in enumerate(closes):
        d = day + timedelta(days=i + 1)
        out.append({"time": d.strftime("%Y-%m-%d"), "open": c, "high": c * 1.01,
                    "low": c * 0.99, "close": c})
    return out


class RiskMetricsTests(BaseAPITestCase):
    def test_new_metrics_keys_and_math(self):
        # 两段交易:先赚后亏 → profit_factor 为有限值;持仓天数可算
        closes = [100 + i * 0.5 for i in range(20)] + [110 - i * 0.5 for i in range(1, 21)] \
            + [98 + i * 0.1 for i in range(1, 21)] + [97 - i * 0.5 for i in range(1, 21)]
        candles = _payload(closes)
        signals = [None] * len(closes)
        signals[0], signals[19], signals[40], signals[59] = "BUY", "SELL", "BUY", "SELL"
        result = run_backtest(candles, signals, 100000)
        m = result["metrics"]
        for key in ("sharpe", "volatility_pct", "profit_factor", "calmar", "exposure_pct", "avg_hold_days"):
            self.assertIn(key, m)
        self.assertEqual(m["trade_count"], 2)
        self.assertIsNotNone(m["profit_factor"])  # 有盈有亏 → 有限盈亏比
        self.assertGreater(m["exposure_pct"], 0)
        self.assertEqual(m["avg_hold_days"], 19.0)  # 执行日间隔 19 天
        self.assertGreater(m["volatility_pct"], 0)

    def test_no_trades_metrics_safe(self):
        candles = _payload([100.0] * 40)
        m = run_backtest(candles, [None] * 40, 100000)["metrics"]
        self.assertEqual(m["sharpe"], 0.0)
        self.assertIsNone(m["profit_factor"])
        self.assertIsNone(m["calmar"])
        self.assertEqual(m["exposure_pct"], 0.0)


class CompareServiceTests(BaseAPITestCase):
    def test_ranking_and_oos_contract(self):
        closes = [100 * (1.003 ** i) for i in range(120)]
        candles = _payload(closes)
        out = compare_strategies(candles, candles)
        self.assertEqual(len(out["results"]), 4)
        self.assertEqual([r["rank"] for r in out["results"]], [1, 2, 3, 4])
        for r in out["results"]:
            self.assertEqual(len(r["oos"]["folds"]), 3)
            self.assertEqual(len(r["curve"]), 120)
            self.assertIn("regime", r)
            self.assertLessEqual(r["oos"]["positive_folds"], 3)
        # 排名按 OOS Sharpe 降序
        sharpes = [r["oos"]["sharpe"] for r in out["results"]]
        self.assertEqual(sharpes, sorted(sharpes, reverse=True))

    def test_subset_strategies(self):
        candles = _payload([100 + i * 0.2 for i in range(80)])
        out = compare_strategies(candles, strategy_ids=["ma_cross", "macd"])
        self.assertEqual({r["id"] for r in out["results"]}, {"ma_cross", "macd"})

    def test_index_scale_lot_one_trades(self):
        # 指数点位尺度(3500+)整手门槛会零成交,lot=1 必须产生交易
        closes = [3500 * (1.002 ** i) * (1 + 0.01 * math.sin(i / 5.0)) for i in range(120)]
        out = compare_strategies(_payload(closes), lot=1)
        self.assertGreater(out["results"][0]["metrics"]["trade_count"], 0)

    def test_short_window_degrades_gracefully(self):
        candles = _payload([100 + i * 0.1 for i in range(30)])
        out = compare_strategies(candles)
        self.assertEqual(len(out["results"]), 4)
        self.assertLess(out["warmup"], 60)


class CompareApiTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        seed_daily_candles(self.stock, count=120)
        self.index = make_stock(symbol="sh000001", name="上证指数", price="3000.00",
                                prev_close="2990.00", active=False, kind=Stock.Kind.INDEX)
        seed_daily_candles(self.index, count=120, seed="idx-cmp")

    def test_requires_auth(self):
        self.anon()
        resp = self.client.post("/api/backtest/compare/", {"symbol": "000001"}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_compare_contract(self):
        self.auth()
        resp = self.client.post("/api/backtest/compare/",
                                {"symbol": "000001", "days": 120}, format="json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["symbol"], "000001")
        self.assertEqual(len(data["results"]), 4)
        self.assertIn("regime_labels", data)
        self.assertEqual(data["results"][0]["rank"], 1)

    def test_unknown_strategy_list_400(self):
        self.auth()
        resp = self.client.post("/api/backtest/compare/",
                                {"symbol": "000001", "strategies": ["nope"]}, format="json")
        self.assertEqual(resp.status_code, 400)