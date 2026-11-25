"""自定义策略 CRUD(仅本人):可视化规则搭建器的持久化端点。"""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import CustomStrategy
from ..serializers import CustomStrategySerializer
from ..services.errors import BusinessError
from ..services.quant.custom import MAX_CUSTOM, apply_params_to_rule, validate_rule


def _clean_payload(data, user, exclude_pk=None):
    name = str(data.get("name", "") or "").strip()
    if not (1 <= len(name) <= 20):
        raise BusinessError("策略名需为 1~20 个字符")
    dup = CustomStrategy.objects.filter(user=user, name=name)
    if exclude_pk is not None:
        dup = dup.exclude(pk=exclude_pk)
    if dup.exists():
        raise BusinessError("已有同名策略,换个名字吧")
    rule = validate_rule(data.get("rule"))
    if isinstance(data.get("params"), dict):
        rule = apply_params_to_rule(rule, data["params"])
    fits = data.get("fits") or []
    if not isinstance(fits, list) or not set(fits) <= {"bull", "bear", "range", "high_vol"}:
        raise BusinessError("适合行情取值无效")
    return {"name": name, "rule": rule, "fits": fits}


class CustomStrategyListCreateView(APIView):
    """GET/POST /api/strategies/custom/ — 本人自定义策略列表 / 新建(上限 10)。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = CustomStrategy.objects.filter(user=request.user)
        return Response({"strategies": CustomStrategySerializer(rows, many=True).data})

    def post(self, request):
        if CustomStrategy.objects.filter(user=request.user).count() >= MAX_CUSTOM:
            raise BusinessError(f"自定义策略最多 {MAX_CUSTOM} 条,请先删除不用的")
        payload = _clean_payload(request.data, request.user)
        row = CustomStrategy.objects.create(user=request.user, **payload)
        return Response({"strategy": CustomStrategySerializer(row).data}, status=201)


class CustomStrategyDetailView(APIView):
    """PUT/DELETE /api/strategies/custom/<id>/ — 修改 / 删除(仅本人)。"""

    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        return get_object_or_404(CustomStrategy, pk=pk, user=request.user)

    def put(self, request, pk):
        row = self._get(request, pk)
        payload = _clean_payload(request.data, request.user, exclude_pk=row.pk)
        for key, value in payload.items():
            setattr(row, key, value)
        row.save()
        return Response({"strategy": CustomStrategySerializer(row).data})

    def delete(self, request, pk):
        self._get(request, pk).delete()
        return Response(status=204)