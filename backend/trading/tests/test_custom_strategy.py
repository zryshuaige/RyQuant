"""自定义策略:规则校验 / 参数去重 / 信号正确性 / CRUD 权限 / 回测对比预览接入。"""
import re

from django.conf import settings
from django.test import override_settings

from trading.models import CustomStrategy
from trading.services.errors import BusinessError
from trading.services.quant import strategies as reg
from trading.services.quant.custom import (
    MAX_CUSTOM,
    build_spec,
    param_schema,
    rule_signals,
    validate_rule,
)

from .base import BaseAPITestCase, seed_daily_candles

# 测试内放开限流,避免用例间相互触发
_RATES = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
          "backtest": "1000/min", "preview": "1000/min"}
_FAST = override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": _RATES})

MA_RULE = {
    "buy": {"left": {"kind": "sma", "n": 5}, "op": "cross_up", "right": {"kind": "sma", "n": 20}},
    "sell_mirror": True,
}


class RuleValidationTests(BaseAPITestCase):
    def test_valid_mirror_rule_normalized(self):
        norm = validate_rule(MA_RULE)
        self.assertTrue(norm["sell_mirror"])
        self.assertEqual(norm["buy"]["left"]["n"], 5)

    def test_invalid_inputs_rejected(self):
        bad_rules = [
            {},  # 无买入
            {"buy": {"left": {"kind": "sma"}, "op": "nope", "right": {"kind": "close"}}},
            {"buy": {"left": {"kind": "unknown"}, "op": "gt", "right": {"kind": "close"}}},
            {"buy": {"left": {"kind": "const", "value": 1}, "op": "gt",
                     "right": {"kind": "const", "value": 2}}},  # 双侧常量
            {"buy": {"left": {"kind": "sma", "n": 999}, "op": "cross_up",
                     "right": {"kind": "close"}}},  # 窗口越界
            {"buy": MA_RULE["buy"]},  # 缺卖出且未镜像
        ]
        for rule in bad_rules:
            with self.assertRaises(BusinessError, msg=str(rule)):
                validate_rule(rule)

    def test_param_dedup_families(self):
        rule = {
            "buy": {"left": {"kind": "dif"}, "op": "cross_up", "right": {"kind": "dea"}},
            "sell": {"left": {"kind": "boll_upper"}, "op": "cross_down", "right": {"kind": "boll_mid"}},
        }
        schema, keymap = param_schema(validate_rule(rule))
        keys = [p["key"] for p in schema]
        self.assertEqual(keys.count("macd_fast"), 1)  # DIF/DEA 共享
        self.assertEqual(keys.count("boll_n"), 1)  # 上轨/中轨共享
        self.assertEqual(keymap["buy_left"]["fast"], keymap["buy_right"]["fast"])

    def test_independent_sma_slots(self):
        schema, keymap = param_schema(validate_rule(MA_RULE))
        self.assertNotEqual(keymap["buy_left"]["n"], keymap["buy_right"]["n"])
        self.assertEqual(len(schema), 2)

    def test_meta_shape_matches_builtin_contract(self):
        spec = build_spec(MA_RULE, "测试均线", fits=["bull"], pk=1)
        for key in ("essence", "buy_rule", "sell_rule", "risk", "presets"):
            self.assertTrue(spec.get(key))
        keys = {p["key"] for p in spec["params"]}
        for tpl in (spec["buy_rule"], spec["sell_rule"]):
            for ref in re.findall(r"\{(\w+)\}", tpl):
                self.assertIn(ref, keys)
        for p in spec["params"]:
            self.assertTrue(p.get("help"))
            self.assertIn("unit", p)
        self.assertTrue(spec["custom"])
        self.assertEqual(spec["id"], "custom_1")


class SignalCorrectnessTests(BaseAPITestCase):
    def test_custom_ma_matches_builtin(self):
        seed_daily_candles(self.stock, count=160, seed="custom-ma")
        from trading.models import Candle
        closes = [float(c.close) for c in
                  Candle.objects.filter(stock=self.stock, period=Candle.Period.DAY).order_by("time")]
        spec = build_spec(MA_RULE, "测试均线", pk=1)
        params = {"buy_left_n": 5, "buy_right_n": 20}
        mine = spec["signals"](closes, params)
        builtin = reg.REGISTRY["ma_cross"]["signals"](closes, {"fast": 5, "slow": 20})
        self.assertEqual(mine, builtin)
        self.assertIn("BUY", mine)
        self.assertIn("SELL", mine)

    def test_gt_edge_triggered(self):
        rule = {"buy": {"left": {"kind": "close"}, "op": "gt", "right": {"kind": "const", "value": 10}},
                "sell_mirror": True}
        spec = build_spec(rule, "阈值", pk=2)
        closes = [9, 9, 11, 12, 12, 8, 7, 11]
        sig = spec["signals"](closes, {"buy_right_value": 10})
        self.assertEqual(sig[2], "BUY")  # 上穿阈值边沿
        self.assertIsNone(sig[3])  # 持续高于不重复触发
        self.assertEqual(sig[5], "SELL")
        self.assertEqual(sig[7], "BUY")


