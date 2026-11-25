"""
一键生成演示数据(幂等,可重复执行):
- 24 只代表性股票(6 板块 × 4 只)+ 3 指数,用于大盘广度与板块统计
  这不是完整股票库:任意标的可在应用内输入名称/代码按需注册,见 stock_registry
- 日 K 优先抓取真实历史行情(腾讯,前复权),失败自动回退随机游走模拟
- 演示账户(demo / demo123456)与管理员(admin / admin123456)
- 演示自选 6 只(加入日期回填到过去,K 线标注可见,并参与加入以来收益统计)

用法:
  python manage.py seed_demo                    # 首次生成;已存在的股票跳过
  python manage.py seed_demo --refresh-history  # 删除现有 K 线并重新抓取真实历史
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from trading.models import Candle, Favorite, Stock
from trading.services.stock_registry import ensure_daily_history

STOCKS = [
    # 金融
    ("601318", "中国平安", "42.30"),
    ("000001", "平安银行", "13.88"),
    ("600036", "招商银行", "38.50"),
    ("600030", "中信证券", "28.60"),
    # 科技
    ("688981", "中芯国际", "99.00"),
    ("600410", "华胜天成", "22.80"),
    ("002415", "海康威视", "31.20"),
    ("603501", "韦尔股份", "118.00"),
    # 消费
    ("600519", "贵州茅台", "1688.00"),
    ("000858", "五粮液", "141.20"),
    ("000333", "美的集团", "72.50"),
    ("600887", "伊利股份", "28.40"),
    # 新能源
    ("300750", "宁德时代", "188.50"),
    ("002594", "比亚迪", "245.60"),
    ("601012", "隆基绿能", "18.90"),
    ("300274", "阳光电源", "78.30"),
    # 医药
    ("600276", "恒瑞医药", "46.80"),
    ("300760", "迈瑞医疗", "268.00"),
    ("000538", "云南白药", "57.20"),
    ("600196", "复星医药", "26.40"),
    # 能源
    ("601899", "紫金矿业", "17.80"),
    ("600028", "中国石化", "6.20"),
    ("601857", "中国石油", "8.10"),
    ("601088", "中国神华", "39.50"),
]

INDICES = [
    ("sh000001", "上证指数", "3000.00"),
    ("sz399001", "深证成指", "10000.00"),
    ("sz399006", "创业板指", "2000.00"),
]

DEMO_USERNAME, DEMO_PASSWORD = "demo", "demo123456"
ADMIN_USERNAME, ADMIN_PASSWORD = "admin", "admin123456"

# 演示自选:加入日期回填天数(控制在 45 天内,K 线默认可视窗口能看到金色标注)
DEMO_FAVORITES = [
    ("600519", 45),
    ("300750", 20),
    ("688981", 8),
    ("000858", 35),
    ("601318", 12),
    ("002594", 28),
]

SOURCE_LABEL = {"existing": "已有历史", "real": "真实历史", "sim": "模拟历史"}


class Command(BaseCommand):
    help = "生成演示数据:24 只演示标的/真实历史K线(离线自动模拟)/演示账户/自选股(幂等)"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument("--refresh-history", action="store_true",
                            help="删除现有 K 线并重新抓取(可将模拟历史升级为真实历史)")

    def handle(self, *args, **options):
        refresh = options["refresh_history"]

        # 1. 演示股票池 + 指数(仅用于行情展示、广度统计与回测)
        for symbol, name, price in STOCKS:
            stock, created = Stock.objects.get_or_create(symbol=symbol, defaults={"name": name})
            if created:
                self.stdout.write(f"  + 股票 {symbol} {name}")
            elif refresh:
                Candle.objects.filter(stock=stock).delete()
                self.stdout.write(f"  ↻ 股票 {symbol} {name} 刷新历史")
            else:
                self.stdout.write(f"  = 股票 {symbol} {name} 已存在,跳过(--refresh-history 可刷新)")
                continue
            source = ensure_daily_history(stock, fallback_price=Decimal(price))
            self.stdout.write(f"    K 线来源:{SOURCE_LABEL.get(source, source)}")

        for symbol, name, price in INDICES:
            stock, created = Stock.objects.get_or_create(
                symbol=symbol,
                defaults={"name": name, "kind": Stock.Kind.INDEX, "is_active": False},
            )
            if created:
                self.stdout.write(f"  + 指数 {symbol} {name}")
            elif refresh:
                Candle.objects.filter(stock=stock).delete()
                self.stdout.write(f"  ↻ 指数 {symbol} {name} 刷新历史")
            else:
                self.stdout.write(f"  = 指数 {symbol} {name} 已存在,跳过")
                continue
            source = ensure_daily_history(stock, fallback_price=Decimal(price))
            self.stdout.write(f"    K 线来源:{SOURCE_LABEL.get(source, source)}")

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

        # 3. 演示自选股:加入日期回填到过去,K 线标注落在默认可视窗口
        now = timezone.localtime()
        for symbol, days_ago in DEMO_FAVORITES:
            fav, fav_created = Favorite.objects.get_or_create(
                user=demo, stock=Stock.objects.get(symbol=symbol),
            )
            if fav_created:
                joined = now - timedelta(days=days_ago)
                while joined.weekday() >= 5:  # 吸附到交易日,K 线标注可见
                    joined -= timedelta(days=1)
                fav.created_at = joined
                fav.save(update_fields=["created_at"])
        self.stdout.write(f"  + 演示自选 {len(DEMO_FAVORITES)} 只(新建时加入日期回填到过去)")

        self.stdout.write(self.style.SUCCESS("演示数据就绪:python manage.py runserver 后访问前端即可体验"))