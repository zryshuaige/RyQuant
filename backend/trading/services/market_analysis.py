"""
市场行情推断:广度 / 趋势 / 波动率分位 → 规则化 regime 判定(离线可用、可解释)。
- market_pulse():市场脉冲快照(TTL 缓存),供前端面板与 AI 上下文
- classify_regime(closes):单条日 K 收盘序列的规则判定
- regime_series(closes):逐日 regime 序列(仅用当日及之前信息,无未来函数),供回测对比分状态评估
"""
import math
import time

from django.utils import timezone

from ..models import Candle, Stock
from .market_data import SECTOR_MEMBERS
from .quant.indicators import sma

REGIME_LABELS = {
    "bull": "多头趋势",
    "bear": "空头趋势",
    "range": "震荡整理",
    "high_vol": "高波动状态",
}
CACHE_TTL = 60
_cache = {"ts": 0.0, "payload": None}


def _daily_closes(stock, limit=260):
    candles = Candle.objects.filter(stock=stock, period=Candle.Period.DAY).order_by("-time")[:limit]
    return [float(c.close) for c in candles][::-1]


def realized_vol(closes, n=20):
    """最近 n 个日收益的年化波动率(%)。"""
    rets = [closes[i] / closes[i - 1] - 1
            for i in range(max(1, len(closes) - n), len(closes)) if closes[i - 1] > 0]
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(250) * 100


def vol_percentile(closes, n=20, window=250):
    """当前 n 日波动率在近 window 日滚动波动率序列中的分位(0-100,并列取中秩)。"""
    if len(closes) < n + 2:
        return 50.0
    vols = [realized_vol(closes[:end], n)
            for end in range(max(n + 1, len(closes) - window), len(closes) + 1)]
    cur = vols[-1]
    others = vols[:-1]
    less = sum(1 for v in others if v < cur)
    eq = sum(1 for v in others if v == cur)
    return round((less + 0.5 * eq) / max(len(others), 1) * 100, 1)


def _regime_from_score(score, vp):
    if vp >= 80:
        return "high_vol"
    if score >= 30:
        return "bull"
    if score <= -30:
        return "bear"
    return "range"


def classify_regime(closes, pct_above_ma20=None, vol_window=250):
    """规则判定:趋势(价格 vs MA20/MA60、MA20 斜率)× 波动率分位 × 广度确认。"""
    n = len(closes)
    if n < 25:
        return {"regime": "range", "label": REGIME_LABELS["range"], "score": 0.0,
                "evidence": ["历史不足 25 根日 K,默认震荡整理"],
                "ma20": None, "ma60": None, "slope_pct": 0.0, "vol_percentile": 50.0}
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60) if n >= 60 else ma20
    last = closes[-1]
    m20 = ma20[-1] or last
    m60 = ma60[-1] or m20
    slope = (ma20[-1] - ma20[-6]) / ma20[-6] * 100 if ma20[-6] else 0.0
    vp = vol_percentile(closes, window=vol_window)
    score, evidence = 0.0, []
    if last > m20:
        score += 25
        evidence.append(f"收盘站上 MA20({m20:.2f})")
    else:
        score -= 25
        evidence.append(f"收盘跌破 MA20({m20:.2f})")
    if last > m60:
        score += 15
        evidence.append("收盘在 MA60 上方,中期趋势完好")
    else:
        score -= 15
        evidence.append("收盘在 MA60 下方,中期趋势偏弱")
    if slope > 0.5:
        score += 20
        evidence.append(f"MA20 五日斜率 +{slope:.2f}%")
    elif slope < -0.5:
        score -= 20
        evidence.append(f"MA20 五日斜率 {slope:.2f}%")
    else:
        evidence.append("MA20 斜率走平,方向不明")
    if vp >= 80:
        evidence.append(f"20 日波动率处近期 {vp:.0f} 分位,波动放大")
    elif vp <= 20:
        score += 5
        evidence.append(f"20 日波动率处近期 {vp:.0f} 分位,低波环境")
    if pct_above_ma20 is not None:
        if pct_above_ma20 >= 55:
            score += 10
            evidence.append(f"广度确认:{pct_above_ma20:.0f}% 个股站上 MA20")
        elif pct_above_ma20 <= 45:
            score -= 10
            evidence.append(f"广度确认:仅 {pct_above_ma20:.0f}% 个股站上 MA20")
    score = max(-100.0, min(100.0, score))
    regime = _regime_from_score(score, vp)
    return {"regime": regime, "label": REGIME_LABELS[regime], "score": round(score, 1),
            "evidence": evidence, "ma20": round(m20, 2), "ma60": round(m60, 2),
            "slope_pct": round(slope, 2), "vol_percentile": vp}


def market_breadth(stocks):
    """涨跌家数 / 站上 MA20 比例 / 平均涨跌幅。"""
    up = sum(1 for s in stocks if s.change_pct > 0)
    down = sum(1 for s in stocks if s.change_pct < 0)
    above = counted = 0
    for s in stocks:
        closes = _daily_closes(s, limit=25)
        if len(closes) >= 21:
            counted += 1
            m20 = sma(closes, 20)[-1]
            above += 1 if m20 and closes[-1] > m20 else 0
    avg = round(sum(float(s.change_pct) for s in stocks) / len(stocks), 2) if stocks else 0.0
    return {"advance": up, "decline": down, "flat": len(stocks) - up - down,
            "pct_above_ma20": round(above / counted * 100, 1) if counted else None,
            "avg_change_pct": avg}


def market_pulse(force=False):
    """市场脉冲快照:regime + 广度 + 板块热度 + 证据链;60s TTL 缓存保持轻量。"""
    now = time.monotonic()
    if not force and _cache["payload"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["payload"]
    stocks = list(Stock.objects.filter(kind=Stock.Kind.STOCK, is_active=True))
    indices = list(Stock.objects.filter(kind=Stock.Kind.INDEX).order_by("pk"))
    breadth = market_breadth(stocks)
    anchor = indices[0] if indices else None
    closes = _daily_closes(anchor) if anchor else []
    trend = classify_regime(closes, pct_above_ma20=breadth["pct_above_ma20"])
    sectors = []
    for name, members in SECTOR_MEMBERS.items():
        objs = [s for s in stocks if s.symbol in members]
        if objs:
            sectors.append({"name": name,
                            "change_pct": round(sum(float(s.change_pct) for s in objs) / len(objs), 2)})
    sectors.sort(key=lambda x: x["change_pct"], reverse=True)
    from .quant.compare import strategy_advice

    advice = strategy_advice(closes, trend["regime"]) if len(closes) >= 60 else []
    payload = {
        "regime": trend["regime"], "label": trend["label"], "score": trend["score"],
        "evidence": trend["evidence"],
        "advice": advice,
        "trend": {k: trend[k] for k in ("ma20", "ma60", "slope_pct", "vol_percentile")},
        "breadth": breadth,
        "sectors": sectors,
        "anchor": {"symbol": anchor.symbol, "name": anchor.name,
                   "change_pct": float(anchor.change_pct)} if anchor else None,
        "quote_source": anchor.quote_source if anchor else Stock.QuoteSource.SIM,
        "generated_at": timezone.localtime().isoformat(),
    }
    _cache.update(ts=now, payload=payload)
    return payload


def regime_series(closes, vol_window=120):
    """逐日 regime:第 i 日仅用 closes[:i+1](无未来函数);历史不足默认 range。"""
    return [classify_regime(closes[:i + 1], vol_window=vol_window)["regime"] if i + 1 >= 25 else "range"
            for i in range(len(closes))]