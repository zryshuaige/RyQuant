"""序列化器:保持旧接口契约(字段与形状),新增能力以增量字段提供。"""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    AIConversation,
    AIMessage,
    BacktestRun,
    Favorite,
    Stock,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email")


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
                  "limit_pct", "lot_size", "is_active", "quote_source", "real_quote_at")

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