@_FAST
class CustomStrategyAPITests(BaseAPITestCase):
    def setUp(self):
        self.auth()
        seed_daily_candles(self.stock, count=160, seed="custom-api")

    def _create(self, name="我的均线", rule=None):
        return self.client.post("/api/strategies/custom/",
                                {"name": name, "rule": rule or MA_RULE, "fits": ["bull"]}, format="json")

    def test_crud_and_ownership(self):
        res = self._create()
        self.assertEqual(res.status_code, 201)
        pk = res.json()["strategy"]["id"]
        # 列表与策略总表均可见
        self.assertEqual(self.client.get("/api/strategies/custom/").json()["strategies"][0]["id"], pk)
        listed = self.client.get("/api/strategies/").json()["strategies"]
        custom = [s for s in listed if s["id"] == f"custom_{pk}"]
        self.assertEqual(len(custom), 1)
        self.assertTrue(custom[0]["custom"])
        self.assertIn("rule", custom[0])
        # 同名拒绝
        self.assertEqual(self._create().status_code, 400)
        # 他人不可改删
        self.auth(self.other)
        self.assertEqual(self.client.put(f"/api/strategies/custom/{pk}/",
                                         {"name": "劫持", "rule": MA_RULE}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/strategies/custom/{pk}/").status_code, 404)
        self.auth()
        # 本人可改可删
        self.assertEqual(self.client.put(f"/api/strategies/custom/{pk}/",
                                         {"name": "改名", "rule": MA_RULE}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/strategies/custom/{pk}/").status_code, 204)

    def test_create_mirror_with_tuned_params(self):
        res = self.client.post("/api/strategies/custom/", {
            "name": "镜像调参", "rule": MA_RULE,
            "params": {"buy_left_n": 7, "buy_right_n": 30},
        }, format="json")
        self.assertEqual(res.status_code, 201)
        pk = res.json()["strategy"]["id"]
        listed = self.client.get("/api/strategies/").json()["strategies"]
        spec = next(s for s in listed if s["id"] == f"custom_{pk}")
        defaults = {p["key"]: p["default"] for p in spec["params"]}
        self.assertEqual(defaults["buy_left_n"], 7)  # 调好的值成为保存默认
        self.assertEqual(defaults["buy_right_n"], 30)
        self.assertTrue(spec["rule"]["sell_mirror"])

    def test_cap_limit(self):
        for i in range(MAX_CUSTOM):
            self.assertEqual(self._create(name=f"策略{i}").status_code, 201)
        self.assertEqual(self._create(name="超额").status_code, 400)

    def test_run_backtest_with_custom(self):
        pk = self._create().json()["strategy"]["id"]
        res = self.client.post("/api/backtest/", {
            "strategy": f"custom_{pk}", "symbol": self.stock.symbol,
            "params": {"buy_left_n": 5, "buy_right_n": 20}, "days": 120,
        }, format="json")
        self.assertEqual(res.status_code, 200)
        run = res.json()["run"]
        self.assertEqual(run["strategy"], f"custom_{pk}")
        self.assertEqual(run["strategy_name"], "我的均线")
        self.assertGreater(len(run["equity_curve"]), 100)
        # 历史显示名;删除自定义后兜底为 id
        hist = self.client.get("/api/backtest/history/").json()["runs"]
        self.assertEqual(hist[0]["strategy_name"], "我的均线")
        self.client.delete(f"/api/strategies/custom/{pk}/")
        hist = self.client.get("/api/backtest/history/").json()["runs"]
        self.assertEqual(hist[0]["strategy_name"], f"custom_{pk}")

    def test_compare_includes_custom(self):
        pk = self._create().json()["strategy"]["id"]
        ids = [s["id"] for s in reg.STRATEGIES] + [f"custom_{pk}"]
        res = self.client.post("/api/backtest/compare/", {
            "symbol": self.stock.symbol, "days": 160, "strategies": ids,
        }, format="json")
        self.assertEqual(res.status_code, 200)
        results = res.json()["results"]
        self.assertEqual(len(results), 5)
        self.assertIn(f"custom_{pk}", [r["id"] for r in results])
        self.assertEqual([r["rank"] for r in results], [1, 2, 3, 4, 5])
        # 默认对比仍为内置 4 个
        default = self.client.post("/api/backtest/compare/",
                                   {"symbol": self.stock.symbol, "days": 160}, format="json")
        self.assertEqual(len(default.json()["results"]), 4)

    def test_preview_builtin_and_inline_rule(self):
        res = self.client.post("/api/backtest/preview/", {
            "strategy": "ma_cross", "symbol": self.stock.symbol, "days": 120,
            "params": {"fast": 5, "slow": 20},
        }, format="json")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["candles"]), 121)
        self.assertEqual(len(body["preview"]["overlays"]), 2)
        self.assertTrue(any(s["side"] == "BUY" for s in body["preview"]["signals"]))
        self.assertIn("5", body["buy_text"])
        # 内联规则(搭建器边搭边看,无需保存)
        inline = self.client.post("/api/backtest/preview/", {
            "rule": MA_RULE, "symbol": self.stock.symbol, "days": 120,
        }, format="json")
        self.assertEqual(inline.status_code, 200)
        self.assertEqual(CustomStrategy.objects.count(), 0)
        # RSI 副图 + 阈值线
        rsi = self.client.post("/api/backtest/preview/", {
            "strategy": "rsi_reversion", "symbol": self.stock.symbol, "days": 120,
        }, format="json")
        panel = rsi.json()["preview"]["subpanel"]
        self.assertIsNotNone(panel)
        self.assertEqual(len(panel["levels"]), 2)

    def test_preview_rejects_unknown_and_bad_rule(self):
        self.assertEqual(self.client.post("/api/backtest/preview/", {
            "strategy": "nope", "symbol": self.stock.symbol}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/backtest/preview/", {
            "rule": {"buy": {"left": {"kind": "const"}, "op": "gt",
                             "right": {"kind": "const"}}},
            "symbol": self.stock.symbol}, format="json").status_code, 400)