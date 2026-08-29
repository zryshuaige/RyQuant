"""
AI 助手客户端:
- 配置 DEEPSEEK_API_KEY 时调用 DeepSeek(OpenAI 兼容接口);
- 未配置或调用失败时,自动降级为内置离线模拟回答(结合用户真实持仓/行情数据),保证离线可运行。
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一个模拟股票交易平台的智能助手,用简洁中文回答投资相关问题,给出客观分析,"
    "并提醒用户这是模拟交易,不构成投资建议。"
)

GENERIC_TIPS = [
    "市场有风险,模拟交易虽不涉及真金白银,也是练习纪律的好地方:控制单笔仓位、少动多看。",
    "可以试试「量化回测」页面:用双均线、MACD 等经典策略在历史 K 线上验证想法,再决定手动跟单。",
    "下单前先看涨跌停范围与每手股数:主板 100 股一手,科创板 688 开头 200 股一手。",
    "挂限价单后如果没成交,可以在「持仓 → 当前委托」里撤单改价,或等待行情回到你的价位。",
]


def _portfolio_summary(user) -> str:
    from ..models import CashAccount, Position

    try:
        cash = user.cash_account
    except Exception:
        return "你还没有资金账户,先完成一笔下单吧。"
    positions = Position.objects.filter(user=user, quantity__gt=0).select_related("stock")
    lines = []
    market_value = 0.0
    for p in positions:
        mv = float(p.stock.price) * p.quantity
        pl = (float(p.stock.price) - float(p.avg_price)) * p.quantity
        market_value += mv
        lines.append(f"{p.stock.name}({p.stock.symbol}){p.quantity} 股,浮动盈亏 {pl:+.2f} 元")
    total = float(cash.balance) + float(cash.frozen_cash) + market_value
    head = f"当前可用资金 {cash.balance} 元、冻结 {cash.frozen_cash} 元,持仓市值约 {market_value:.2f} 元,总资产约 {total:.2f} 元。"
    if lines:
        return head + "\n" + "\n".join(lines)
    return head + "目前空仓,可以考虑分批建仓。"


def _market_summary() -> str:
    from ..models import Stock

    stocks = Stock.objects.filter(is_active=True)[:5]
    parts = [f"{s.name} {s.price}({s.change_pct:+.2f}%)" for s in stocks]
    return "近期标的一览:" + ";".join(parts) if parts else "暂无行情数据。"


def mock_reply(user, text: str) -> str:
    """离线模拟回答:按关键词路由,结合真实账户数据生成内容。"""
    t = text.lower()
    if any(k in t for k in ("持仓", "仓位", "账户", "资产", "余额", "盈亏")):
        return _portfolio_summary(user)
    if any(k in t for k in ("行情", "大盘", "涨跌", "走势", "指数")):
        return _market_summary()
    if any(k in t for k in ("策略", "回测", "量化", "均线", "macd", "rsi", "布林")):
        return (
            "平台内置 4 个可回测策略:双均线交叉、MACD 金叉死叉、RSI 均值回归、布林带突破。"
            "到「量化回测」页选择策略与参数即可在历史 K 线上验证;回测为次日开盘成交、计入佣金与印花税。"
        )
    if any(k in t for k in ("怎么", "如何", "下单", "买入", "卖出", "撤单")):
        return (
            "下单流程:在首页或持仓页点击「下单」,选择限价/市价 → 输入数量(整手)→ 确认。"
            "买单提交即冻结资金,成交后扣款;卖单冻结持仓。未成交的委托可随时撤单,资金秒退。"
        )
    import random

    return random.choice(GENERIC_TIPS)


def _call_deepseek(text: str, history) -> str:
    from openai import OpenAI  # 延迟导入:未安装 openai 时其他功能不受影响

    client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:
        role = "assistant" if msg.get("sender") == "bot" else "user"
        messages.append({"role": role, "content": msg.get("content", "")})
    messages.append({"role": "user", "content": text})
    resp = client.chat.completions.create(
        model=settings.DEEPSEEK_MODEL, messages=messages, temperature=0.7, max_tokens=800, timeout=30,
    )
    return resp.choices[0].message.content


def get_ai_reply(user, text: str, history=None) -> str:
    if settings.DEEPSEEK_API_KEY:
        try:
            return _call_deepseek(text, history or [])
        except Exception as exc:  # 降级而非报错,保证对话不中断
            logger.warning("DeepSeek 调用失败,降级为离线回答: %s", exc)
            return "(DeepSeek 暂时不可用,已切换离线模式)\n\n" + mock_reply(user, text)
    return mock_reply(user, text)
