"""
AI 助手客户端:
- 配置 DEEPSEEK_API_KEY 时调用 DeepSeek(OpenAI 兼容接口);
- 未配置或调用失败时,自动降级为内置离线模拟回答(结合用户真实持仓/行情数据),保证离线可运行。
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一个股票量化研究终端的智能助手,用简洁中文回答投资相关问题,给出客观分析,"
    "并提醒用户行情为模拟/研究用途,不构成投资建议。"
    "平台提供规则化市场脉冲(regime/广度/波动率分位)与分状态策略有效性数据,回答行情/策略类问题时优先引用上下文中的脉冲与推荐数据。"
)

GENERIC_TIPS = [
    "市场有风险,模拟交易虽不涉及真金白银,也是练习纪律的好地方:控制单笔仓位、少动多看。",
    "可以试试「量化回测」页面:用双均线、MACD 等经典策略在历史 K 线上验证想法,再决定手动跟单。",
    "下单前先看涨跌停范围与每手股数:主板 100 股一手,科创板 688 开头 200 股一手。",
    "挂限价单后如果没成交,可以在「持仓 → 当前委托」里撤单改价,或等待行情回到你的价位。",
]


def _favorites_summary(user) -> str:
    from django.utils import timezone

    from ..models import Favorite

    favs = Favorite.objects.filter(user=user).select_related("stock")[:8]
    if not favs:
        return "你还没有自选股。在行情总览页点击「加自选」建立观察池,K 线会标注加入日期。"
    lines = [
        f"{f.stock.name}({f.stock.symbol}){timezone.localtime(f.created_at):%Y-%m-%d} 加入自选,"
        f"现价 {f.stock.price}({f.stock.change_pct:+.2f}%)"
        for f in favs
    ]
    return "你的自选股:\n" + "\n".join(lines)


def _market_summary() -> str:
    from ..models import Stock
    from .market_analysis import market_pulse

    pulse = market_pulse()
    b = pulse["breadth"]
    head = (f"市场脉冲:{pulse['label']}(评分 {pulse['score']:+.0f}),涨 {b['advance']} 家 / 跌 {b['decline']} 家,"
            f"平均涨跌幅 {b['avg_change_pct']:+.2f}%。" + ";".join(pulse["evidence"][:3]))
    stocks = Stock.objects.filter(is_active=True)[:5]
    parts = [f"{s.name} {s.price}({s.change_pct:+.2f}%)" for s in stocks]
    return head + ("\n近期标的一览:" + ";".join(parts) if parts else "")


def mock_reply(user, text: str) -> str:
    """离线模拟回答:按关键词路由,结合真实账户数据生成内容。"""
    t = text.lower()
    if any(k in t for k in ("自选", "关注", "持仓", "账户", "观察池")):
        return _favorites_summary(user)
    if any(k in t for k in ("行情", "大盘", "涨跌", "走势", "指数")):
        return _market_summary()
    if any(k in t for k in ("策略", "回测", "量化", "均线", "macd", "rsi", "布林")):
        return (
            "平台内置 4 个可回测策略:双均线交叉、MACD 金叉死叉、RSI 均值回归、布林带突破。"
            "到「量化回测」页选择策略与参数即可在历史 K 线上验证;回测为次日开盘成交、计入佣金与印花税。"
        )
    if any(k in t for k in ("怎么", "如何", "用", "流程")):
        return (
            "使用流程:行情总览看市场脉冲与指数 → 加自选建立观察池(K 线标注加入日期)→ "
            "量化回测页跑单策略或「策略有效性对比」→ 参考当前大盘状态的适用策略推荐。"
        )
    import random

    return random.choice(GENERIC_TIPS)


def _call_deepseek(text: str, history) -> str:
    from openai import OpenAI  # 延迟导入:未安装 openai 时其他功能不受影响

    client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    from .market_analysis import market_pulse

    p = market_pulse()
    messages.append({"role": "system", "content": (
        f"当前市场脉冲(规则化推断,供参考):{p['label']} 评分 {p['score']};"
        f"涨 {p['breadth']['advance']} 家 / 跌 {p['breadth']['decline']} 家;" + ";".join(p["evidence"][:4])
    )})
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
