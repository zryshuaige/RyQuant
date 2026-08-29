"""
行情模拟器:后台线程周期性推动价格随机游走(受涨跌停约束),
聚合分钟/日 K 线,并驱动撮合引擎。
- 股票:随机游走模拟(基线可由 seed 抓取的真实历史覆盖)
- 指数(kind=index):每 tick 抓取腾讯**真实实时行情**,失败自动回退随机游走
"""
import logging
import random
import threading
import time
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from ..models import Candle, Stock
from . import matching

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
TICK_VOLATILITY = 0.006  # 单 tick 最大波动 ±0.6%

_thread = None


def _minute_start(dt):
    return dt.replace(second=0, microsecond=0)


def _day_start(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def fetch_realtime_quotes(symbols):
    """
    腾讯实时行情(s_ 简要接口):v_s_sh000001="1~上证指数~000001~3042.53~2999.75~42.78~1.43~..."
    返回 {symbol: {current, prev_close, change, change_pct}},失败返回 {}。
    """
    if not symbols:
        return {}
    try:
        import requests

        resp = requests.get(
            "https://qt.gtimg.cn/q=" + ",".join(f"s_{s}" for s in symbols),
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (FinQuant)"},
        )
        resp.encoding = "gbk"
        quotes = {}
        for line in resp.text.split(";"):
            line = line.strip()
            if "=" not in line or '"' not in line:
                continue
            key = line.split("=", 1)[0].strip().replace("v_s_", "")
            fields = line.split('"', 1)[1].split("~")
            if len(fields) < 7:
                continue
            try:
                quotes[key] = {
                    "current": Decimal(fields[3]).quantize(TWO_PLACES),
                    "prev_close": Decimal(fields[4]).quantize(TWO_PLACES),
                    "change": Decimal(fields[5]).quantize(TWO_PLACES),
                    "change_pct": Decimal(fields[6]).quantize(TWO_PLACES),
                }
            except Exception:
                continue
        return quotes
    except Exception:
        return {}


def _update_candle(stock, now, price: Decimal, volume: int, period: str, bucket) -> None:
    candle, created = Candle.objects.get_or_create(
        stock=stock, period=period, time=bucket,
        defaults={"open": price, "high": price, "low": price, "close": price, "volume": volume},
    )
    if not created:
        candle.high = max(candle.high, price)
        candle.low = min(candle.low, price)
        candle.close = price
        candle.volume += volume
        candle.save(update_fields=["high", "low", "close", "volume"])


@transaction.atomic
def _tick_stock(stock: Stock, now) -> None:
    pct = random.uniform(-TICK_VOLATILITY, TICK_VOLATILITY)
    new_price = (stock.price * Decimal(str(1 + pct))).quantize(TWO_PLACES, ROUND_HALF_UP)
    if stock.prev_close > 0:
        new_price = min(max(new_price, stock.limit_down), stock.limit_up)
    if new_price <= 0:
        return

    _apply_price(stock, now, new_price, random.randint(stock.lot_size, stock.lot_size * 8))
    matching.match_pending_orders(stock)


@transaction.atomic
def _tick_index(stock: Stock, now, quote) -> None:
    """指数 tick:优先真实实时报价;无报价(离线)时随机游走兜底。"""
    if quote is not None and quote["current"] > 0:
        new_price = quote["current"]
        if quote["prev_close"] > 0:
            stock.prev_close = quote["prev_close"]
    else:
        pct = random.uniform(-TICK_VOLATILITY * 0.6, TICK_VOLATILITY * 0.6)
        new_price = (stock.price * Decimal(str(1 + pct))).quantize(TWO_PLACES, ROUND_HALF_UP)
        if new_price <= 0:
            return

    _apply_price(stock, now, new_price, random.randint(800, 9000))


def _apply_price(stock: Stock, now, new_price: Decimal, volume: int) -> None:
    """更新价格 → 聚合分钟/日 K。撮合由股票路径单独调用。"""
    stock.price = new_price
    stock.save(update_fields=["price", "prev_close", "updated_at"])
    _update_candle(stock, now, new_price, volume, Candle.Period.MINUTE, _minute_start(now))
    _update_candle(stock, now, new_price, volume, Candle.Period.DAY, _day_start(now))


def tick() -> None:
    """推进一个行情周期:股票随机游走 + 撮合;指数接真实实时行情。"""
    global _index_symbols
    now = timezone.localtime()

    indices = list(Stock.objects.filter(kind=Stock.Kind.INDEX).order_by("symbol"))
    quotes = fetch_realtime_quotes([s.symbol for s in indices]) if indices else {}
    for stock in indices:
        _tick_index(stock, now, quotes.get(stock.symbol))

    for stock in Stock.objects.filter(kind=Stock.Kind.STOCK, is_active=True).order_by("symbol"):
        _tick_stock(stock, now)


def _loop() -> None:
    interval = max(getattr(settings, "SIMULATOR_TICK_SECONDS", 3), 1)
    while True:
        time.sleep(interval)
        try:
            close_old_connections()
            tick()
            close_old_connections()
        except Exception:
            logger.exception("行情模拟 tick 失败")


def start_simulator() -> None:
    """启动守护线程(幂等)。仅由 AppConfig.ready 在 runserver 服务进程中调用。"""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, name="market-simulator", daemon=True)
    _thread.start()
    logger.info("行情模拟器已启动,每 %s 秒 tick", settings.SIMULATOR_TICK_SECONDS)
