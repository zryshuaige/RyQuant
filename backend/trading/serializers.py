"""序列化器:保持旧接口契约(字段与形状),新增能力以增量字段提供。"""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    AIConversation,
    AIMessage,
    BacktestRun,
    CashAccount,
    Favorite,
    Order,
    Stock,
    Trade,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    is_vip = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "is_vip")

    def get_is_vip(self, obj) -> bool:
        account = getattr(obj, "cash_account", None)
        return bool(account and account.is_vip)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )


class StockSerializer(serializers.ModelSerializer):
    change = serializers.SerializerMethodField()
    change_pct = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = ("id", "symbol", "name", "price", "prev_close", "change", "change_pct",
                  "limit_pct", "lot_size", "is_active")

    def get_change(self, obj):
        return round(float(obj.change), 2)

    def get_change_pct(self, obj):
        return round(float(obj.change_pct), 2)


class FavoriteSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    stock_id = serializers.PrimaryKeyRelatedField(queryset=Stock.objects.all(), write_only=True, source="stock")

    class Meta:
        model = Favorite
        fields = ("id", "stock", "stock_id", "created_at")
        read_only_fields = ("created_at",)


class OrderSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    stock_id = serializers.PrimaryKeyRelatedField(queryset=Stock.objects.all(), write_only=True, source="stock")

    class Meta:
        model = Order
        fields = ("id", "stock", "stock_id", "side", "order_type", "quantity", "price",
                  "filled_quantity", "avg_fill_price", "status", "reject_reason",
                  "frozen_amount", "frozen_quantity",
                  "created_at", "updated_at")
        read_only_fields = ("status", "filled_quantity", "avg_fill_price", "reject_reason")


class TradeSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    order = serializers.IntegerField(source="order_id", read_only=True)

    class Meta:
        model = Trade
        fields = ("id", "order", "stock", "side", "quantity", "price", "amount", "fee", "created_at")


class CashAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashAccount
        fields = ("balance", "frozen_cash", "is_vip")


class AIMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIMessage
        fields = ("id", "sender", "content", "created_at")


class AIConversationSerializer(serializers.ModelSerializer):
    messages = AIMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIConversation
        fields = ("id", "title", "created_at", "messages")


class BacktestRunListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestRun
        fields = ("id", "strategy", "symbol", "days", "initial_capital", "params", "metrics", "created_at")


class BacktestRunDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BacktestRun
        fields = ("id", "strategy", "symbol", "days", "initial_capital", "params",
                  "metrics", "equity_curve", "candles", "markers", "trades", "created_at")
