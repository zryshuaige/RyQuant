"""领域模型:标的 / 自选 / 行情 / AI / 回测 / 自定义策略"""
from .ai import AIConversation, AIMessage
from .backtest import BacktestRun
from .custom_strategy import CustomStrategy
from .favorite import Favorite
from .market import Candle
from .stock import Stock

__all__ = [
    "Stock", "Favorite", "Candle", "AIConversation", "AIMessage", "BacktestRun", "CustomStrategy",
]