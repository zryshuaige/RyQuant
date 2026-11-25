"""行情推断:regime 规则 / 波动率分位 / regime_series 无未来函数 / pulse 端点 / AI 离线上下文。"""
import math

from django.test import SimpleTestCase

from trading.models import Stock
from trading.services import market_analysis as ma
from trading.services.ai_client import mock_reply

from .base import BaseAPITestCase, make_stock, seed_daily_candles


def _bull(n=120):
    return [100 * (1.004 ** i) for i in range(n)]


def _bear(n=120):
    return [100 * (0.996 ** i) for i in range(n)]


def _range(n=120):
    # 长期缓跌后末端温和回升:站上 MA20 但仍在 MA60 下方、斜率走平 → 震荡
    # 两阶段叠加同幅噪声,避免零波动段导致波动率分位失真
    base = [120 - 0.2 * i for i in range(100)] + [100.2 + 0.03 * i for i in range(20)]
    return [p + 0.15 * math.sin(i / 3.0) for i, p in enumerate(base)]


def _high_vol(n=180):
    calm = [100 * (1 + 0.003 * math.sin(i / 7.0)) for i in range(150)]
    storm = [calm[-1]]
    for i in range(30):
        storm.append(storm[-1] * (1.05 if i % 2 == 0 else 0.95))
    return calm + storm[1:]


class RegimeRuleTests(SimpleTestCase):
    def test_bull(self):
        self.assertEqual(ma.classify_regime(_bull())["regime"], "bull")

    def test_bear(self):
        self.assertEqual(ma.classify_regime(_bear())["regime"], "bear")

    def test_range(self):
        self.assertEqual(ma.classify_regime(_range())["regime"], "range")

    def test_high_vol(self):
        self.assertEqual(ma.classify_regime(_high_vol())["regime"], "high_vol")

    def test_vol_percentile_midrank_constant(self):
        self.assertEqual(ma.vol_percentile([100.0] * 60), 50.0)

    def test_short_history_defaults_range(self):
        out = ma.classify_regime([100.0] * 10)
        self.assertEqual(out["regime"], "range")
        self.assertTrue(out["evidence"])

    def test_breadth_confirmation_shifts_score(self):
        base = ma.classify_regime(_range())
        confirmed = ma.classify_regime(_range(), pct_above_ma20=80.0)
        self.assertGreater(confirmed["score"], base["score"])


class RegimeSeriesTests(SimpleTestCase):
    def test_no_lookahead(self):
        a = _bull(80)
        extra = _bear(40)
        s1 = ma.regime_series(a)
        s2 = ma.regime_series(a + extra)
        self.assertEqual(s1, s2[:len(a)])  # 未来数据不改变历史判定

    def test_length_and_warmup(self):
        closes = _bull(60)
        s = ma.regime_series(closes)
        self.assertEqual(len(s), 60)
        self.assertEqual(set(s[:24]), {"range"})


class PulseApiTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.index = make_stock(symbol="sh000001", name="上证指数", price="3000.00",
                                prev_close="2990.00", active=False, kind=Stock.Kind.INDEX)
        seed_daily_candles(self.index, count=120, seed="idx")
        ma.market_pulse(force=True)  # 清缓存,避免跨用例脏快照

    def test_pulse_contract_and_cache(self):
        self.anon()
        r1 = self.client.get("/api/market/pulse/")
        self.assertEqual(r1.status_code, 200)
        data = r1.json()
        for key in ("regime", "label", "score", "evidence", "breadth", "sectors",
                    "anchor", "quote_source", "generated_at", "advice"):
            self.assertIn(key, data)
        self.assertEqual(data["anchor"]["symbol"], "sh000001")
        r2 = self.client.get("/api/market/pulse/")
        self.assertEqual(r1.json()["generated_at"], r2.json()["generated_at"])  # TTL 缓存

    def test_breadth_counts(self):
        make_stock(symbol="601318", name="中国平安", price="42.30", prev_close="42.00")
        make_stock(symbol="600519", name="贵州茅台", price="1600.00", prev_close="1688.00")
        pulse = ma.market_pulse(force=True)
        self.assertEqual(pulse["breadth"]["advance"], 2)  # 000001 + 601318
        self.assertEqual(pulse["breadth"]["decline"], 1)  # 600519


class StrategyAdviceTests(SimpleTestCase):
    def test_advice_ranks_regime_performance_first(self):
        from trading.services.quant.compare import strategy_advice

        # 带回调的多头:保证趋势策略在 bull 桶内有卖出成交
        closes = [100 * (1.003 ** i) * (1 + 0.025 * math.sin(i / 5.0)) for i in range(150)]
        advice = strategy_advice(closes, "bull")
        self.assertTrue(1 <= len(advice) <= 3)
        for a in advice:
            self.assertIn("reason", a)
            self.assertIn("oos_sharpe", a)
        # 多头状态下趋势类策略应有成交且排在前面
        self.assertGreater(advice[0]["regime_trades"], 0)
        self.assertIn("多头趋势", advice[0]["reason"])

    def test_advice_fallback_when_regime_empty(self):
        from trading.services.quant.compare import strategy_advice

        advice = strategy_advice(_bull(150), "high_vol")
        self.assertTrue(advice)
        self.assertIn("无成交记录", advice[0]["reason"])

    def test_advice_index_scale_has_trades(self):
        from trading.services.quant.compare import strategy_advice

        closes = [3500 * (1.002 ** i) * (1 + 0.02 * math.sin(i / 5.0)) for i in range(150)]
        advice = strategy_advice(closes, "bull")
        self.assertGreater(advice[0]["regime_trades"], 0)  # 不再退化到"无成交"回退

    def test_advice_short_history_empty(self):
        from trading.services.quant.compare import strategy_advice

        self.assertEqual(strategy_advice([100.0] * 30, "range"), [])


class AiOfflineContextTests(BaseAPITestCase):
    def test_market_reply_includes_pulse(self):
        reply = mock_reply(self.user, "最近大盘走势如何?")
        self.assertIn("大盘状态", reply)
        self.assertIn("涨", reply)