"""行情数据:标的列表 / 指数 / K 线 / 板块 / 资讯。全部离线可运行,无外部依赖。"""
from decimal import Decimal

from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Candle, NewsItem, Stock
from ..services.errors import BusinessError
from ..services.market_data import SECTOR_MEMBERS
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
                "quote_source": s.quote_source,
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
                    "quote_source": Stock.QuoteSource.SIM,
                })
        return Response({"indices": indices})


class KlineView(APIView):
    """K 线(?symbol=&period=1day|1min&limit=60);sources 逐根标注真实/模拟来源。"""

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
        timestamps, klines, volumes, sources = [], [], [], []
        for c in candles:
            local = timezone.localtime(c.time)
            if period == Candle.Period.DAY:
                timestamps.append(local.strftime("%Y-%m-%d"))
            else:
                timestamps.append(local.strftime("%m-%d %H:%M"))
            # 旧契约:[open, close, low, high]
            klines.append([float(c.open), float(c.close), float(c.low), float(c.high)])
            volumes.append(c.volume)
            sources.append(c.source)
        return Response({"symbol": stock.symbol, "name": stock.name, "period": period,
                         "timestamps": timestamps, "klines": klines, "volumes": volumes,
                         "sources": sources, "quote_source": stock.quote_source})


class SectorsView(APIView):
    """板块走势:由成分股真实日 K 计算(成员归一化收盘均值,基期=100),
    change_pct 为成员当前涨跌幅均值(真实报价或离线模拟)。成分映射见 market_data.SECTOR_MEMBERS。"""

    def get(self, request):
        stocks = {s.symbol: s for s in Stock.objects.filter(kind=Stock.Kind.STOCK)}
        series_by_sector, all_days = {}, set()
        for name, members in SECTOR_MEMBERS.items():
            objs = [stocks[m] for m in members if m in stocks]
            series = {}
            for s in objs:
                candles = list(
                    Candle.objects.filter(stock=s, period=Candle.Period.DAY).order_by("-time")[:30]
                )[::-1]
                if not candles:
                    continue
                base = float(candles[0].close) or 1.0
                for c in candles:
                    day = timezone.localtime(c.time).date()
                    series.setdefault(day, []).append(float(c.close) / base * 100)
            series_by_sector[name] = (objs, series)
            all_days.update(series.keys())
        days = sorted(all_days)[-30:]
        sectors = []
        for name, (objs, series) in series_by_sector.items():
            heat = round(sum(float(s.change_pct) for s in objs) / len(objs), 2) if objs else 0.0
            values, last = [], 100.0
            for d in days:  # 停牌等缺失日沿用前值,保持日期轴对齐
                if d in series:
                    last = sum(series[d]) / len(series[d])
                values.append(round(last, 2))
            sectors.append({"name": name, "values": values, "change_pct": heat})
        return Response({"labels": [d.strftime("%m-%d") for d in days], "sectors": sectors})


class NewsView(APIView):
    def get(self, request):
        news = NewsItem.objects.all()[:10]
        return Response([
            {"id": n.id, "title": n.title, "summary": n.summary,
             "source": n.source, "ts": timezone.localtime(n.published_at).isoformat()}
            for n in news
        ])
