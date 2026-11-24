"""量化模块:指标纯函数、回测引擎数学、VIP 权限与 API 契约。"""
from unittest.mock import patch

from rest_framework import status

from trading.services.quant import indicators as ta
from trading.services.quant.engine import run_backtest
from trading.services.quant.strategies import clean_params, get_strategy

from .base import BaseAPITestCase, make_stock, seed_daily_candles


class IndicatorTests(BaseAPITestCase):
    def test_sma_known_values(self):
        values = [1, 2, 3, 4, 5]
        result = ta.sma(values, 3)
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertAlmostEqual(result[2], 2.0)
        self.assertAlmostEqual(result[4], 4.0)

    def test_ema_converges_to_constant(self):
        result = ta.ema([10.0] * 40, 12)
        self.assertAlmostEqual(result[-1], 10.0)
        self.assertIsNone(result[0])

    def test_rsi_bounds_and_trend(self):
        rising = [100 + i * 2 for i in range(40)]
        r = ta.rsi(rising, 14)
        self.assertGreater(r[-1], 90)
        falling = [100 - i for i in range(40)]
        self.assertLess(ta.rsi(falling, 14)[-1], 10)

    def test_boll_band_math(self):
        values = [10.0] * 25
        mid, upper, lower = ta.boll(values, 20, 2.0)[-1]
        self.assertAlmostEqual(mid, 10.0)
        self.assertAlmostEqual(upper, 10.0)
        self.assertAlmostEqual(lower, 10.0)

    def test_macd_alignment(self):
        dif, dea, hist = ta.macd(list(range(1, 60)), 12, 26, 9)
        self.assertEqual(len(dif), len(dea), len(hist))
        self.assertIsNone(dif[0])
        self.assertIsNone(dea[0])


class BacktestEngineTests(BaseAPITestCase):
    def test_signals_execute_next_open(self):
        # 先抑后扬序列 → 双均线金叉 → 引擎应在信号后的下一根开盘买入
        closes = [100 - i for i in range(20)] + [80 + i * 2 for i in range(20)]
        candles = [{"time": f"2025-01-{i+1:02d}", "open": c, "high": c,
                    "low": c, "close": c} for i, c in enumerate(closes)]
        spec = get_strategy("ma_cross")
        closes = [c["close"] for c in candles]
        signals = spec["signals"](closes, {"fast": 3, "slow": 10})
        result = run_backtest(candles, signals, 100000)
        self.assertEqual(len(result["equity_curve"]), len(candles))
        self.assertTrue(result["markers"])  # 至少出现一次买点
        first_buy = next(m for m in result["markers"] if m["side"] == "BUY")
        first_signal_index = next(i for i, s in enumerate(signals) if s == "BUY")
        self.assertEqual(first_buy["index"], first_signal_index + 1)

    def test_metrics_math(self):
        # 先抑后扬:金叉后全仓买入应跑出正收益;基准=买入持有
        closes = [100 - i for i in range(25)] + [75 + i * 3 for i in range(35)]
        candles = [{"time": str(i), "open": c, "high": c, "low": c, "close": c}
                   for i, c in enumerate(closes)]
        spec = get_strategy("ma_cross")
        signals = spec["signals"](closes, {"fast": 3, "slow": 10})
        result = run_backtest(candles, signals, 100000)
        metrics = result["metrics"]
        self.assertGreater(metrics["total_return_pct"], 0)
        self.assertGreater(metrics["final_equity"], 100000)
        self.assertTrue(-15 < metrics["max_drawdown_pct"] <= 0)

    def test_clean_params_clamps(self):
        spec = get_strategy("ma_cross")
        params = clean_params(spec, {"fast": 999, "slow": 1, "unknown": 5})
        self.assertEqual(params["fast"], 60)  # 截断到上限
        self.assertEqual(params["slow"], 5)  # 非法值截断到下限
        self.assertNotIn("unknown", params)


class BacktestApiTests(BaseAPITestCase):
    def setUp(self):
        seed_daily_candles(self.stock, count=200, seed="backtest")
        # 抬升价格避免全部为整手取整为 0
        self.stock.price = self.stock.price
        self.stock.save()

    def test_requires_auth(self):
        self.anon()
        resp = self.client.post("/api/backtest/", {
            "strategy": "ma_cross", "symbol": self.stock.symbol,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_run_contract(self):
        self.auth()
        resp = self.client.post("/api/backtest/", {
            "strategy": "ma_cross", "symbol": self.stock.symbol,
            "params": {"fast": 5, "slow": 20}, "days": 150, "initial_capital": 100000,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        run = resp.data["run"]
        for key in ("id", "strategy", "symbol", "params", "metrics", "equity_curve", "candles", "markers", "trades"):
            self.assertIn(key, run)
        self.assertEqual(run["strategy"], "ma_cross")
        self.assertTrue(run["metrics"])

    def test_unknown_strategy(self):
        self.auth()
        resp = self.client.post("/api/backtest/", {"strategy": "nope", "symbol": self.stock.symbol}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_history_and_detail(self):
        self.auth()
        self.client.post("/api/backtest/", {"strategy": "rsi_reversion", "symbol": self.stock.symbol}, format="json")
        resp = self.client.get("/api/backtest/history/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["runs"]), 1)
        run_id = resp.data["runs"][0]["id"]
        resp = self.client.get(f"/api/backtest/history/{run_id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("equity_curve", resp.data["run"])

    def test_backtest_on_real_index(self):
        index = make_stock("sh000001", "上证指数", price="3952.18", prev_close="3956.57",
                           active=False, kind="index")
        seed_daily_candles(index, count=200, seed="index-bt")
        self.auth()
        resp = self.client.post("/api/backtest/", {
            "strategy": "ma_cross", "symbol": "sh000001", "days": 150,
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        run = resp.data["run"]
        self.assertEqual(run["symbol"], "sh000001")
        self.assertIn("metrics", run)

    def test_strategies_list_schema(self):
        self.auth()
        resp = self.client.get("/api/strategies/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        strategies = resp.data["strategies"]
        self.assertEqual(len(strategies), 4)
        for s in strategies:
            self.assertIn("params", s)
            for p in s["params"]:
                self.assertIn("key", p)
