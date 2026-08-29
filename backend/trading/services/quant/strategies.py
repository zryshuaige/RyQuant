"""
策略注册表:内置策略 + 参数 schema(前端据此渲染动态参数表单)。
generate_signals(closes, params) 返回与 closes 对齐的信号列表:"BUY" / "SELL" / None。
信号在下一根 K 线开盘价执行(引擎保证),避免未来函数。
"""
from typing import List, Optional

from . import indicators as ta

Signal = Optional[str]


def _int_param(params, key, default, minimum=None):
    try:
        v = int(float(params.get(key, default)))
    except (TypeError, ValueError):
        v = int(default)
    if minimum is not None:
        v = max(v, minimum)
    return v


def _float_param(params, key, default, minimum=None):
    try:
        v = float(params.get(key, default))
    except (TypeError, ValueError):
        v = float(default)
    if minimum is not None:
        v = max(v, minimum)
    return v


def _cross_signals(closes, upper, lower) -> List[Signal]:
    """通用穿越信号:upper 序列上穿 lower 序列 → BUY,下穿 → SELL。"""
    sig = [None] * len(closes)
    for i in range(1, len(closes)):
        if None in (upper[i], lower[i], upper[i - 1], lower[i - 1]):
            continue
        if upper[i - 1] <= lower[i - 1] and upper[i] > lower[i]:
            sig[i] = "BUY"
        elif upper[i - 1] >= lower[i - 1] and upper[i] < lower[i]:
            sig[i] = "SELL"
    return sig


# ---- 双均线交叉 ----
def ma_cross_signals(closes, params) -> List[Signal]:
    fast = _int_param(params, "fast", 5, minimum=2)
    slow = max(_int_param(params, "slow", 20, minimum=3), fast + 1)
    return _cross_signals(closes, ta.sma(closes, fast), ta.sma(closes, slow))


MA_CROSS = {
    "id": "ma_cross",
    "name": "双均线交叉",
    "description": "短期均线上穿长期均线买入,下穿卖出。最经典的趋势跟随策略,适合单边行情。",
    "params": [
        {"key": "fast", "label": "快线窗口(日)", "type": "int", "default": 5, "min": 2, "max": 60},
        {"key": "slow", "label": "慢线窗口(日)", "type": "int", "default": 20, "min": 5, "max": 120},
    ],
    "signals": ma_cross_signals,
}


# ---- MACD 金叉死叉 ----
def macd_signals(closes, params) -> List[Signal]:
    fast = _int_param(params, "fast", 12, minimum=2)
    slow = max(_int_param(params, "slow", 26, minimum=3), fast + 1)
    signal_n = _int_param(params, "signal", 9, minimum=1)
    dif, dea, _ = ta.macd(closes, fast, slow, signal_n)
    return _cross_signals(closes, dif, dea)


MACD_STRATEGY = {
    "id": "macd",
    "name": "MACD 金叉死叉",
    "description": "DIF 上穿 DEA(金叉)买入,下穿(死叉)卖出。动能类指标,趋势确认更稳健。",
    "params": [
        {"key": "fast", "label": "快线 EMA", "type": "int", "default": 12, "min": 2, "max": 60},
        {"key": "slow", "label": "慢线 EMA", "type": "int", "default": 26, "min": 5, "max": 120},
        {"key": "signal", "label": "信号线", "type": "int", "default": 9, "min": 1, "max": 60},
    ],
    "signals": macd_signals,
}


# ---- RSI 均值回归 ----
def rsi_signals(closes, params) -> List[Signal]:
    period = _int_param(params, "period", 14, minimum=2)
    oversold = _float_param(params, "oversold", 30, minimum=1)
    overbought = _float_param(params, "overbought", 70, minimum=1)
    r = ta.rsi(closes, period)
    sig = [None] * len(closes)
    for i in range(1, len(closes)):
        if r[i] is None or r[i - 1] is None:
            continue
        if r[i - 1] < oversold <= r[i]:
            sig[i] = "BUY"  # 自下而上脱离超卖区
        elif r[i - 1] > overbought >= r[i]:
            sig[i] = "SELL"  # 自上而下跌离超买区
    return sig


RSI_STRATEGY = {
    "id": "rsi_reversion",
    "name": "RSI 均值回归",
    "description": "RSI 从超卖区回升时买入,从超买区回落时卖出。震荡市表现好,单边趋势中易过早离场。",
    "params": [
        {"key": "period", "label": "RSI 周期", "type": "int", "default": 14, "min": 2, "max": 60},
        {"key": "oversold", "label": "超卖阈值", "type": "float", "default": 30, "min": 5, "max": 50},
        {"key": "overbought", "label": "超买阈值", "type": "float", "default": 70, "min": 50, "max": 95},
    ],
    "signals": rsi_signals,
}


# ---- 布林带突破 ----
def boll_signals(closes, params) -> List[Signal]:
    n = _int_param(params, "n", 20, minimum=2)
    k = _float_param(params, "k", 2.0, minimum=0.5)
    bands = ta.boll(closes, n, k)
    sig = [None] * len(closes)
    for i in range(1, len(closes)):
        if bands[i] is None or bands[i - 1] is None:
            continue
        mid_prev, upper_prev, _ = bands[i - 1]
        mid, upper, _ = bands[i]
        if closes[i - 1] <= upper_prev and closes[i] > upper:
            sig[i] = "BUY"  # 放量突破上轨追入
        elif closes[i - 1] >= mid_prev and closes[i] < mid:
            sig[i] = "SELL"  # 跌破中轨离场
    return sig


BOLL_STRATEGY = {
    "id": "boll_breakout",
    "name": "布林带突破",
    "description": "收盘价突破上轨买入,跌破中轨卖出。捕捉波动率扩张,趋势启动快。",
    "params": [
        {"key": "n", "label": "周期", "type": "int", "default": 20, "min": 5, "max": 60},
        {"key": "k", "label": "标准差倍数", "type": "float", "default": 2.0, "min": 0.5, "max": 4.0},
    ],
    "signals": boll_signals,
}


STRATEGIES = [MA_CROSS, MACD_STRATEGY, RSI_STRATEGY, BOLL_STRATEGY]
REGISTRY = {s["id"]: s for s in STRATEGIES}


def get_strategy(strategy_id: str):
    return REGISTRY.get(strategy_id)


def clean_params(spec: dict, params: dict) -> dict:
    """按 schema 清洗参数:缺失/非法用默认值,越界截断,忽略未知键。"""
    params = params or {}
    cleaned = {}
    for p in spec["params"]:
        if p["type"] == "float":
            v = _float_param(params, p["key"], p["default"])
        else:
            v = _int_param(params, p["key"], p["default"])
        v = min(max(v, p["min"]), p["max"])
        cleaned[p["key"]] = v
    return cleaned
