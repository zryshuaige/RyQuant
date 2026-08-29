from django.contrib import admin

from .models import (
    AIConversation,
    AIMessage,
    BacktestRun,
    Candle,
    CashAccount,
    NewsItem,
    Order,
    Position,
    Stock,
    Trade,
)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "price", "prev_close", "limit_pct", "lot_size", "is_active", "updated_at")
    list_editable = ("price", "is_active")
    search_fields = ("symbol", "name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "stock", "side", "order_type", "quantity", "filled_quantity",
                    "avg_fill_price", "status", "created_at")
    list_filter = ("status", "side", "order_type")
    search_fields = ("user__username", "stock__symbol")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "stock", "side", "quantity", "price", "amount", "fee", "created_at")
    search_fields = ("user__username", "stock__symbol")


@admin.register(CashAccount)
class CashAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "frozen_cash", "is_vip", "updated_at")
    search_fields = ("user__username",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("user", "stock", "quantity", "available_quantity", "avg_price", "updated_at")
    search_fields = ("user__username", "stock__symbol")


@admin.register(Candle)
class CandleAdmin(admin.ModelAdmin):
    list_display = ("stock", "period", "time", "open", "high", "low", "close", "volume")
    list_filter = ("period",)
    search_fields = ("stock__symbol",)


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "published_at")
    search_fields = ("title",)


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = ("user", "strategy", "symbol", "days", "initial_capital", "created_at")
    search_fields = ("user__username", "symbol")


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "created_at")
    search_fields = ("user__username",)


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at")
