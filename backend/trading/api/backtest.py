"""量化回测:策略列表 / 运行回测 / 历史记录。"""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import BacktestRun, Candle, CustomStrategy, Stock
from ..services.errors import BusinessError
from ..serializers import BacktestRunDetailSerializer, BacktestRunListSerializer
from ..services.quant import strategies as strategy_registry
from ..services.quant.custom import build_spec, validate_rule
from ..services.quant.engine import run_backtest
from ..services.quant.preview import build_preview
from .throttling import BacktestThrottle, PreviewThrottle

MIN_DAYS, MAX_DAYS = 30, 250


def _public_spec(s):
    """策略 spec → 前端契约(不含 signals 可调用对象)。"""
    out = {
        "id": s["id"], "name": s["name"], "description": s["description"],
        "essence": s["essence"], "buy_rule": s["buy_rule"], "sell_rule": s["sell_rule"],
        "fits": s["fits"], "risk": s["risk"], "presets": s["presets"],
        "params": s["params"], "custom": bool(s.get("custom")),
    }
    if s.get("custom"):
        out["rule"] = s["rule"]
    return out


def _resolve_spec(request, strategy_id):
    """内置注册表 ∪ 本人自定义策略;未知 id → None。"""
    spec = strategy_registry.get_strategy(strategy_id)
    if spec is not None:
        return spec
    if strategy_id.startswith("custom_") and strategy_id[7:].isdigit():
        row = CustomStrategy.objects.filter(pk=strategy_id[7:], user=request.user).first()
        if row is not None:
            return build_spec(row.rule, row.name, fits=row.fits, pk=row.pk)
    return None


class StrategyListView(APIView):
    """GET /api/strategies/ — 内置策略 + 本人自定义 + 白话解释 + 买卖规则 + 参数 schema 与预设。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        specs = list(strategy_registry.STRATEGIES)
        specs += [build_spec(c.rule, c.name, fits=c.fits, pk=c.pk)
                  for c in CustomStrategy.objects.filter(user=request.user)]
        return Response({"strategies": [_public_spec(s) for s in specs]})


class BacktestRunView(APIView):
    """
    POST /api/backtest/ — body: {strategy, symbol|stock_id, params?, days?, initial_capital?}
    返回完整回测结果(指标 / 资金曲线 / K 线 / 买卖点 / 逐笔),并持久化供历史回看。
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [BacktestThrottle]

    def post(self, request):
        data = request.data
        spec = _resolve_spec(request, str(data.get("strategy", "")))
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
        extra_specs = []
        if ids not in (None, ""):
            if not isinstance(ids, list) or not all(_resolve_spec(request, str(i)) for i in ids):
                raise BusinessError("strategies 需为已知策略 id 列表")
            ids = [str(i) for i in ids]
            builtin_ids = [i for i in ids if i in strategy_registry.REGISTRY]
            extra_specs = [_resolve_spec(request, i) for i in ids if i not in strategy_registry.REGISTRY]
            ids = builtin_ids

        index_payload = None
        anchor = Stock.objects.filter(kind=Stock.Kind.INDEX).order_by("pk").first()
        if anchor is not None and anchor.pk != stock.pk:
            index_candles = list(
                Candle.objects.filter(stock=anchor, period=Candle.Period.DAY).order_by("-time")[: days + 1]
            )[::-1]
            if len(index_candles) >= 25:
                index_payload = [_candle_payload(c) for c in index_candles]

        lot = stock.lot_size if stock.kind == Stock.Kind.STOCK else 1
        result = compare_strategies(payload, index_payload, strategy_ids=ids, capital=capital,
                                    lot=lot, extra_specs=extra_specs or None)
        result["symbol"] = stock.symbol
        result["name"] = stock.name
        return Response(result)


class BacktestPreviewView(APIView):
    """
    POST /api/backtest/preview/ — body: {strategy|rule, symbol|stock_id, days?, params?}
    策略实时预览:K 线 + 指标叠加线/副图 + 信号标记 + 白话买卖句。不跑引擎、不持久化。
    rule 内联时供搭建器「边搭边看」,无需先保存。
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [PreviewThrottle]

    def post(self, request):
        data = request.data
        if data.get("rule"):
            spec = build_spec(validate_rule(data["rule"]), str(data.get("name") or "我的策略"))
        else:
            spec = _resolve_spec(request, str(data.get("strategy", "")))
            if spec is None:
                raise BusinessError("未知策略,请从 /api/strategies/ 中选择")

        stock = BacktestRunView._resolve_stock(data)
        days = BacktestRunView._parse_int(data.get("days", 120), "days", MIN_DAYS, MAX_DAYS)
        candles = list(
            Candle.objects.filter(stock=stock, period=Candle.Period.DAY).order_by("-time")[: days + 1]
        )[::-1]
        if len(candles) < 10:
            raise BusinessError(f"历史数据不足({len(candles)} 根),无法预览")
        payload = [_candle_payload(c) for c in candles]
        closes = [c["close"] for c in payload]

        from ..services.quant.strategies import clean_params
        params = clean_params(spec, data.get("params") or {})
        preview = build_preview(spec, closes, params)
        return Response({
            "candles": payload,
            "preview": preview,
            "params": params,
            "params_schema": spec["params"],
            "name": spec["name"],
            "buy_text": spec["buy_rule"].format(**params),
            "sell_text": spec["sell_rule"].format(**params),
        })


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
