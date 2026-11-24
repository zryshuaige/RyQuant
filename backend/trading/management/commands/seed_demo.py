"""
一键生成演示数据(幂等,可重复执行):
- 8 只示例股票 + 250 根日 K + 最近一个交易日的分钟线(供图表与回测)
  日 K 优先抓取**真实历史行情**(腾讯行情接口,前复权);网络不可用时自动回退为随机游走模拟
- 模拟资讯、演示账户(demo / demo123456,VIP 已开通)、管理员(admin / admin123456)
- 通过真实交易服务产生历史委托与成交,保证资金/持仓/订单数据自洽

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

from trading.models import Candle, CashAccount, Favorite, NewsItem, Stock
from trading.services import matching
from trading.services import trading as trading_svc
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

NEWS = [
    ("央行开展 4500 亿元逆回购操作,市场流动性合理充裕", "公开市场操作净投放资金,机构预计月末资金面将保持平稳。"),
    ("三大指数集体收涨,科技板块领涨两市", "半导体、人工智能概念全天强势,成交额较上一交易日放大一成。"),
    ("多家券商上调全年盈利预测,看好高端制造景气度", "研报指出,设备更新与出口回暖共同拉动制造业投资。"),
    ("国际金价创阶段新高,避险情绪升温", "分析人士认为,短期金价或维持高位震荡,关注本周经济数据。"),
    ("新「国九条」落地一周年:上市公司分红总额创历史新高", "监管持续引导上市公司提高股东回报,红利资产受资金青睐。"),
    ("模拟盘小贴士:限价单未成交可撤单改价", "本平台为模拟交易环境,祝练习愉快,注意仓位管理。"),
]

DEMO_USERNAME, DEMO_PASSWORD = "demo", "demo123456"
ADMIN_USERNAME, ADMIN_PASSWORD = "admin", "admin123456"

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


def _seed_orders(demo: User) -> None:
    from trading.services.trading import place_order

    def filled_buy(symbol, quantity):
        stock = Stock.objects.get(symbol=symbol)
        order = place_order(demo, stock, side="BUY", quantity=quantity,
                            order_type="LIMIT", price=stock.price)
        assert order.status == "FILLED", f"{symbol} 演示买单未成交: {order.status}"

    filled_buy("000001", 200)
    filled_buy("600410", 400)
    filled_buy("300750", 100)

    # 卖出部分持仓,形成已实现盈亏
    stock = Stock.objects.get(symbol="600410")
    place_order(demo, stock, side="SELL", quantity=200, order_type="LIMIT", price=stock.price)

    # 一笔低于市价的限价买单 → 停留在 PENDING,展示「当前委托」与冻结资金
    wly = Stock.objects.get(symbol="000858")
    place_order(demo, wly, side="BUY", quantity=100,
                order_type="LIMIT", price=(wly.price * Decimal("0.96")).quantize(TWO))


class Command(BaseCommand):
    help = "生成演示数据:股票/真实历史K线(离线自动模拟)/资讯/演示账户/历史订单(幂等)"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--refresh-history", action="store_true",
                            help="删除现有 K 线并重新抓取(可将模拟历史升级为真实历史)")

    def handle(self, *args, **options):
        refresh = options["refresh_history"]

        # 1. 股票与历史行情(指数 kind=index,不可交易,仅供行情展示与回测)
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

        # 2. 资讯
        now = timezone.localtime()
        if not NewsItem.objects.exists():
            for i, (title, summary) in enumerate(NEWS):
                NewsItem.objects.create(
                    title=title, summary=summary, source="模拟财经",
                    published_at=now - timedelta(hours=i * 7),
                )
            self.stdout.write(f"  + 资讯 {len(NEWS)} 条")

        # 3. 管理员与演示账户
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
        cash, _ = CashAccount.objects.get_or_create(user=demo)
        if not cash.is_vip:
            cash.is_vip = True
            cash.save(update_fields=["is_vip", "updated_at"])

        # 4. 演示订单:通过真实交易服务产生,保证数据自洽;无限流动性使限价单立即成交
        if refresh and not created:
            # 价格已刷新,同步重建演示账户的持仓/委托,避免旧成本价与新行情脱节
            from django.db import transaction

            with transaction.atomic():
                demo.orders.all().delete()   # 级联删除成交回报
                demo.positions.all().delete()
                cash.balance = trading_svc._initial_capital()
                cash.frozen_cash = Decimal("0.00")
                cash.save(update_fields=["balance", "frozen_cash", "updated_at"])
            self.stdout.write("  ↻ 已重置演示账户交易数据(适配新价格)")

        if created or refresh:
            original = matching._liquidity
            matching._liquidity = lambda stock, order: 10 ** 9
            try:
                _seed_orders(demo)
            finally:
                matching._liquidity = original
            for symbol in ("600519", "300750", "688981"):
                Favorite.objects.get_or_create(user=demo, stock=Stock.objects.get(symbol=symbol))
            self.stdout.write(f"  + 演示账户 {DEMO_USERNAME}/{DEMO_PASSWORD}(VIP,含历史委托与持仓)")
        else:
            self.stdout.write(f"  = 演示账户 {DEMO_USERNAME} 已存在,跳过订单初始化")

        self.stdout.write(self.style.SUCCESS("演示数据就绪:python manage.py runserver 后访问前端即可体验"))
