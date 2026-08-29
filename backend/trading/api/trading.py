"""交易接口:下单(含旧路径别名)/ 委托列表 / 撤单 / 成交记录。"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Order, Stock, Trade
from ..serializers import CashAccountSerializer, OrderSerializer, TradeSerializer
from ..services import trading as trading_service
from ..services.errors import BusinessError
from .throttling import OrderThrottle


def _resolve_stock(request_data):
    """兼容 stock_id 与 symbol 两种定位方式(旧契约)。"""
    stock_id = request_data.get("stock_id")
    symbol = str(request_data.get("symbol", "") or "").strip()
    if stock_id not in (None, ""):
        try:
            stock_id = int(stock_id)
        except (TypeError, ValueError):
            raise BusinessError("stock_id 必须为整数")
        stock = Stock.objects.filter(pk=stock_id).first()
    elif symbol:
        stock = Stock.objects.filter(symbol=symbol).first()
    else:
        raise BusinessError("需要提供 stock_id 或 symbol")
    if stock is None:
        raise BusinessError(f"未找到标的: {symbol or stock_id}")
    return stock


def _parse_quantity(raw):
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        raise BusinessError("下单数量必须为正整数")


def _place(request):
    """下单公共逻辑:解析参数 → 领域服务 → {order, cash} 响应(旧契约)。"""
    data = request.data
    stock = _resolve_stock(data)

    side = str(data.get("side", "")).strip().upper()
    if side not in Order.Side.values:
        raise BusinessError("side 必须为 BUY 或 SELL")
    order_type = str(data.get("order_type", "")).strip().upper() or Order.OrderType.LIMIT
    if order_type not in Order.OrderType.values:
        raise BusinessError("order_type 必须为 LIMIT 或 MARKET")
    quantity = _parse_quantity(data.get("quantity"))
    price = trading_service.parse_price(data.get("price")) if order_type == Order.OrderType.LIMIT else None
    if order_type == Order.OrderType.LIMIT and price is None:
        raise BusinessError("限价单必须提供委托价格")

    order = trading_service.place_order(
        request.user, stock, side=side, quantity=quantity,
        order_type=order_type, price=price,
    )
    cash = trading_service.get_cash_account(request.user)
    return Response({"order": OrderSerializer(order).data, "cash": CashAccountSerializer(cash).data})


class OrdersView(APIView):
    """GET /api/orders/(委托列表,?status=&active=1)+ POST /api/orders/(下单)。"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [OrderThrottle]

    def get(self, request):
        qs = Order.objects.filter(user=request.user).select_related("stock")
        status_filter = str(request.query_params.get("status", "")).strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        elif request.query_params.get("active") in ("1", "true", "True"):
            qs = qs.filter(status__in=Order.ACTIVE_STATUSES)
        qs = qs[:200]
        return Response({"orders": OrderSerializer(qs, many=True).data})

    def post(self, request):
        return _place(request)


class PlaceOrderView(APIView):
    """POST /api/order/ — 旧路径别名(仅下单)。body: {stock_id|symbol, side, quantity, price?}"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [OrderThrottle]

    def post(self, request):
        return _place(request)


class OrderCancelView(APIView):
    """POST /api/orders/<id>/cancel/ — 撤单并解冻,返回更新后的订单与资金。"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [OrderThrottle]

    def post(self, request, pk):
        order = trading_service.cancel_order(request.user, pk)
        cash = trading_service.get_cash_account(request.user)
        return Response({"order": OrderSerializer(order).data, "cash": CashAccountSerializer(cash).data})


class TradeListView(APIView):
    """GET /api/trades/ — 成交记录(逐笔)。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        trades = Trade.objects.filter(user=request.user).select_related("stock")[:200]
        return Response({"trades": TradeSerializer(trades, many=True).data})
