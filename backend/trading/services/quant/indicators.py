"""技术指标纯函数。输入 float 列表(时间升序),输出对齐长度的列表,数据不足处为 None。"""
from typing import List, Optional


def sma(values: List[float], n: int) -> List[Optional[float]]:
    out = [None] * len(values)
    if n <= 0:
        return out
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= n:
            running -= values[i - n]
        if i >= n - 1:
            out[i] = running / n
    return out


def ema(values: List[float], n: int) -> List[Optional[float]]:
    out = [None] * len(values)
    if n <= 0 or len(values) < n:
        return out
    k = 2.0 / (n + 1)
    prev = sum(values[:n]) / n  # 首值用 SMA 种子
    out[n - 1] = prev
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def macd(values, fast: int = 12, slow: int = 26, signal: int = 9):
    """返回 (dif, dea, hist),hist 为 MACD 柱(中国口径 = 2*(dif-dea))。"""
    ema_fast, ema_slow = ema(values, fast), ema(values, slow)
    dif = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow)
    ]
    valid = [d for d in dif if d is not None]
    dea_valid = ema(valid, signal)
    dea = [None] * len(dif)
    j = 0
    for i, d in enumerate(dif):
        if d is not None:
            dea[i] = dea_valid[j]
            j += 1
    hist = [
        (d - a) * 2 if (d is not None and a is not None) else None
        for d, a in zip(dif, dea)
    ]
    return dif, dea, hist


def rsi(values: List[float], n: int = 14) -> List[Optional[float]]:
    """Wilder 平滑 RSI。"""
    out = [None] * len(values)
    if n <= 0 or len(values) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        ch = values[i] - values[i - 1]
        if ch >= 0:
            gains += ch
        else:
            losses -= ch
    avg_g, avg_l = gains / n, losses / n
    out[n] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    for i in range(n + 1, len(values)):
        ch = values[i] - values[i - 1]
        g = ch if ch > 0 else 0.0
        l = -ch if ch < 0 else 0.0
        avg_g = (avg_g * (n - 1) + g) / n
        avg_l = (avg_l * (n - 1) + l) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def boll(values: List[float], n: int = 20, k: float = 2.0) -> List[Optional[tuple]]:
    """布林带:返回 (mid, upper, lower) 三元组列表。"""
    out = [None] * len(values)
    if n <= 0:
        return out
    for i in range(n - 1, len(values)):
        window = values[i - n + 1: i + 1]
        mid = sum(window) / n
        variance = sum((x - mid) ** 2 for x in window) / n
        sd = variance ** 0.5
        out[i] = (mid, mid + k * sd, mid - k * sd)
    return out
