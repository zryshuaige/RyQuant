"""
自选跟踪:加入自选以来的收益、同期上证表现与超额收益。

产品含义:加入日期不只是 K 线上的一条线,而是这段持有期的起点。
"""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from ..models import Candle, Favorite, Stock


def _daily_closes(stock_ids, since):
    rows = (
        Candle.objects.filter(stock_id__in=stock_ids, period=Candle.Period.DAY, time__date__gte=since)
        .order_by("stock_id", "time")
        .values_list("stock_id", "time", "close")
    )
    series = defaultdict(list)
    for stock_id, time, close in rows:
        series[stock_id].append((timezone.localtime(time).date(), float(close)))
    return series


def _first_close(series, since):
    for day, close in series:
        if day >= since and close > 0:
            return day, close
    return None, None


def _asof(series, day):
    value = None
    for item_day, close in series:
        if item_day > day:
            break
        value = close
    return value


def _spark_points(stock_series, bench_series, joined, stock_join, bench_join,
                  stock_now, bench_now, limit=30):
    days = sorted({d for d, _ in stock_series if d >= joined} | {d for d, _ in bench_series if d >= joined})
    today = timezone.localdate()
    if days and days[-1] < today:
        days.append(today)
    if not days:
        return []
    if len(days) > limit:
        step = (len(days) - 1) / (limit - 1)
        days = [days[round(i * step)] for i in range(limit)]
    points = []
    for day in days:
        stock_close = stock_now if day == today else _asof(stock_series, day)
        bench_close = bench_now if day == today else _asof(bench_series, day)
        if not stock_close or not bench_close or not stock_join or not bench_join:
            continue
        points.append({
            "date": day.isoformat(),
            "stock_pct": round((stock_close / stock_join - 1) * 100, 2),
            "bench_pct": round((bench_close / bench_join - 1) * 100, 2),
        })
    return points


def favorites_summary(user):
    """一次批量查询算出所有自选的加入以来表现。"""
    favorites = list(
        Favorite.objects.filter(user=user).select_related("stock").order_by("-created_at", "-pk")
    )
    if not favorites:
        return {
            "count": 0, "avg_return_pct": 0.0, "beat_count": 0, "best": None,
            "benchmark": None, "items": [],
        }

    benchmark = (
        Stock.objects.filter(kind=Stock.Kind.INDEX, symbol="sh000001").first()
        or Stock.objects.filter(kind=Stock.Kind.INDEX).order_by("pk").first()
    )
    today = timezone.localdate()
    joined_days = {fav.id: timezone.localtime(fav.created_at).date() for fav in favorites}
    since = min(joined_days.values())
    stock_ids = [fav.stock_id for fav in favorites]
    if benchmark:
        stock_ids.append(benchmark.id)

    series = _daily_closes(stock_ids, since - timedelta(days=7))
    bench_series = series.get(benchmark.id, []) if benchmark else []
    bench_now = float(benchmark.price) if benchmark and benchmark.price > 0 else (
        bench_series[-1][1] if bench_series else None
    )

    items = []
    for fav in favorites:
        stock = fav.stock
        joined = joined_days[fav.id]
        stock_series = series.get(stock.id, [])
        join_day, join_price = _first_close(stock_series, joined)
        current = float(stock.price) if stock.price > 0 else (
            stock_series[-1][1] if stock_series else join_price
        )
        bench_join_day, bench_join = _first_close(bench_series, joined)
        if not join_price or not current:
            continue
        return_pct = round((current / join_price - 1) * 100, 2)
        bench_pct = (
            round((bench_now / bench_join - 1) * 100, 2)
            if bench_join and bench_now else 0.0
        )
        items.append({
            "stock": stock,
            "joined_at": joined.isoformat(),
            "join_date": join_day.isoformat() if join_day else joined.isoformat(),
            "join_price": round(join_price, 2),
            "current_price": round(current, 2),
            "return_pct": return_pct,
            "benchmark_return_pct": bench_pct,
            "excess_pct": round(return_pct - bench_pct, 2),
            "days_held": max((today - joined).days, 0),
            "series": _spark_points(stock_series, bench_series, joined,
                                    join_price, bench_join, current, bench_now),
        })

    if not items:
        return {
            "count": 0, "avg_return_pct": 0.0, "beat_count": 0, "best": None,
            "benchmark": None, "items": [],
        }

    avg = round(sum(item["return_pct"] for item in items) / len(items), 2)
    best = max(items, key=lambda item: item["return_pct"])
    return {
        "count": len(items),
        "avg_return_pct": avg,
        "beat_count": sum(1 for item in items if item["excess_pct"] > 0),
        "best": {
            "symbol": best["stock"].symbol,
            "name": best["stock"].name,
            "return_pct": best["return_pct"],
        },
        "benchmark": (
            {"symbol": benchmark.symbol, "name": benchmark.name} if benchmark else None
        ),
        "items": items,
    }