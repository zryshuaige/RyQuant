"""
可视化规则搭建器:operand 目录 / 规则校验 / 自动生成标准策略 spec。
规则 = 买入条件 + 卖出条件(或镜像买入),条件 = 左 operand × 比较 × 右 operand。
不执行任何用户代码:operand 只能从内置指标目录选取,信号由纯函数计算。
生成的 spec 与内置策略同形状,直接走 clean_params / run_backtest / compare。
"""
from ..errors import BusinessError
from . import indicators as ta
from .strategies import _cross_signals

MAX_CUSTOM = 10  # 每用户自定义策略上限(轻量研究终端)

OPS = {"cross_up": "上穿", "cross_down": "下穿", "gt": "高于", "lt": "低于"}
FLIP = {"cross_up": "cross_down", "cross_down": "cross_up", "gt": "lt", "lt": "gt"}

# operand 目录:family 用于参数去重(MACD 三线共享 fast/slow/signal,布林三轨共享 n/k)
OPERANDS = {
    "sma": {"label": "均线 SMA", "family": "sma", "fields": ["n"], "panel": False},
    "ema": {"label": "指数均线 EMA", "family": "ema", "fields": ["n"], "panel": False},
    "rsi": {"label": "强弱值 RSI", "family": "rsi", "fields": ["n"], "panel": True},
    "dif": {"label": "动能线 DIF", "family": "macd", "fields": ["fast", "slow", "signal"], "panel": True},
    "dea": {"label": "信号线 DEA", "family": "macd", "fields": ["fast", "slow", "signal"], "panel": True},
    "boll_upper": {"label": "布林上轨", "family": "boll", "fields": ["n", "k"], "panel": False},
    "boll_mid": {"label": "布林中轨", "family": "boll", "fields": ["n", "k"], "panel": False},
    "boll_lower": {"label": "布林下轨", "family": "boll", "fields": ["n", "k"], "panel": False},
    "close": {"label": "收盘价", "family": "close", "fields": [], "panel": False},
    "const": {"label": "固定数值", "family": "const", "fields": ["value"], "panel": False},
}

FIELD_META = {
    "n": {"label": "窗口", "unit": "日", "type": "int", "default": 20, "min": 2, "max": 120,
          "help": "计算该指标所用的天数。越小越灵敏、噪音越多;越大越平滑、越滞后。"},
    "fast": {"label": "快线", "unit": "日", "type": "int", "default": 12, "min": 2, "max": 60,
             "help": "MACD 短期 EMA 天数。越小对价格变化越敏感。"},
    "slow": {"label": "慢线", "unit": "日", "type": "int", "default": 26, "min": 5, "max": 120,
             "help": "MACD 长期 EMA 天数。与快线之差决定 DIF 的幅度。"},
    "signal": {"label": "信号线", "unit": "日", "type": "int", "default": 9, "min": 1, "max": 60,
               "help": "对 DIF 再平滑的天数。越小金叉死叉越频繁。"},
    "k": {"label": "通道宽度", "unit": "倍波动", "type": "float", "default": 2.0, "min": 0.5, "max": 4.0,
          "help": "上下轨距离中轨几倍波动。越大越难突破、信号越少。"},
    "value": {"label": "阈值", "unit": "", "type": "float", "default": 0, "min": -10000, "max": 100000,
              "help": "与之比较的固定数值(如 RSI 的 30/70、DIF 的零轴)。", "control": "number"},
}

SLOTS = ["buy_left", "buy_right", "sell_left", "sell_right"]


def _effective_rule(rule):
    """镜像卖出 → 展开为与买入同 operand、反向比较的卖出条件。"""
    buy = rule["buy"]
    if rule.get("sell_mirror"):
        sell = {"left": buy["left"], "right": buy["right"], "op": FLIP[buy["op"]]}
    else:
        sell = rule["sell"]
    return {"buy": buy, "sell": sell}


def _validate_operand(raw, where):
    if not isinstance(raw, dict) or raw.get("kind") not in OPERANDS:
        raise BusinessError(f"{where}:指标项无效,请从目录中选择")
    op = dict(raw)
    meta = OPERANDS[op["kind"]]
    for field in meta["fields"]:
        fm = FIELD_META[field]
        v = op.get(field, fm["default"])
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise BusinessError(f"{where}:{fm['label']}必须为数字")
        if not (fm["min"] <= v <= fm["max"]):
            raise BusinessError(f"{where}:{fm['label']}需在 {fm['min']}~{fm['max']} 之间")
        op[field] = int(v) if fm["type"] == "int" else round(v, 2)
    return op


def _validate_condition(raw, where):
    if not isinstance(raw, dict):
        raise BusinessError(f"{where}:条件格式无效")
    if raw.get("op") not in OPS:
        raise BusinessError(f"{where}:比较方式无效(上穿/下穿/高于/低于)")
    left = _validate_operand(raw.get("left"), f"{where}左侧")
    right = _validate_operand(raw.get("right"), f"{where}右侧")
    if left["kind"] == "const" and right["kind"] == "const":
        raise BusinessError(f"{where}:两侧不能都是固定数值")
    return {"left": left, "right": right, "op": raw["op"]}


