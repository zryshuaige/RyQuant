"""
回测引擎:
- 信号在下一根 K 线开盘价执行(无未来函数);
- 全仓进出、按手数取整;佣金/印花税与实盘交易同费率;
- T+1 天然满足:每根 K 线只在开盘执行一次动作,买入当日不会再触发卖出。
"""
import math
from typing import Dict, List, Optional

from ..fees import buy_fee, sell_fee


def run_backtest(candles: List[Dict], signals: List[Optional[str]], initial_capital: float) -> Dict:
    """
    candles: 升序 [{"time": "YYYY-MM-DD", "open","high","low","close"}]
    signals: 与 candles 对齐的策略信号(在 K 线 i 收盘判定,i+1 开盘执行)。
    返回 metrics / equity_curve / candles / markers / trades。
    """
    n = len(candles)
    closes = [c["close"] for c in candles]

    cash = float(initial_capital)
    shares = 0
    avg_cost = 0.0  # 含买入佣金的摊薄成本
    equity_curve, markers, trades = [], [], []
    wins = sells = 0

    for i, candle in enumerate(candles):
        signal = signals[i] if i < len(signals) else None
        if i + 1 < n:  # 下一根开盘执行
            exec_candle = candles[i + 1]
            exec_price = exec_candle["open"]
            if signal == "BUY" and shares == 0:
                affordable = cash / (exec_price * 1.001)
                qty = int(affordable // 100) * 100  # 回测统一按 100 股一手取整
                if qty > 0:
                    amount = exec_price * qty
                    fee = float(buy_fee(amount))
                    cash -= amount + fee
                    avg_cost = (amount + fee) / qty
                    shares = qty
                    markers.append({"index": i + 1, "side": "BUY", "price": exec_price})
                    trades.append({
                        "time": exec_candle["time"], "side": "BUY", "quantity": qty,
                        "price": round(exec_price, 2), "amount": round(amount, 2), "fee": round(fee, 2),
                    })
            elif signal == "SELL" and shares > 0:
                amount = exec_price * shares
                fee = float(sell_fee(amount))
                pnl = (amount - fee) - avg_cost * shares
                cash += amount - fee
                trades.append({
                    "time": exec_candle["time"], "side": "SELL", "quantity": shares,
                    "price": round(exec_price, 2), "amount": round(amount, 2),
                    "fee": round(fee, 2), "pnl": round(pnl, 2),
                })
                markers.append({"index": i + 1, "side": "SELL", "price": exec_price})
                sells += 1
                wins += 1 if pnl > 0 else 0
                shares, avg_cost = 0, 0.0
        equity = cash + shares * closes[i]
        benchmark = float(initial_capital) * closes[i] / closes[0] if closes[0] else float(initial_capital)
        equity_curve.append({
            "date": candle["time"],
            "equity": round(equity, 2),
            "benchmark": round(benchmark, 2),
            "price": round(closes[i], 2),
        })

    # 剔除未执行的尾部信号已经天然满足(循环内只在 i+1 < n 时执行)

    final_equity = equity_curve[-1]["equity"] if equity_curve else float(initial_capital)
    total_return = (final_equity / float(initial_capital) - 1) * 100
    benchmark_return = (equity_curve[-1]["benchmark"] / float(initial_capital) - 1) * 100 if equity_curve else 0.0
    years = max(n / 250.0, 1 / 250.0)
    annualized = ((final_equity / float(initial_capital)) ** (1 / years) - 1) * 100 if final_equity > 0 else -100.0

    peak, max_drawdown = -math.inf, 0.0
    for point in equity_curve:
        peak = max(peak, point["equity"])
        if peak > 0:
            max_drawdown = min(max_drawdown, (point["equity"] / peak - 1) * 100)

    metrics = {
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(annualized, 2),
        "benchmark_return_pct": round(benchmark_return, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "trade_count": sells,
        "win_rate_pct": round(wins / sells * 100, 2) if sells else 0.0,
        "final_equity": round(final_equity, 2),
        "initial_capital": round(float(initial_capital), 2),
    }
    return {"metrics": metrics, "equity_curve": equity_curve, "markers": markers, "trades": trades}
