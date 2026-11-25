"""
标的注册表:本地检索 + 腾讯名称联想 + 按需落库 + 历史行情补齐。

产品约束:不预置全市场几千只股票。用户输入名称或代码,后端识别后落库,
再按需补齐 250 根日 K,后续即可加自选、看 K 线、做回测。
"""
import random
import re
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from ..models import Candle, Stock
from .errors import BusinessError
from .market_data import HISTORY_BARS, fetch_real_daily_netease, fetch_real_daily_tencent

TWO = Decimal("0.01")
CODE_RE = re.compile(r"^(?:(sh|sz|bj))?(\d{6})$", re.IGNORECASE)
SMARTBOX_URL = "https://smartbox.gtimg.cn/s3/"
MIN_HISTORY_BARS = 60


def _clean_query(value) -> str:
    return str(value or "").strip()[:32]


def _decode_escapes(value: str) -> str:
    r"""腾讯联想偶尔返回 \uXXXX 形式的转义名,解码成中文。"""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), str(value or ""))


def _bare_code(symbol: str) -> str:
    match = CODE_RE.match(symbol or "")
    return match.group(2) if match else ""


def _local_matches(query: str, limit: int = 8):
    raw = query
    if raw[:2].lower() in ("sh", "sz", "bj") and raw[2:].isdigit():
        raw = raw[2:]
    rows = (
        Stock.objects.filter(Q(symbol__icontains=raw) | Q(name__icontains=query))
        .order_by("kind", "symbol")[:limit]
    )
    return [
        {
            "symbol": stock.symbol,
            "code": _bare_code(stock.symbol) or stock.symbol,
            "name": stock.name,
            "kind": stock.kind,
            "in_db": True,
            "source": "local",
        }
        for stock in rows
    ]


def _remote_matches(query: str, limit: int = 6):
    """腾讯 smartbox 名称联想。返回 (结果列表, 远程是否可用)。"""
    try:
        import requests

        resp = requests.get(
            SMARTBOX_URL,
            params={"q": query, "t": "all"},
            timeout=4,
            headers={"User-Agent": "Mozilla/5.0 (RyQuant)"},
        )
        resp.encoding = "gbk"
        text = resp.text
        start, end = text.find('"'), text.rfind('"')
        if start == -1 or end <= start:
            return [], False
        payload = text[start + 1:end]
        if not payload or payload == "N":
            return [], True
        results, seen = [], set()
        for item in payload.split("^"):
            parts = item.split("~")
            if len(parts) < 5:
                continue
            market, code, name, _pinyin, sec_type = parts[:5]
            if sec_type != "GP-A" or not code.isdigit() or len(code) != 6:
                continue
            if code in seen:
                continue
            seen.add(code)
            results.append({
                "symbol": f"{market}{code}" if market in ("sh", "sz", "bj") else code,
                "code": code,
                "name": _decode_escapes(name),
                "kind": Stock.Kind.STOCK,
                "in_db": Stock.objects.filter(symbol=code).exists(),
                "source": "remote",
            })
            if len(results) >= limit:
                break
        return results, True
    except Exception:
        return [], False


def search_symbols(query: str):
    """本地优先 + 腾讯联想补全,按代码去重。远程失败时仍返回本地结果。"""
    q = _clean_query(query)
    if not q:
        return {"results": [], "remote_available": True}
    local = _local_matches(q)
    seen = {item["code"] for item in local}
    remote, remote_available = _remote_matches(q)
    results = local + [item for item in remote if item["code"] not in seen]
    return {"results": results[:8], "remote_available": remote_available}


def _fetch_quote(code: str):
    from .market_sim import fetch_realtime_quotes

    return fetch_realtime_quotes([code]).get(code)


def _parse_day(date_str):
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    return None


def _aware_day(day):
    return timezone.make_aware(datetime(day.year, day.month, day.day))


def fetch_history_rows(symbol: str, count: int = HISTORY_BARS):
    return fetch_real_daily_tencent(symbol, count=count) or fetch_real_daily_netease(symbol, count=count)


def _write_real_history(stock: Stock, rows) -> int:
    dedup = {}
    for date_str, open_, close, high, low, volume in rows:
        day = _parse_day(date_str)
        if day is None or close <= 0:
            continue
        dedup[day] = (open_, close, high, low, volume)
    if len(dedup) < MIN_HISTORY_BARS:
        return 0
    objs = [
        Candle(stock=stock, period=Candle.Period.DAY, time=_aware_day(day),
               open=open_, high=high, low=low, close=close, volume=volume,
               source=Candle.Source.REAL)
        for day, (open_, close, high, low, volume) in sorted(dedup.items())
    ]
    Candle.objects.bulk_create(objs, batch_size=500, ignore_conflicts=True)
    closes = [float(obj.close) for obj in objs]
    fields = []
    if stock.price <= 0:
        stock.price = Decimal(str(closes[-1])).quantize(TWO)
        fields.append("price")
    if stock.prev_close <= 0:
        stock.prev_close = Decimal(str(closes[-2])).quantize(TWO)
        fields.append("prev_close")
    if fields:
        stock.save(update_fields=fields + ["updated_at"])
    return len(objs)


