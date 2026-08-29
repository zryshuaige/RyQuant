"""自选股 CRUD:列表 / 加入 / 删除(仅本人)。"""
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListCreateAPIView, DestroyAPIView
from rest_framework.permissions import IsAuthenticated

from ..models import Favorite
from ..serializers import FavoriteSerializer


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