def validate_rule(rule):
    """校验并补全规则(填充默认数值),返回规范化后的规则。"""
    if not isinstance(rule, dict) or not isinstance(rule.get("buy"), dict):
        raise BusinessError("规则需包含买入条件")
    mirror = bool(rule.get("sell_mirror"))
    if not mirror and not isinstance(rule.get("sell"), dict):
        raise BusinessError("规则需包含卖出条件(或勾选「卖出与买入镜像」)")
    buy = _validate_condition(rule["buy"], "买入")
    norm = {"buy": buy, "sell_mirror": mirror}
    if not mirror:
        norm["sell"] = _validate_condition(rule["sell"], "卖出")
    return norm


def _param_key(slot, kind, field):
    family = OPERANDS[kind]["family"]
    if family in ("macd", "boll"):
        return f"{family}_{field}"  # 同族共享一套参数
    return f"{slot}_{field}"


def _base_label(kind, field, side):
    fm = FIELD_META[field]
    family = OPERANDS[kind]["family"]
    if family == "macd":
        return f"MACD {fm['label']}"
    if family == "boll":
        return f"布林 {fm['label']}"
    if kind == "const":
        return "买入阈值" if side == "buy" else "卖出阈值"
    return f"{OPERANDS[kind]['label']}·{fm['label']}"


def param_schema(rule):
    """由规则自动生成参数 schema + 槽位→参数键映射(同族去重,保持出现顺序)。"""
    norm = _effective_rule(rule)
    keymap = {s: {} for s in SLOTS}
    entries, seen = [], set()
    for side in ("buy", "sell"):
        for pos in ("left", "right"):
            slot = f"{side}_{pos}"
            src_slot = f"buy_{pos}" if (side == "sell" and rule.get("sell_mirror")) else slot
            operand = norm[side][pos]
            kind = operand["kind"]
            for field in OPERANDS[kind]["fields"]:
                key = _param_key(src_slot, kind, field)
                keymap[slot][field] = key
                if key in seen:
                    continue
                seen.add(key)
                entries.append((key, kind, field, side, pos, operand))
    # 同名参数(如买卖两侧各一条 SMA)加槽位后缀消歧
    counts = {}
    for _, kind, field, side, _, _ in entries:
        base = _base_label(kind, field, side)
        counts[base] = counts.get(base, 0) + 1
    schema = []
    for key, kind, field, side, pos, operand in entries:
        fm = FIELD_META[field]
        label = _base_label(kind, field, side)
        if counts[label] > 1:
            label += f"({'买入' if side == 'buy' else '卖出'}{'左' if pos == 'left' else '右'})"
        schema.append({
            "key": key, "label": label, "unit": fm["unit"], "type": fm["type"],
            "default": operand.get(field, fm["default"]),
            "min": fm["min"], "max": fm["max"], "help": fm["help"],
            "control": fm.get("control", "slider"),
        })
    return schema, keymap


def _operand_text(kind, slot, keymap):
    k = keymap[slot]
    if kind == "sma":
        return f"近 {{{k['n']}}} 日均价"
    if kind == "ema":
        return f"近 {{{k['n']}}} 日指数均价"
    if kind == "rsi":
        return f"强弱值 RSI({{{k['n']}}} 日)"
    if kind == "dif":
        return "动能线 DIF"
    if kind == "dea":
        return "信号线 DEA"
    if kind == "boll_upper":
        return f"布林上轨({{{k['n']}}} 日 + {{{k['k']}}} 倍波动)"
    if kind == "boll_mid":
        return f"布林中轨({{{k['n']}}} 日均价)"
    if kind == "boll_lower":
        return f"布林下轨({{{k['n']}}} 日 - {{{k['k']}}} 倍波动)"
    if kind == "close":
        return "收盘价"
    return f"{{{k['value']}}}"  # const


def rule_texts(rule, keymap):
    norm = _effective_rule(rule)
    out = []
    for side in ("buy", "sell"):
        cond = norm[side]
        slots = (f"buy_{p}" if (side == "sell" and rule.get("sell_mirror")) else f"{side}_{p}"
                 for p in ("left", "right"))
        left_slot, right_slot = slots
        left = _operand_text(cond["left"]["kind"], left_slot, keymap)
        right = _operand_text(cond["right"]["kind"], right_slot, keymap)
        out.append(f"{left} {OPS[cond['op']]} {right}")
    return out[0], out[1]