def _business_days(count: int):
    """昨日(含)向前的 count 个交易日,跳过周末。"""
    days, cursor = [], timezone.localdate() - timedelta(days=1)
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def _write_sim_history(stock: Stock, fallback_price) -> int:
    base = stock.prev_close if stock.prev_close > 0 else (stock.price if stock.price > 0 else fallback_price)
    base = float(base or 100)
    rnd = random.Random(f"hist-{stock.symbol}")
    closes = [base] * HISTORY_BARS
    for i in range(HISTORY_BARS - 2, -1, -1):
        closes[i] = closes[i + 1] / (1 + rnd.uniform(-0.025, 0.025))
    objs = []
    for day, close in zip(_business_days(HISTORY_BARS), closes):
        open_ = close * (1 + rnd.uniform(-0.01, 0.01))
        high = max(open_, close) * (1 + rnd.uniform(0, 0.015))
        low = min(open_, close) * (1 - rnd.uniform(0, 0.015))
        objs.append(Candle(
            stock=stock, period=Candle.Period.DAY, time=_aware_day(day),
            open=round(open_, 2), high=round(high, 2), low=round(low, 2),
            close=round(close, 2), volume=rnd.randint(80_000, 3_000_000),
            source=Candle.Source.SIM,
        ))
    Candle.objects.bulk_create(objs, batch_size=500, ignore_conflicts=True)
    fields = []
    if stock.price <= 0:
        stock.price = Decimal(str(round(closes[-1], 2))).quantize(TWO)
        fields.append("price")
    if stock.prev_close <= 0:
        prev = closes[-2] if len(closes) > 1 else closes[-1]
        stock.prev_close = Decimal(str(round(prev, 2))).quantize(TWO)
        fields.append("prev_close")
    if fields:
        stock.save(update_fields=fields + ["updated_at"])
    return len(objs)


def ensure_daily_history(stock: Stock, fallback_price=None, rows=None) -> str:
    """确保有可回测的日 K:已有 → real → sim。返回 existing/real/sim。"""
    if Candle.objects.filter(stock=stock, period=Candle.Period.DAY).count() >= MIN_HISTORY_BARS:
        return "existing"
    real_rows = rows if rows is not None else fetch_history_rows(stock.symbol)
    if real_rows and _write_real_history(stock, real_rows):
        return "real"
    _write_sim_history(stock, fallback_price)
    return "sim"


def resolve_stock(query: str):
    """
    按代码/名称识别标的并落库。
    返回 (stock, created, history_source);无法识别时抛 BusinessError。
    """
    q = _clean_query(query)
    if not q:
        raise BusinessError("请输入股票代码或名称")

    match = CODE_RE.match(q)
    if not match:
        found = search_symbols(q)["results"]
        if not found:
            raise BusinessError("未找到该股票,请换个名称或输入 6 位代码")
        # 本地同名优先,其次腾讯联想第一条
        picked = next((x for x in found if x["in_db"]), found[0])
        if picked.get("kind") == Stock.Kind.INDEX:
            raise BusinessError("指数无需注册,可在行情页直接查看")
        match = CODE_RE.match(picked["symbol"])
        if not match:
            raise BusinessError("暂不支持该代码,请输入 A 股 6 位代码")

    code = match.group(2)
    if match.group(1):
        stock = Stock.objects.filter(symbol=q.lower()).first()
        if stock:
            return stock, False, ensure_daily_history(stock)
    stock = Stock.objects.filter(symbol=code).first()
    if stock:
        return stock, False, ensure_daily_history(stock)

    quote = _fetch_quote(code)
    if not quote or quote["current"] <= 0:
        raise BusinessError("无法获取该代码的行情,请确认代码是否正确")

    stock = Stock.objects.create(
        symbol=code,
        name=quote.get("name") or f"股票{code}",
        price=quote["current"],
        prev_close=quote["prev_close"],
        quote_source=Stock.QuoteSource.REAL,
        real_quote_at=timezone.localtime(),
        is_active=True,
    )
    history_source = ensure_daily_history(stock, fallback_price=quote["prev_close"])
    return stock, True, history_source