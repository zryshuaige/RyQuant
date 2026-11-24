from django.contrib import admin

from .models import (
    AIConversation,
    AIMessage,
    BacktestRun,
    Candle,
    Favorite,
    Stock,
)


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "price", "prev_close", "quote_source", "is_active", "updated_at")
    list_editable = ("price", "is_active")
    search_fields = ("symbol", "name")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "stock", "created_at")
    search_fields = ("user__username", "stock__symbol")


@admin.register(Candle)
class CandleAdmin(admin.ModelAdmin):
    list_display = ("stock", "period", "time", "open", "high", "low", "close", "volume", "source")
    list_filter = ("period", "source")
    search_fields = ("stock__symbol",)


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