def operand_series(closes, operand, params, keymap, slot):
    """按槽位参数计算 operand 序列(const → 常量序列,close → 收盘价本身)。"""
    kind = operand["kind"]
    k = keymap[slot]
    if kind == "close":
        return list(closes)
    if kind == "const":
        return [float(params[k["value"]])] * len(closes)
    if kind in ("sma", "ema"):
        n = int(params[k["n"]])
        return ta.sma(closes, n) if kind == "sma" else ta.ema(closes, n)
    if kind == "rsi":
        return ta.rsi(closes, int(params[k["n"]]))
    if kind in ("dif", "dea"):
        dif, dea, _ = ta.macd(closes, int(params[k["fast"]]), int(params[k["slow"]]),
                              int(params[k["signal"]]))
        return dif if kind == "dif" else dea
    bands = ta.boll(closes, int(params[k["n"]]), float(params[k["k"]]))
    idx = {"boll_mid": 0, "boll_upper": 1, "boll_lower": 2}[kind]
    return [b[idx] if b is not None else None for b in bands]


def _cond_fires(closes, cond, params, keymap, side, mirror):
    """条件触发序列(bool):cross 用通用穿越,gt/lt 用边沿触发(由假变真才触发)。"""
    slots = {}
    for pos in ("left", "right"):
        slots[pos] = f"buy_{pos}" if (side == "sell" and mirror) else f"{side}_{pos}"
    left = operand_series(closes, cond["left"], params, keymap, slots["left"])
    right = operand_series(closes, cond["right"], params, keymap, slots["right"])
    op = cond["op"]
    fires = [False] * len(closes)
    if op in ("cross_up", "cross_down"):
        crossed = _cross_signals(closes, left, right)
        want = "BUY" if op == "cross_up" else "SELL"
        for i, s in enumerate(crossed):
            fires[i] = s == want
    else:
        for i in range(1, len(closes)):
            if None in (left[i], right[i], left[i - 1], right[i - 1]):
                continue
            now = left[i] > right[i] if op == "gt" else left[i] < right[i]
            prev = left[i - 1] > right[i - 1] if op == "gt" else left[i - 1] < right[i - 1]
            fires[i] = now and not prev
    return fires


def rule_signals(closes, rule, params, keymap):
    mirror = bool(rule.get("sell_mirror"))
    norm = _effective_rule(rule)
    buy = _cond_fires(closes, norm["buy"], params, keymap, "buy", mirror)
    sell = _cond_fires(closes, norm["sell"], params, keymap, "sell", mirror)
    # 同 bar 买卖冲突时卖出优先(风险优先)
    return ["SELL" if s else ("BUY" if b else None) for b, s in zip(buy, sell)]


def build_spec(rule, name, fits=None, pk=None):
    """规则 → 标准策略 spec(与内置同形状,可直接回测/对比/预览)。"""
    norm = validate_rule(rule)
    schema, keymap = param_schema(norm)
    buy_text, sell_text = rule_texts(norm, keymap)
    return {
        "id": f"custom_{pk}" if pk is not None else "custom_preview",
        "name": name,
        "description": f"自定义规则策略:{buy_text} 时买入;{sell_text} 时卖出。",
        "essence": f"{buy_text} 就买,{sell_text} 就卖。",
        "buy_rule": buy_text,
        "sell_rule": sell_text,
        "fits": [f for f in (fits or []) if f in ("bull", "bear", "range", "high_vol")],
        "risk": "自定义规则策略:信号质量取决于规则设计,建议先用「策略对比」与样本外检验再采信。",
        "presets": [{"name": "默认", "hint": "搭建器保存的数值",
                     "values": {p["key"]: p["default"] for p in schema}}],
        "params": schema,
        "custom": True,
        "rule": norm,
        "signals": lambda closes, params: rule_signals(closes, norm, params, keymap),
    }


def apply_params_to_rule(rule, params):
    """把搭建器里调好的参数值写回 operand 默认值(保存后默认即所见)。"""
    norm = validate_rule(rule)
    schema, keymap = param_schema(norm)
    defaults = {p["key"]: p["default"] for p in schema}
    values = {**defaults, **(params or {})}
    mirror = bool(norm.get("sell_mirror"))
    effective = _effective_rule(norm)  # 镜像时 sell 与 buy 共享 operand 引用,写回即同步
    for side in ("buy", "sell"):
        for pos in ("left", "right"):
            slot = f"buy_{pos}" if (side == "sell" and mirror) else f"{side}_{pos}"
            operand = effective[side][pos]
            for field in OPERANDS[operand["kind"]]["fields"]:
                key = keymap[slot][field]
                fm = FIELD_META[field]
                v = values.get(key, operand.get(field, fm["default"]))
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
                v = min(max(v, fm["min"]), fm["max"])
                operand[field] = int(v) if fm["type"] == "int" else round(v, 2)
    return norm


def spec_max_window(spec):
    """spec 用到的最大窗口(供对比 warmup);内置策略保持默认 60。"""
    days = [p["max"] for p in spec.get("params", []) if p["type"] == "int" and p.get("unit") == "日"]
    return max(days) if days else 60