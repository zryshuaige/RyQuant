"""策略实时预览:指标叠加线 / 副图 / 信号标记(只算指标与信号,不跑引擎、不持久化)。"""
from . import indicators as ta
from .custom import OPERANDS, _effective_rule, operand_series
from .strategies import clean_params


def _round(data):
    return [round(v, 4) if v is not None else None for v in data]


def _builtin_series(strategy_id, closes, params):
    if strategy_id == "ma_cross":
        f, s = int(params["fast"]), int(params["slow"])
        return ([{"key": "fast", "label": f"MA{f}", "data": _round(ta.sma(closes, f))},
                 {"key": "slow", "label": f"MA{s}", "data": _round(ta.sma(closes, s))}], None)
    if strategy_id == "macd":
        dif, dea, _ = ta.macd(closes, int(params["fast"]), int(params["slow"]), int(params["signal"]))
        return ([], {"label": "MACD",
                     "series": [{"key": "dif", "label": "DIF", "data": _round(dif)},
                                {"key": "dea", "label": "DEA", "data": _round(dea)}],
                     "levels": [{"value": 0, "label": "零轴"}]})
    if strategy_id == "rsi_reversion":
        r = ta.rsi(closes, int(params["period"]))
        return ([], {"label": f"RSI({params['period']})",
                     "series": [{"key": "rsi", "label": "RSI", "data": _round(r)}],
                     "levels": [{"value": params["oversold"], "label": "超卖"},
                                {"value": params["overbought"], "label": "超买"}]})
    if strategy_id == "boll_breakout":
        bands = ta.boll(closes, int(params["n"]), float(params["k"]))
        mid = [b[0] if b else None for b in bands]
        upper = [b[1] if b else None for b in bands]
        lower = [b[2] if b else None for b in bands]
        return ([{"key": "upper", "label": "上轨", "data": _round(upper)},
                 {"key": "mid", "label": "中轨", "data": _round(mid)},
                 {"key": "lower", "label": "下轨", "data": _round(lower)}], None)
    return ([], None)


def _custom_series(spec, closes, params):
    """按规则中的 operand 生成叠加线/副图(同族同参数去重),常量对手方 → 副图阈值线。"""
    from .custom import param_schema

    rule = spec["rule"]
    norm = _effective_rule(rule)
    _, keymap = param_schema(rule)

    overlays, panel_series, levels = [], [], []
    seen_overlay, seen_panel = set(), set()
    mirror = bool(rule.get("sell_mirror"))
    for side in ("buy", "sell"):
        cond = norm[side]
        for pos in ("left", "right"):
            slot = f"buy_{pos}" if (side == "sell" and mirror) else f"{side}_{pos}"
            operand = cond[pos]
            kind = operand["kind"]
            meta = OPERANDS[kind]
            if kind in ("close", "const"):
                continue
            data = _round(operand_series(closes, operand, params, keymap, slot))
            sig = (kind, tuple(sorted((f, params[keymap[slot][f]]) for f in meta["fields"])))
            if meta["panel"]:
                if sig in seen_panel:
                    continue
                seen_panel.add(sig)
                label = {"rsi": f"RSI({params[keymap[slot]['n']]})", "dif": "DIF", "dea": "DEA"}[kind]
                panel_series.append({"key": f"{slot}", "label": label, "data": data})
            else:
                if sig in seen_overlay:
                    continue
                seen_overlay.add(sig)
                if kind == "sma":
                    label = f"MA{params[keymap[slot]['n']]}"
                elif kind == "ema":
                    label = f"EMA{params[keymap[slot]['n']]}"
                else:
                    label = {"boll_upper": "上轨", "boll_mid": "中轨", "boll_lower": "下轨"}[kind]
                overlays.append({"key": slot, "label": label, "data": data})
        # 副图指标 × 固定数值 → 阈值水平线
        for a, b in ((cond["left"], cond["right"]), (cond["right"], cond["left"])):
            if OPERANDS[a["kind"]]["panel"] and b["kind"] == "const":
                pos_b = "right" if a is cond["left"] else "left"
                slot_b = f"buy_{pos_b}" if (side == "sell" and mirror) else f"{side}_{pos_b}"
                value = params[keymap[slot_b]["value"]]
                if not any(lv["value"] == value for lv in levels):
                    levels.append({"value": value, "label": "阈值"})
    subpanel = ({"label": " / ".join(s["label"] for s in panel_series),
                 "series": panel_series, "levels": levels} if panel_series else None)
    return overlays, subpanel


def build_preview(spec, closes, params):
    """返回 {overlays, subpanel, signals};signals 为信号判定 bar(非执行 bar)。"""
    params = clean_params(spec, params)
    signals = spec["signals"](closes, params)
    markers = [{"index": i, "side": s} for i, s in enumerate(signals) if s]
    if spec.get("custom"):
        overlays, subpanel = _custom_series(spec, closes, params)
    else:
        overlays, subpanel = _builtin_series(spec["id"], closes, params)
    return {"overlays": overlays, "subpanel": subpanel, "signals": markers}