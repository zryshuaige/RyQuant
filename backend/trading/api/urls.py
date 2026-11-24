from django.urls import path

from . import account, ai, auth, backtest, favorites, market, trading

urlpatterns = [
    # 认证
    path("register/", auth.RegisterView.as_view(), name="register"),
    path("login/", auth.LoginView.as_view(), name="login"),
    # 行情
    path("stocks/", market.StockListView.as_view(), name="stocks"),
    path("indices/", market.IndicesView.as_view(), name="indices"),
    path("kline/", market.KlineView.as_view(), name="kline"),
    path("sectors/", market.SectorsView.as_view(), name="sectors"),
    path("market/pulse/", market.MarketPulseView.as_view(), name="market-pulse"),
    path("news/", market.NewsView.as_view(), name="news"),
    # 自选
    path("favorites/", favorites.FavoriteListCreateView.as_view(), name="favorites"),
    path("favorites/<int:pk>/", favorites.FavoriteDeleteView.as_view(), name="favorite-delete"),
    # 交易
    path("order/", trading.PlaceOrderView.as_view(), name="order"),  # 旧路径别名
    path("orders/", trading.OrdersView.as_view(), name="orders"),
    path("orders/<int:pk>/cancel/", trading.OrderCancelView.as_view(), name="order-cancel"),
    path("trades/", trading.TradeListView.as_view(), name="trades"),
    path("positions/", account.PositionsView.as_view(), name="positions"),
    # AI 助手(VIP)
    path("ai/activate/", ai.ActivateVipView.as_view(), name="ai-activate"),
    path("ai/query/", ai.AIQueryView.as_view(), name="ai-query"),
    # 量化回测(VIP)
    path("strategies/", backtest.StrategyListView.as_view(), name="strategies"),
    path("backtest/", backtest.BacktestRunView.as_view(), name="backtest"),
    path("backtest/compare/", backtest.BacktestCompareView.as_view(), name="backtest-compare"),
    path("backtest/history/", backtest.BacktestHistoryView.as_view(), name="backtest-history"),
    path("backtest/history/<int:pk>/", backtest.BacktestDetailView.as_view(), name="backtest-detail"),
]
