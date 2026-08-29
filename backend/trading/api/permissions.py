from rest_framework.permissions import BasePermission


class IsVip(BasePermission):
    """服务端 VIP 校验(AI 助手 / 量化回测)。前端隐藏入口只是体验,这里才是闸门。"""

    message = "该功能需要 VIP,请先开通"

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        account = getattr(user, "cash_account", None)
        return bool(account and account.is_vip)
