"""行情数据:标的列表 / 指数 / K 线 / 板块 / 资讯。全部离线可运行,无外部依赖。"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Candle, NewsItem, Stock
from ..services.errors import BusinessError
from ..serializers import StockSerializer

TWO = Decimal("0.01")

# 指数定义:名称 / 基值 / 成分股代码前缀
INDEX_DEFS = [
    ("上证指数", 3000.0, ("600", "601", "603", "688")),
    ("深证成指", 10000.0, ("000", "001", "002")),
    ("创业板指", 2000.0, ("300", "301")),
]


class StockListView(ListAPIView):
    serializer_class = StockSerializer

    def get_queryset(self):
        # 只列出可交易股票;指数(kind=index)通过 /indices/ 提供
        return Stock.objects.filter(kind=Stock.Kind.STOCK, is_active=True)


class IndicesView(APIView):
    """
    指数行情:优先返回库内真实指数(kind=index,由模拟器每 tick 抓取腾讯实时行情维护);
    库内无指数数据时回退为按成分股聚合的模拟指数。
    """

    def get(self, request):
        indices = []
        for s in Stock.objects.filter(kind=Stock.Kind.INDEX).order_by("pk"):
            if s.prev_close <= 0:
                continue
            change = s.price - s.prev_close
            indices.append({
                "symbol": s.symbol,
                "name": s.name,
                "current": float(s.price),
                "prev_close": float(s.prev_close),
                "change": round(float(change), 2),
                "change_pct": round(float(s.change_pct), 2),
            })

        if not indices:  # 回退:成分股聚合的模拟指数
            stocks = list(Stock.objects.filter(kind=Stock.Kind.STOCK, is_active=True))
            for name, base, prefixes in INDEX_DEFS:
                members = [x for x in stocks if x.symbol.startswith(prefixes)]
                avg_pct = (sum(float(x.change_pct) for x in members) / len(members)) if members else 0.0
                current = round(base * (1 + avg_pct / 100), 2)
                indices.append({
                    "symbol": None,
                    "name": name,
                    "current": current,
                    "prev_close": base,
                    "change": round(current - base, 2),
                    "change_pct": round(avg_pct, 2),
                })
        return Response({"indices": indices})


class KlineView(APIView):
    """K 线:真实存储的模拟历史(?symbol=&period=1day|1min&limit=60)。"""

    def get(self, request):
        symbol = str(request.query_params.get("symbol", "")).strip()
        stock_id = request.query_params.get("stock_id")
        period = request.query_params.get("period", Candle.Period.DAY)
        if period not in Candle.Period.values:
            period = Candle.Period.DAY
        try:
            limit = min(max(int(request.query_params.get("limit", 60)), 1), 500)
        except (TypeError, ValueError):
            raise BusinessError("limit 必须为整数")

        if stock_id:
            stock = Stock.objects.filter(pk=stock_id).first()
        elif symbol:
            stock = Stock.objects.filter(symbol=symbol).first()
        else:
            raise BusinessError("需要提供 symbol 或 stock_id")
        if stock is None:
            raise BusinessError(f"未找到标的: {symbol or stock_id}")

        candles = list(
            Candle.objects.filter(stock=stock, period=period).order_by("-time")[:limit]
        )[::-1]  # 升序输出
        timestamps, klines, volumes = [], [], []
        for c in candles:
            local = timezone.localtime(c.time)
            if period == Candle.Period.DAY:
                timestamps.append(local.strftime("%Y-%m-%d"))
            else:
                timestamps.append(local.strftime("%m-%d %H:%M"))
            # 旧契约:[open, close, low, high]
            klines.append([float(c.open), float(c.close), float(c.low), float(c.high)])
            volumes.append(c.volume)
        return Response({"symbol": stock.symbol, "name": stock.name, "period": period,
                         "timestamps": timestamps, "klines": klines, "volumes": volumes})


class SectorsView(APIView):
    """板块走势:以「日期+板块」为种子的确定性随机游走,同一天内刷新结果稳定。"""

    def get(self, request):
        import random

        today = timezone.localdate()
        labels = [(today - timedelta(days=29 - i)).strftime("%m-%d") for i in range(30)]
        sectors = []
        for name, base, drift in (("金融", 100.0, 0.001), ("科技", 150.0, 0.002), ("医药", 120.0, 0.0015)):
            rnd = random.Random(f"{name}-{today.isoformat()}")
            value, values = base, []
            for _ in range(30):
                value *= 1 + rnd.uniform(-0.02, 0.02) + drift
                values.append(round(value, 2))
            sectors.append({"name": name, "values": values})
        return Response({"labels": labels, "sectors": sectors})


class NewsView(APIView):
    def get(self, request):
        news = NewsItem.objects.all()[:10]
        return Response([
            {"id": n.id, "title": n.title, "summary": n.summary,
             "source": n.source, "ts": timezone.localtime(n.published_at).isoformat()}
            for n in news
        ])
