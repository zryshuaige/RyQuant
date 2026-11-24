"""
跨策略有效性对比:同标的同窗口、各策略默认参数 →
全窗口指标 + 滚动样本外(OOS folds) + 分 regime 条件化评估 + 排名(OOS Sharpe 主排序)。
信号仅用历史收盘判定(无未来函数);OOS 折内独立资金、折间收益拼接,前置 warmup 供指标预热。
结果不持久化(轻量);单策略持久化仍走 BacktestRun。
"""
import math

from ..market_analysis import REGIME_LABELS, regime_series
from . import strategies
from .engine import run_backtest

OOS_FOLDS = 3
WARMUP = 60  # 指标预热根数(MA60 为最长内置周期)


def _curve_returns(curve):
    return [curve[i]["equity"] / curve[i - 1]["equity"] - 1
            for i in range(1, len(curve)) if curve[i - 1]["equity"] > 0]


def _sharpe(rets):
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
    return round(mean / sd * math.sqrt(250), 2) if sd > 0 else 0.0


def _regime_breakdown(result, date_regime):
    """全窗口资金曲线日收益与逐笔盈亏,按当日 regime 分桶。"""
    buckets = {}
    curve = result["equity_curve"]
    for i in range(1, len(curve)):
        r = curve[i]["equity"] / curve[i - 1]["equity"] - 1 if curve[i - 1]["equity"] > 0 else 0.0
        b = buckets.setdefault(date_regime.get(curve[i]["date"], "range"),
                               {"days": 0, "grow": 1.0, "trade_count": 0, "wins": 0})
        b["days"] += 1
        b["grow"] *= 1 + r
    for t in result["trades"]:
        if t["side"] != "SELL":
            continue
        b = buckets.setdefault(date_regime.get(t["time"], "range"),
                               {"days": 0, "grow": 1.0, "trade_count": 0, "wins": 0})
        b["trade_count"] += 1
        b["wins"] += 1 if t.get("pnl", 0) > 0 else 0
    return {
        regime: {
            "days": b["days"],
            "return_pct": round((b["grow"] - 1) * 100, 2),
            "trade_count": b["trade_count"],
            "win_rate_pct": round(b["wins"] / b["trade_count"] * 100, 2) if b["trade_count"] else 0.0,
        }
        for regime, b in buckets.items()
    }


def compare_strategies(candles, index_candles=None, strategy_ids=None, capital=100000.0,
                       oos_folds=OOS_FOLDS, lot=100):
    """
    candles / index_candles: 升序 [{"time","open","high","low","close"}]。
    index_candles 缺省时用标的自身序列推断 regime。
    """
    n = len(candles)
    closes = [c["close"] for c in candles]
    ids = strategy_ids or [s["id"] for s in strategies.STRATEGIES]
    specs = [strategies.REGISTRY[i] for i in ids if i in strategies.REGISTRY]
    if not specs:
        raise ValueError("no known strategies")

    reg_candles = index_candles if index_candles and len(index_candles) >= 25 else candles
    reg_closes = [c["close"] for c in reg_candles]
    regimes = regime_series(reg_closes) if len(reg_closes) >= 25 else ["range"] * len(reg_candles)
    date_regime = {c["time"]: r for c, r in zip(reg_candles, regimes)}

    warmup = min(WARMUP, max(n // 2, 1))
    eval_len = n - warmup
    fold_size = max(eval_len // oos_folds, 1)

    results = []
    for spec in specs:
        params = strategies.clean_params(spec, {})
        signals = spec["signals"](closes, params)
        full = run_backtest(candles, signals, capital, lot=lot)

        folds, oos_rets = [], []
        for k in range(oos_folds):
            s = warmup + k * fold_size
            e = n if k == oos_folds - 1 else min(s + fold_size, n)
            if e - s < 2:
                continue
            seg = run_backtest(candles[s:e], signals[s:e], capital, lot=lot)
            folds.append({"from": candles[s]["time"], "to": candles[e - 1]["time"],
                          "return_pct": seg["metrics"]["total_return_pct"]})
            oos_rets.extend(_curve_returns(seg["equity_curve"]))
        oos_return = 1.0
        for f in folds:
            oos_return *= 1 + f["return_pct"] / 100
        fold_returns = [f["return_pct"] for f in folds]
        fold_std = 0.0
        if len(fold_returns) > 1:
            m = sum(fold_returns) / len(fold_returns)
            fold_std = math.sqrt(sum((x - m) ** 2 for x in fold_returns) / (len(fold_returns) - 1))

        results.append({
            "id": spec["id"],
            "name": spec["name"],
            "params": params,
            "metrics": full["metrics"],
            "oos": {
                "return_pct": round((oos_return - 1) * 100, 2),
                "sharpe": _sharpe(oos_rets),
                "folds": folds,
                "positive_folds": sum(1 for x in fold_returns if x > 0),
                "fold_std_pct": round(fold_std, 2),
            },
            "regime": _regime_breakdown(full, date_regime),
            "curve": [{"date": p["date"], "pct": round((p["equity"] / capital - 1) * 100, 2)}
                      for p in full["equity_curve"]],
        })

    results.sort(key=lambda r: (r["oos"]["sharpe"], r["oos"]["return_pct"]), reverse=True)
    for rank, r in enumerate(results, 1):
        r["rank"] = rank
    return {
        "capital": capital,
        "warmup": warmup,
        "folds": oos_folds,
        "regime_labels": REGIME_LABELS,
        "results": results,
    }


def strategy_advice(closes, current_regime, window=120):
    """
    当前大盘状态 → 适用策略推荐:优先看该 regime 下的条件化历史表现(有成交才采信),
    无成交时回退样本外 Sharpe 排序;返回 top3 带可解释理由。
    """
    seg = closes[-window:]
    if len(seg) < 60:
        return []
    from datetime import timedelta

    from django.utils import timezone

    base = timezone.localdate() - timedelta(days=len(seg))
    candles = [{"time": (base + timedelta(days=i)).strftime("%Y-%m-%d"),
                "open": c, "high": c, "low": c, "close": c}
               for i, c in enumerate(seg)]
    out = compare_strategies(candles, candles, lot=1)  # 指数研究按 1 单位,避免整手门槛
    label = REGIME_LABELS.get(current_regime, current_regime)
    ranked = []
    for r in out["results"]:
        bucket = r["regime"].get(current_regime)
        usable = bool(bucket and bucket["trade_count"] > 0)
        key = (
            1 if usable else 0,
            bucket["return_pct"] if usable else r["oos"]["return_pct"],
            r["oos"]["sharpe"],
        )
        if usable:
            reason = (f"{label}状态下历史区间收益 {bucket['return_pct']:+.2f}%"
                      f"({bucket['trade_count']} 笔、胜率 {bucket['win_rate_pct']}%),"
                      f"样本外 Sharpe {r['oos']['sharpe']}")
        else:
            reason = f"{label}状态下无成交记录,按样本外 Sharpe {r['oos']['sharpe']} 排序"
        ranked.append((key, {
            "id": r["id"], "name": r["name"],
            "regime_return_pct": bucket["return_pct"] if bucket else None,
            "regime_trades": bucket["trade_count"] if bucket else 0,
            "oos_sharpe": r["oos"]["sharpe"],
            "oos_return_pct": r["oos"]["return_pct"],
            "reason": reason,
        }))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in ranked[:3]]