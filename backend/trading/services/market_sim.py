"""
行情模拟器:后台线程周期性推动价格(受涨跌停约束),
聚合分钟/日 K 线,并驱动撮合引擎。
- 个股与指数:每 tick 批量抓取腾讯**真实实时行情**(完整格式),逐标的失败回退随机游走
- 离线(无报价)时全模拟,接口契约不变;行情来源记录于 Stock.quote_source / Candle.source
"""
import logging
import random
import threading
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from ..models import Candle, Stock
from .market_data import fetch_real_daily_tencent, tencent_code

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
TICK_VOLATILITY = 0.006  # 单 tick 最大波动 ±0.6%
PCT_TOLERANCE = Decimal("0.05")  # 报告涨跌幅与现价/昨收推算值的自校验容差

_thread = None
_last_refresh_date = None
_prev_quote_volume = {}  # 真实报价当日累计量缓存,用于分钟增量


def _minute_start(dt):
    return dt.replace(second=0, microsecond=0)


def _day_start(dt):
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def fetch_realtime_quotes(symbols):
    """
    腾讯实时行情(完整格式):v_sh600519="1~贵州茅台~600519~现价~昨收~今开~成交量(手)~...~涨跌~涨跌幅~最高~最低~..."
    字段位:3=现价 4=昨收 6=成交量(手) 31=涨跌额 32=涨跌幅 33=最高 34=最低。
    返回 {symbol: {current, prev_close, change, change_pct, high, low, volume(股)}},失败返回 {}。
    自校验:报告涨跌幅与现价/昨收推算值偏差 >0.05 视为解析失败,防止字段错位污染行情。
    """
    if not symbols:
        return {}
    code_map = {tencent_code(s): s for s in symbols}
    try:
        import requests

        resp = requests.get(
            "https://qt.gtimg.cn/q=" + ",".join(code_map),
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (RyQuant)"},
        )
        resp.encoding = "gbk"
        quotes = {}
        for line in resp.text.split(";"):
            line = line.strip()
            if "=" not in line or '"' not in line:
                continue
            key = line.split("=", 1)[0].strip().replace("v_", "")
            symbol = code_map.get(key)
            if symbol is None:
                continue
            fields = line.split('"', 1)[1].split("~")
            if len(fields) < 38:
                continue
            try:
                current = Decimal(fields[3]).quantize(TWO_PLACES)
                prev_close = Decimal(fields[4]).quantize(TWO_PLACES)
                change_pct = Decimal(fields[32]).quantize(TWO_PLACES)
                if current <= 0 or prev_close <= 0:
                    continue
                calc_pct = (current - prev_close) / prev_close * 100
                if abs(calc_pct - change_pct) > PCT_TOLERANCE:
                    continue
                quotes[symbol] = {
                    "name": fields[1].strip(),
                    "current": current,
                    "prev_close": prev_close,
                    "change": Decimal(fields[31]).quantize(TWO_PLACES),
                    "change_pct": change_pct,
                    "high": Decimal(fields[33]).quantize(TWO_PLACES),
                    "low": Decimal(fields[34]).quantize(TWO_PLACES),
                    "volume": int(float(fields[6])) * 100,  # 手 → 股
                }
            except Exception:
                continue
        return quotes
    except Exception:
        return {}


def _update_candle(stock, now, price: Decimal, volume: int, period: str, bucket,
                   high=None, low=None, source=Candle.Source.SIM, volume_total=False) -> None:
    candle, created = Candle.objects.get_or_create(
        stock=stock, period=period, time=bucket,
        defaults={"open": price, "high": high or price, "low": low or price,
                  "close": price, "volume": volume, "source": source},
    )
    if not created:
        candle.high = max(candle.high, high or price)
        candle.low = min(candle.low, low or price)
        candle.close = price
        # 真实报价的量是当日累计值→覆盖;模拟/分钟增量→累加
        candle.volume = volume if volume_total else candle.volume + volume
        candle.source = source
        candle.save(update_fields=["high", "low", "close", "volume", "source"])


@transaction.atomic
def _tick_stock(stock: Stock, now) -> None:
    """离线兜底:随机游走模拟 tick。"""
    pct = random.uniform(-TICK_VOLATILITY, TICK_VOLATILITY)
    new_price = (stock.price * Decimal(str(1 + pct))).quantize(TWO_PLACES, ROUND_HALF_UP)
    if stock.prev_close > 0:
        new_price = min(max(new_price, stock.limit_down), stock.limit_up)
    if new_price <= 0:
        return

    stock.quote_source = Stock.QuoteSource.SIM
    _apply_price(stock, now, new_price, random.randint(stock.lot_size, stock.lot_size * 8))


