"""账户视图:持仓与资金汇总。响应信封与旧接口一致,新增 total_asset 与 available_quantity 增量字段。"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Position
from ..serializers import CashAccountSerializer
from ..services.trading import get_cash_account


class PositionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        cash = get_cash_account(user)

        details = []
        total_market_value = 0.0
        total_unrealized_pl = 0.0
        positions = Position.objects.filter(user=user, quantity__gt=0).select_related("stock")
        for pos in positions:
            market_price = float(pos.stock.price)
            avg_price = float(pos.avg_price)
            market_value = round(market_price * pos.quantity, 2)
            unrealized_pl = round((market_price - avg_price) * pos.quantity, 2)
            total_market_value += market_value
            total_unrealized_pl += unrealized_pl
            details.append({
                "position_id": pos.pk,
                "stock_id": pos.stock_id,
                "symbol": pos.stock.symbol,
                "name": pos.stock.name,
                "quantity": pos.quantity,
                "available_quantity": pos.available_quantity,  # 增量字段
                "avg_price": round(avg_price, 2),
                "market_price": market_price,
                "market_value": market_value,
                "unrealized_pl": unrealized_pl,
            })

        total_asset = float(cash.balance) + float(cash.frozen_cash) + total_market_value
        return Response({
            "cash": CashAccountSerializer(cash).data,
            "total_market_value": round(total_market_value, 2),
            "total_unrealized_pl": round(total_unrealized_pl, 2),
            "total_asset": round(total_asset, 2),  # 增量字段
            "details": details,
        })
