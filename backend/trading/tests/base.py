"""测试公共基类:构造标准标的与用户。"""
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from trading.models import CashAccount, Candle, Position, Stock
from trading.services.trading import place_order

TWO = Decimal("0.01")


def make_stock(symbol="000001", name="平安银行", price="13.88", prev_close="13.20", active=True, kind=None):
    stock = Stock.objects.create(
        symbol=symbol, name=name,
        price=Decimal(price), prev_close=Decimal(prev_close), is_active=active,
        **({"kind": kind} if kind else {}),
    )
    stock.save()  # 触发 lot_size / limit_pct 推导
    stock.refresh_from_db()
    return stock


def seed_daily_candles(stock, count=160, start_price=None, seed="test"):
    """生成 count 根日 K(升序),最后一根 close = stock.price。"""
    import random
    from datetime import timedelta

    from django.utils import timezone

    rnd = random.Random(seed)
    start = start_price or float(stock.price)
    closes = [start] * count
    for i in range(count - 2, -1, -1):
        closes[i] = closes[i + 1] / (1 + rnd.uniform(-0.02, 0.02))
    base_day = timezone.localdate() - timedelta(days=count)
    rows = []
    for i, c in enumerate(closes):
        day = base_day + timedelta(days=i)
        rows.append(Candle(
            stock=stock, period=Candle.Period.DAY,
            time=timezone.make_aware(timezone.datetime(day.year, day.month, day.day)),
            open=round(c * 0.99, 2), high=round(c * 1.02, 2), low=round(c * 0.97, 2),
            close=round(c, 2), volume=100_000,
        ))
    Candle.objects.bulk_create(rows, batch_size=500)


class BaseAPITestCase(APITestCase):
    """自带用户 + 标的的基类。"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("tester", password="password123")
        cls.other = User.objects.create_user("other", password="password123")
        cls.stock = make_stock()
        cls.token = Token.objects.create(user=cls.user)

    def auth(self, user=None):
        user = user or self.user
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def anon(self):
        self.client.credentials()

    @staticmethod
    def buy(user, stock, quantity, price=None, **kwargs):
        return place_order(user, stock, side="BUY", quantity=quantity,
                           order_type="LIMIT", price=price or stock.price, **kwargs)

    @staticmethod
    def sell(user, stock, quantity, price=None, **kwargs):
        return place_order(user, stock, side="SELL", quantity=quantity,
                           order_type="LIMIT", price=price or stock.price, **kwargs)

    @staticmethod
    def give_position(user, stock, quantity=200, price="13.00"):
        """绕过撮合直接构造持仓(测试卖出场景)。"""
        return Position.objects.create(
            user=user, stock=stock, quantity=quantity, available_quantity=quantity,
            avg_price=Decimal(price),
        )