@transaction.atomic
def _tick_stock_real(stock: Stock, now, quote) -> None:
    """真实报价 tick:现价/昨收/高低来自腾讯;日量=当日累计覆盖,分钟量=相邻 tick 增量。"""
    stock.prev_close = quote["prev_close"]
    stock.quote_source = Stock.QuoteSource.REAL
    stock.real_quote_at = now
    new_price = min(max(quote["current"], stock.limit_down), stock.limit_up)
    prev = _prev_quote_volume.get(stock.symbol, 0)
    delta = max(quote["volume"] - prev, 0)
    _prev_quote_volume[stock.symbol] = quote["volume"]
    _apply_price(stock, now, new_price, delta, quote["high"], quote["low"], volume_total=quote["volume"])


@transaction.atomic
def _tick_index(stock: Stock, now, quote) -> None:
    """指数 tick:优先真实实时报价;无报价(离线)时随机游走兜底。"""
    if quote is not None and quote["current"] > 0:
        new_price = quote["current"]
        if quote["prev_close"] > 0:
            stock.prev_close = quote["prev_close"]
        stock.quote_source = Stock.QuoteSource.REAL
        stock.real_quote_at = now
        prev = _prev_quote_volume.get(stock.symbol, 0)
        delta = max(quote["volume"] - prev, 0)
        _prev_quote_volume[stock.symbol] = quote["volume"]
        volume, high, low = delta, quote["high"], quote["low"]
        _apply_price(stock, now, new_price, volume, high, low, volume_total=quote["volume"])
        return
    else:
        pct = random.uniform(-TICK_VOLATILITY * 0.6, TICK_VOLATILITY * 0.6)
        new_price = (stock.price * Decimal(str(1 + pct))).quantize(TWO_PLACES, ROUND_HALF_UP)
        if new_price <= 0:
            return
        stock.quote_source = Stock.QuoteSource.SIM
        volume, high, low = random.randint(800, 9000), None, None

    _apply_price(stock, now, new_price, volume, high, low)


def _apply_price(stock: Stock, now, new_price: Decimal, volume: int, high=None, low=None,
                 volume_total=None) -> None:
    """更新价格 → 聚合分钟/日 K。volume 为分钟增量;volume_total 非 None 时作为当日累计量覆盖日 K。"""
    stock.price = new_price
    stock.save(update_fields=["price", "prev_close", "quote_source", "real_quote_at", "updated_at"])
    source = stock.quote_source
    _update_candle(stock, now, new_price, volume, Candle.Period.MINUTE, _minute_start(now), high, low, source)
    day_volume = volume_total if volume_total is not None else volume
    _update_candle(stock, now, new_price, day_volume, Candle.Period.DAY, _day_start(now),
                   high, low, source, volume_total=volume_total is not None)


def _parse_day(date_str):
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    return None


def _maybe_refresh_daily(now, stocks) -> None:
    """每交易日一次:后台线程增量补抓腾讯真实日 K(失败静默),不阻塞 tick 主循环。"""
    global _last_refresh_date
    today = now.date()
    if _last_refresh_date == today or now.weekday() >= 5:
        return
    _last_refresh_date = today
    threading.Thread(target=_refresh_daily_all, args=(list(stocks), today),
                     name="daily-history-refresh", daemon=True).start()


def _refresh_daily_all(stocks, today) -> None:
    close_old_connections()
    for stock in stocks:
        try:
            rows = fetch_real_daily_tencent(stock.symbol, count=5)
            if not rows:
                continue
            for date_str, o, c, h, l, vol in rows:
                day = _parse_day(date_str)
                if day is None or day >= today:
                    continue  # 不覆盖当日实时聚合的 K 线
                Candle.objects.update_or_create(
                    stock=stock, period=Candle.Period.DAY,
                    time=timezone.make_aware(timezone.datetime(day.year, day.month, day.day)),
                    defaults={"open": o, "high": h, "low": l, "close": c, "volume": vol,
                              "source": Candle.Source.REAL},
                )
        except Exception:
            logger.debug("日 K 增量刷新失败: %s", stock.symbol, exc_info=True)
    close_old_connections()


def tick() -> None:
    """推进一个行情周期:个股/指数批量接真实实时行情,逐标的失败回退随机游走 + 撮合。"""
    now = timezone.localtime()

    indices = list(Stock.objects.filter(kind=Stock.Kind.INDEX).order_by("symbol"))
    stocks = list(Stock.objects.filter(kind=Stock.Kind.STOCK, is_active=True).order_by("symbol"))
    quotes = fetch_realtime_quotes([s.symbol for s in indices + stocks])
    for stock in indices:
        _tick_index(stock, now, quotes.get(stock.symbol))

    for stock in stocks:
        quote = quotes.get(stock.symbol)
        if quote is not None and quote["current"] > 0:
            _tick_stock_real(stock, now, quote)
        else:
            _tick_stock(stock, now)

    _maybe_refresh_daily(now, indices + stocks)


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