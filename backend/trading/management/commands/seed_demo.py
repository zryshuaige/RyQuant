"""
一键生成演示数据(幂等,可重复执行):
- 8 只示例股票 + 3 指数 + 250 根日 K + 最近一个交易日的分钟线(供图表与回测)
  日 K 优先抓取**真实历史行情**(腾讯行情接口,前复权);网络不可用时自动回退为随机游走模拟
- 演示账户(demo / demo123456)与管理员(admin / admin123456)
- 演示自选股(加入日期回填到过去,K 线标注可见)

用法:
  python manage.py seed_demo                    # 首次生成;已存在的股票跳过
  python manage.py seed_demo --refresh-history  # 删除现有 K 线并重新抓取真实历史
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from trading.models import Candle, Favorite, Stock
from trading.services.market_data import (
    HISTORY_BARS,
    fetch_real_daily_netease,
    fetch_real_daily_tencent,
)

TWO = Decimal("0.01")

STOCKS = [
    ("600519", "贵州茅台", "1688.00"),
    ("000001", "平安银行", "13.88"),
    ("688981", "中芯国际", "99.00"),
    ("300750", "宁德时代", "188.50"),
    ("601318", "中国平安", "42.30"),
    ("000858", "五粮液", "141.20"),
    ("002594", "比亚迪", "245.60"),
    ("600410", "华胜天成", "22.80"),
]

INDICES = [
    ("sh000001", "上证指数", "3000.00"),
    ("sz399001", "深证成指", "10000.00"),
    ("sz399006", "创业板指", "2000.00"),
]

DEMO_USERNAME, DEMO_PASSWORD = "demo", "demo123456"
ADMIN_USERNAME, ADMIN_PASSWORD = "admin", "admin123456"

# 演示自选:加入日期回填天数(让 K 线 markLine 落在可视窗口内)
DEMO_FAVORITES = [("600519", 45), ("300750", 20), ("688981", 8)]


def _business_dates(count: int):
    """自今日(含)向前的 count 个交易日(跳过周末),用于模拟数据。"""
    dates = []
    cursor = timezone.localdate()
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor -= timedelta(days=1)
    return dates


def _simulate_closes(end_price: Decimal, count: int, seed: str):
    """随机游走生成 count 个收盘价(升序,末位=end_price)。"""
    rnd = random.Random(f"hist-{seed}")
    closes = [end_price] * count
    for i in range(count - 2, -1, -1):
        closes[i] = (closes[i + 1] / (1 + Decimal(str(rnd.uniform(-0.025, 0.025))))).quantize(TWO)
    return closes, rnd


def _seed_history(stock: Stock, fallback_price: Decimal, out) -> None:
    """写入 250 根日 K(真实优先)+ 最近一个交易日分钟线,并更新现价/昨收。"""
    real = fetch_real_daily_tencent(stock.symbol) or fetch_real_daily_netease(stock.symbol)

    if real and len(real) >= 60:
        source = "真实历史"
        # 数据源可能包含重复日期(停牌复牌等),按日期去重保序
        dedup = {}
        for date_str, o, c, h, l, vol in real:
            key = str(date_str)
            if key not in dedup and c > 0:
                dedup[key] = (date_str, o, c, h, l, vol)
        rows = []
        for date_str, o, c, h, l, vol in dedup.values():
            t = timezone.make_aware(timezone.datetime.strptime(date_str, "%Y%m%d")) \
                if len(date_str) == 8 and date_str.isdigit() \
                else timezone.make_aware(timezone.datetime.strptime(date_str, "%Y-%m-%d"))
            rows.append(Candle(stock=stock, period=Candle.Period.DAY, time=t,
                               open=o, high=h, low=l, close=c, volume=vol,
                               source=Candle.Source.REAL))
        closes = [r.close for r in rows]
    else:
        source = "模拟"
        dates = _business_dates(HISTORY_BARS)
        closes, rnd = _simulate_closes(fallback_price, HISTORY_BARS, stock.symbol)
        rows = []
        for date, close_price in zip(dates, closes):
            open_price = (close_price * (1 + Decimal(str(rnd.uniform(-0.01, 0.01))))).quantize(TWO)
            high = max(open_price, close_price) * (1 + Decimal(str(rnd.uniform(0, 0.015)))).quantize(TWO)
            low = min(open_price, close_price) * (1 - Decimal(str(rnd.uniform(0, 0.015)))).quantize(TWO)
            rows.append(Candle(
                stock=stock, period=Candle.Period.DAY,
                time=timezone.make_aware(timezone.datetime(date.year, date.month, date.day)),
                open=open_price, high=high, low=low, close=close_price,
                volume=rnd.randint(80_000, 3_000_000),
            ))
    Candle.objects.bulk_create(rows, batch_size=500, ignore_conflicts=True)
    # 最近一个交易日的分钟线(09:30-11:30 / 13:00-15:00),围绕最新收盘价模拟
    rnd = random.Random(f"min-{stock.symbol}")
    last_date = timezone.localdate()
    while last_date.weekday() >= 5:  # 分钟线只落在交易日(周末回退到周五)
        last_date -= timedelta(days=1)
    minute_closes = [closes[-1]]
    for _ in range(239):
        minute_closes.append((minute_closes[-1] * (1 + Decimal(str(rnd.uniform(-0.004, 0.004))))).quantize(TWO))
    minute_rows = []
    for i, c in enumerate(minute_closes):
        offset = i if i < 120 else i + 60  # 跳过午休 60 分钟
        t = timezone.datetime(last_date.year, last_date.month, last_date.day, 9, 30) + timedelta(minutes=offset)
        minute_rows.append(Candle(
            stock=stock, period=Candle.Period.MINUTE, time=timezone.make_aware(t),
            open=c, high=c, low=c, close=c, volume=rnd.randint(stock.lot_size, stock.lot_size * 6),
        ))
    # ignore_conflicts:与运行中的行情模拟器并发时,同一分钟 K 线可能已被服务端创建,安全跳过
    Candle.objects.bulk_create(minute_rows, batch_size=500, ignore_conflicts=True)

    stock.price = closes[-1]
    stock.prev_close = closes[-2]
    stock.save(update_fields=["price", "prev_close", "updated_at"])
    out(f"    K 线来源:{source}({len(rows)} 根,最新收盘 {closes[-1]})")


class Command(BaseCommand):
    help = "生成演示数据:股票/真实历史K线(离线自动模拟)/演示账户/自选股(幂等)"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--refresh-history", action="store_true",
                            help="删除现有 K 线并重新抓取(可将模拟历史升级为真实历史)")

    def handle(self, *args, **options):
        refresh = options["refresh_history"]

        # 1. 股票与历史行情(指数 kind=index,仅供行情展示与回测)
        for symbol, name, price in STOCKS:
            stock, created = Stock.objects.get_or_create(symbol=symbol, defaults={"name": name})
            if created:
                self.stdout.write(f"  + 股票 {symbol} {name}")
                _seed_history(stock, Decimal(price), self.stdout.write)
            elif refresh:
                Candle.objects.filter(stock=stock).delete()
                self.stdout.write(f"  ↻ 股票 {symbol} {name} 刷新历史")
                _seed_history(stock, stock.price or Decimal(price), self.stdout.write)
            else:
                self.stdout.write(f"  = 股票 {symbol} {name} 已存在,跳过(--refresh-history 可刷新)")

        for symbol, name, price in INDICES:
            stock, created = Stock.objects.get_or_create(
                symbol=symbol,
                defaults={"name": name, "kind": Stock.Kind.INDEX, "is_active": False},
            )
            if created:
                self.stdout.write(f"  + 指数 {symbol} {name}")
                _seed_history(stock, Decimal(price), self.stdout.write)
            elif refresh:
                Candle.objects.filter(stock=stock).delete()
                self.stdout.write(f"  ↻ 指数 {symbol} {name} 刷新历史")
                _seed_history(stock, stock.price or Decimal(price), self.stdout.write)
            else:
                self.stdout.write(f"  = 指数 {symbol} {name} 已存在,跳过")

        # 2. 管理员与演示账户
        if not User.objects.filter(username=ADMIN_USERNAME).exists():
            User.objects.create_superuser(ADMIN_USERNAME, "admin@example.com", ADMIN_PASSWORD)
            self.stdout.write(f"  + 管理员 {ADMIN_USERNAME}/{ADMIN_PASSWORD}")

        demo, created = User.objects.get_or_create(
            username=DEMO_USERNAME,
            defaults={"email": "demo@example.com"},
        )
        if created:
            demo.set_password(DEMO_PASSWORD)
            demo.save()
            self.stdout.write(f"  + 演示账户 {DEMO_USERNAME}/{DEMO_PASSWORD}")
        else:
            self.stdout.write(f"  = 演示账户 {DEMO_USERNAME} 已存在")

        # 3. 演示自选股:加入日期回填到过去,K 线标注落在可视窗口
        now = timezone.localtime()
        for symbol, days_ago in DEMO_FAVORITES:
            fav, fav_created = Favorite.objects.get_or_create(
                user=demo, stock=Stock.objects.get(symbol=symbol),
            )
            if fav_created:
                fav.created_at = now - timedelta(days=days_ago)
                fav.save(update_fields=["created_at"])
        self.stdout.write(f"  + 演示自选 {len(DEMO_FAVORITES)} 只(加入日期已回填)")

        self.stdout.write(self.style.SUCCESS("演示数据就绪:python manage.py runserver 后访问前端即可体验"))