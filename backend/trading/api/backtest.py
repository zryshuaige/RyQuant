"""VIP 量化回测:策略列表 / 运行回测 / 历史记录。"""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import BacktestRun, Candle, Stock
from ..services.errors import BusinessError
from ..serializers import BacktestRunDetailSerializer, BacktestRunListSerializer
from ..services.quant import strategies as strategy_registry
from ..services.quant.engine import run_backtest
from .throttling import BacktestThrottle

MIN_DAYS, MAX_DAYS = 30, 250


class StrategyListView(APIView):
    """GET /api/strategies/ — 内置策略 + 参数 schema(登录即可浏览,运行需 VIP)。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"strategies": [
            {"id": s["id"], "name": s["name"], "description": s["description"], "params": s["params"]}
            for s in strategy_registry.STRATEGIES
        ]})


class BacktestRunView(APIView):
    """
    POST /api/backtest/ — body: {strategy, symbol|stock_id, params?, days?, initial_capital?}
    返回完整回测结果(指标 / 资金曲线 / K 线 / 买卖点 / 逐笔),并持久化供历史回看。
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [BacktestThrottle]

    def post(self, request):
        data = request.data
        spec = strategy_registry.get_strategy(str(data.get("strategy", "")))
        if spec is None:
            raise BusinessError("未知策略,请从 /api/strategies/ 中选择")

        stock = self._resolve_stock(data)
        days = self._parse_int(data.get("days", 120), "days", MIN_DAYS, MAX_DAYS)
        initial_capital = self._parse_capital(data.get("initial_capital", 100000))

        candles = list(
            Candle.objects.filter(stock=stock, period=Candle.Period.DAY).order_by("-time")[: days + 1]
        )[::-1]
        if len(candles) < MIN_DAYS:
            raise BusinessError(f"历史数据不足({len(candles)} 根),无法回测")

        params = strategy_registry.clean_params(spec, data.get("params") or {})
        closes = [float(c.close) for c in candles]
        signals = spec["signals"](closes, params)

        payload = [{"time": timezone_local(c.time).strftime("%Y-%m-%d"),
                    "open": float(c.open), "high": float(c.high),
                    "low": float(c.low), "close": float(c.close)}
                   for c in candles]
        lot = stock.lot_size if stock.kind == Stock.Kind.STOCK else 1
        result = run_backtest(payload, signals, initial_capital, lot=lot)

        run = BacktestRun.objects.create(
            user=request.user,
            strategy=spec["id"],
            stock=stock,
            symbol=stock.symbol,
            params=params,
            days=len(candles),
            initial_capital=initial_capital,
            metrics=result["metrics"],
            equity_curve=result["equity_curve"],
            candles=payload,
            markers=result["markers"],
            trades=result["trades"],
        )
        return Response({"run": BacktestRunDetailSerializer(run).data})

    @staticmethod
    def _resolve_stock(data):
        stock = None
        if data.get("stock_id") not in (None, ""):
            stock = Stock.objects.filter(pk=data.get("stock_id")).first()
        if stock is None and str(data.get("symbol", "") or "").strip():
            stock = Stock.objects.filter(symbol=str(data["symbol"]).strip()).first()
        if stock is None:
            raise BusinessError("需要提供有效的 symbol 或 stock_id")
        return stock

    @staticmethod
    def _parse_int(raw, name, minimum, maximum):
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            raise BusinessError(f"{name} 必须为整数")
        return min(max(value, minimum), maximum)

    @staticmethod
    def _parse_capital(raw):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise BusinessError("initial_capital 必须为数字")
        if value <= 0:
            raise BusinessError("initial_capital 必须大于 0")
        return round(value, 2)


class BacktestCompareView(APIView):
    """
    POST /api/backtest/compare/ — body: {symbol|stock_id, days?, initial_capital?, strategies?}
    跨策略有效性对比:同窗口默认参数 + 滚动样本外 + 分 regime 评估 + 排名;结果不持久化。
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [BacktestThrottle]

    def post(self, request):
        from ..services.quant.compare import compare_strategies

        data = request.data
        stock = BacktestRunView._resolve_stock(data)
        days = BacktestRunView._parse_int(data.get("days", 120), "days", MIN_DAYS, MAX_DAYS)
        capital = BacktestRunView._parse_capital(data.get("initial_capital", 100000))

        candles = list(
            Candle.objects.filter(stock=stock, period=Candle.Period.DAY).order_by("-time")[: days + 1]
        )[::-1]
        if len(candles) < MIN_DAYS:
            raise BusinessError(f"历史数据不足({len(candles)} 根),无法对比")
        payload = [_candle_payload(c) for c in candles]

        ids = data.get("strategies")
        if ids not in (None, ""):
            if not isinstance(ids, list) or not all(strategy_registry.get_strategy(str(i)) for i in ids):
                raise BusinessError("strategies 需为已知策略 id 列表")
            ids = [str(i) for i in ids]

        index_payload = None
        anchor = Stock.objects.filter(kind=Stock.Kind.INDEX).order_by("pk").first()
        if anchor is not None and anchor.pk != stock.pk:
            index_candles = list(
                Candle.objects.filter(stock=anchor, period=Candle.Period.DAY).order_by("-time")[: days + 1]
            )[::-1]
            if len(index_candles) >= 25:
                index_payload = [_candle_payload(c) for c in index_candles]

        lot = stock.lot_size if stock.kind == Stock.Kind.STOCK else 1
        result = compare_strategies(payload, index_payload, strategy_ids=ids, capital=capital, lot=lot)
        result["symbol"] = stock.symbol
        result["name"] = stock.name
        return Response(result)


def _candle_payload(c):
    return {"time": timezone_local(c.time).strftime("%Y-%m-%d"),
            "open": float(c.open), "high": float(c.high),
            "low": float(c.low), "close": float(c.close)}


def timezone_local(dt):
    from django.utils import timezone

    return timezone.localtime(dt)


class BacktestHistoryView(APIView):
    """GET /api/backtest/history/ — 本人回测历史(列表轻量化,不含曲线数据)。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        runs = BacktestRun.objects.filter(user=request.user)[:50]
        return Response({"runs": BacktestRunListSerializer(runs, many=True).data})


class BacktestDetailView(APIView):
    """GET /api/backtest/history/<id>/ — 单次回测完整结果。"""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        run = get_object_or_404(BacktestRun, pk=pk, user=request.user)
        return Response({"run": BacktestRunDetailSerializer(run).data})
