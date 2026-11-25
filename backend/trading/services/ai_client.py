"""
AI 研究助手客户端:
- 配置 DEEPSEEK_API_KEY 时调用 DeepSeek(OpenAI 兼容接口);
- 未配置或调用失败时,自动降级为内置离线回答(结合用户自选与大盘状态),保证离线可运行。
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一个股票量化研究终端的研究助手,用简洁中文回答投资研究问题,给出客观分析,"
    "并提醒用户内容仅供研究学习,不构成投资建议。"
    "平台提供规则化大盘状态(趋势/广度/波动率分位)与分行情策略有效性数据,"
    "回答行情或策略类问题时优先引用上下文中的大盘状态与策略建议。"
)

GENERIC_TIPS = [
    "研究有风险:任何策略都应先看样本外表现与最大回撤,再决定是否参考。",
    "可以试试「量化回测」页面:用双均线、MACD 等经典策略在历史 K 线上验证想法。",
    "自选页会记录加入以来的收益,并与同期上证指数对比,方便判断选股是否跑赢大盘。",
    "策略建议只是在当前行情下的历史统计,不代表未来收益。",
]


def _favorites_summary(user) -> str:
    from .watchlist import favorites_summary

    data = favorites_summary(user)
    if not data["count"]:
        return "你还没有自选标的。在行情总览或自选页输入代码/名称即可加入,K 线会标注加入日期。"
    lines = [
        f"{item['stock'].name}({item['stock'].symbol}) {item['joined_at']} 加入,"
        f"加入以来 {item['return_pct']:+.2f}%,同期上证 {item['benchmark_return_pct']:+.2f}%,"
        f"超额 {item['excess_pct']:+.2f}%"
        for item in data["items"][:8]
    ]
    return (f"你的自选共 {data['count']} 只,平均加入以来 {data['avg_return_pct']:+.2f}%,"
            f"跑赢上证 {data['beat_count']}/{data['count']} 只。\n" + "\n".join(lines))


def _market_summary() -> str:
    from ..models import Stock
    from .market_analysis import market_pulse

    pulse = market_pulse()
    b = pulse["breadth"]
    head = (f"大盘状态:{pulse['label']}(评分 {pulse['score']:+.0f}),涨 {b['advance']} 家 / "
            f"跌 {b['decline']} 家,平均涨跌幅 {b['avg_change_pct']:+.2f}%。" + ";".join(pulse["evidence"][:3]))
    stocks = Stock.objects.filter(kind=Stock.Kind.STOCK, is_active=True)[:5]
    parts = [f"{s.name} {s.price}({s.change_pct:+.2f}%)" for s in stocks]
    return head + ("\n近期标的一览:" + ";".join(parts) if parts else "")


def mock_reply(user, text: str) -> str:
    """离线回答:按关键词路由,结合真实自选与大盘数据生成内容。"""
    t = text.lower()
    if any(k in t for k in ("自选", "关注", "观察池", "跑赢")):
        return _favorites_summary(user)
    if any(k in t for k in ("行情", "大盘", "涨跌", "走势", "指数")):
        return _market_summary()
    if any(k in t for k in ("策略", "回测", "量化", "均线", "macd", "rsi", "布林")):
        return (
            "平台内置 4 个可回测策略:双均线交叉、MACD 金叉死叉、RSI 均值回归、布林带突破。"
            "到「量化回测」页选择策略与参数即可在历史 K 线上验证;回测为次日开盘成交、计入佣金与印花税。"
            "「策略对比」会按当前行情状态统计各策略的历史表现,并给出样本外结果。"
        )
    if any(k in t for k in ("怎么", "如何", "用", "流程")):
        return (
            "使用流程:行情总览看大盘状态与策略建议 → 加自选建立观察池(K 线标注加入日期、自选页跟踪超额收益)→ "
            "量化回测页跑单策略或「策略有效性对比」→ 回到大盘状态查看当前行情更适合的策略。"
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
        f"当前大盘状态(规则化推断,供参考):{p['label']} 评分 {p['score']};"
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