"""自选股 CRUD + 加入以来表现汇总(仅本人)。"""
from django.shortcuts import get_object_or_404
from rest_framework.generics import DestroyAPIView, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Favorite
from ..serializers import FavoriteSerializer, StockSerializer
from ..services.watchlist import favorites_summary


class FavoriteListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteSerializer

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related("stock")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FavoriteDeleteView(DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return get_object_or_404(Favorite, pk=self.kwargs["pk"], user=self.request.user)


class FavoritesSummaryView(APIView):
    """GET /api/favorites/summary/ — 加入以来收益 / 同期上证 / 超额收益。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = favorites_summary(request.user)
        data["items"] = [
            {**{k: v for k, v in item.items() if k != "stock"},
             "stock": StockSerializer(item["stock"]).data}
            for item in data["items"]
        ]
        return Response(data)