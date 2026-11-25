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
    "essence": "跟着趋势走:短期平均成本升破长期平均成本就买,跌回去就卖。",
    "buy_rule": "近 {fast} 日均价 上穿 近 {slow} 日均价",
    "sell_rule": "近 {fast} 日均价 下穿 近 {slow} 日均价",
    "fits": ["bull", "bear"],
    "risk": "震荡市里两条线反复缠绕,会连续小亏(俗称打脸)。",
    "presets": [
        {"name": "标准", "hint": "教科书默认 5/20", "values": {"fast": 5, "slow": 20}},
        {"name": "灵敏", "hint": "信号更快,交易更多", "values": {"fast": 3, "slow": 10}},
        {"name": "稳健", "hint": "信号更慢,过滤噪音", "values": {"fast": 10, "slow": 60}},
    ],
    "params": [
        {"key": "fast", "label": "快线窗口", "unit": "日", "type": "int", "default": 5, "min": 2, "max": 60,
         "help": "短期平均成本的天数。越小信号越快、交易越多;越大越平滑。"},
        {"key": "slow", "label": "慢线窗口", "unit": "日", "type": "int", "default": 20, "min": 5, "max": 120,
         "help": "中期平均成本的天数。与快线差距越大,信号越稳但越滞后。"},
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
    "essence": "看上涨/下跌的「力气」:力气由弱转强(金叉)买,由强转弱(死叉)卖。",
    "buy_rule": "动能线 DIF 上穿 信号线 DEA(金叉)",
    "sell_rule": "动能线 DIF 下穿 信号线 DEA(死叉)",
    "fits": ["bull", "bear"],
    "risk": "信号比均线更滞后,行情启动的第一段往往吃不到。",
    "presets": [
        {"name": "标准", "hint": "教科书默认 12/26/9", "values": {"fast": 12, "slow": 26, "signal": 9}},
        {"name": "灵敏", "hint": "更快捕捉动能转折", "values": {"fast": 6, "slow": 13, "signal": 5}},
        {"name": "稳健", "hint": "只跟大级别动能", "values": {"fast": 24, "slow": 52, "signal": 18}},
    ],
    "params": [
        {"key": "fast", "label": "快线 EMA", "unit": "日", "type": "int", "default": 12, "min": 2, "max": 60,
         "help": "短期动能的平滑天数。越小对价格变化越敏感。"},
        {"key": "slow", "label": "慢线 EMA", "unit": "日", "type": "int", "default": 26, "min": 5, "max": 120,
         "help": "长期动能的平滑天数。与快线之差决定 DIF 的幅度。"},
        {"key": "signal", "label": "信号线", "unit": "日", "type": "int", "default": 9, "min": 1, "max": 60,
         "help": "对 DIF 再平滑的天数。越小金叉死叉越频繁。"},
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
    "essence": "跌过头了买、涨过头了卖:赌价格会回到中间水平。",
    "buy_rule": "强弱值 RSI 从低于 {oversold} 回升穿过 {oversold}(跌过头后回暖)",
    "sell_rule": "强弱值 RSI 从高于 {overbought} 回落穿过 {overbought}(涨过头后降温)",
    "fits": ["range"],
    "risk": "单边下跌时会「抄底抄在半山腰」,趋势市慎用。",
    "presets": [
        {"name": "标准", "hint": "教科书默认 14/30/70", "values": {"period": 14, "oversold": 30, "overbought": 70}},
        {"name": "灵敏", "hint": "更早进出,信号更多", "values": {"period": 7, "oversold": 35, "overbought": 65}},
        {"name": "稳健", "hint": "只抓极端超买超卖", "values": {"period": 21, "oversold": 20, "overbought": 80}},
    ],
    "params": [
        {"key": "period", "label": "RSI 周期", "unit": "日", "type": "int", "default": 14, "min": 2, "max": 60,
         "help": "衡量涨跌强弱的窗口天数。越小越敏感、噪音越多。"},
        {"key": "oversold", "label": "超卖阈值", "unit": "", "type": "float", "default": 30, "min": 5, "max": 50,
         "help": "低于它算「跌过头」。调高=更早抄底,但假信号更多。"},
        {"key": "overbought", "label": "超买阈值", "unit": "", "type": "float", "default": 70, "min": 50, "max": 95,
         "help": "高于它算「涨过头」。调低=更早落袋,但可能卖飞。"},
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
    "essence": "价格冲出「正常波动通道」上沿就追进去,跌回通道中线就离场。",
    "buy_rule": "收盘价 向上突破 上轨(近 {n} 日均价 + {k} 倍波动)",
    "sell_rule": "收盘价 向下跌破 中轨(近 {n} 日均价)",
    "fits": ["high_vol", "bull"],
    "risk": "假突破多:冲高回落会买在短期高点,靠中轨止损。",
    "presets": [
        {"name": "标准", "hint": "教科书默认 20/2.0", "values": {"n": 20, "k": 2.0}},
        {"name": "灵敏", "hint": "窄通道,更早触发", "values": {"n": 10, "k": 1.5}},
        {"name": "稳健", "hint": "宽通道,只抓大突破", "values": {"n": 40, "k": 2.5}},
    ],
    "params": [
        {"key": "n", "label": "通道周期", "unit": "日", "type": "int", "default": 20, "min": 5, "max": 60,
         "help": "中轨=近 N 日均价。越大通道越稳定、越滞后。"},
        {"key": "k", "label": "通道宽度", "unit": "倍波动", "type": "float", "default": 2.0, "min": 0.5, "max": 4.0,
         "help": "上下轨距离中轨几倍波动。越大越难突破、信号越少。"},
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
