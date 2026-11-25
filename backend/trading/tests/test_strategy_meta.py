"""策略白话解释 / 买卖规则 / 预设 / 参数含义 的 schema 完整性。"""
from django.test import TestCase

from trading.services.quant import strategies as reg


class StrategyMetaTests(TestCase):
    def test_every_strategy_has_plain_language_meta(self):
        for s in reg.STRATEGIES:
            for key in ("essence", "buy_rule", "sell_rule", "fits", "risk", "presets"):
                self.assertTrue(s.get(key), f"{s['id']} 缺少 {key}")
            self.assertTrue(set(s["fits"]) <= {"bull", "bear", "range", "high_vol"})

    def test_rule_templates_reference_known_params(self):
        import re
        for s in reg.STRATEGIES:
            keys = {p["key"] for p in s["params"]}
            for tpl in (s["buy_rule"], s["sell_rule"]):
                for ref in re.findall(r"\{(\w+)\}", tpl):
                    self.assertIn(ref, keys, f"{s['id']} 规则引用了未知参数 {ref}")

    def test_presets_within_schema_and_cleanable(self):
        for s in reg.STRATEGIES:
            self.assertGreaterEqual(len(s["presets"]), 2)
            for preset in s["presets"]:
                cleaned = reg.clean_params(s, preset["values"])
                for p in s["params"]:
                    self.assertGreaterEqual(cleaned[p["key"]], p["min"])
                    self.assertLessEqual(cleaned[p["key"]], p["max"])
                self.assertTrue(preset.get("hint"))

    def test_params_carry_help_and_unit(self):
        for s in reg.STRATEGIES:
            for p in s["params"]:
                self.assertTrue(p.get("help"), f"{s['id']}.{p['key']} 缺少 help")
                self.assertIn("unit", p)

    def test_api_exposes_meta(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        user = get_user_model().objects.create_user(username="meta_user", password="pw123456")
        client = APIClient()
        from rest_framework.authtoken.models import Token
        token = Token.objects.create(user=user)
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        res = client.get("/api/strategies/")
        self.assertEqual(res.status_code, 200)
        first = res.json()["strategies"][0]
        for key in ("essence", "buy_rule", "sell_rule", "fits", "risk", "presets"):
            self.assertIn(key, first)