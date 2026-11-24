"""
真实行情数据抓取:腾讯日 K(前复权)/ 网易日 K 备选源 / 板块成分映射。
seed_demo 与 market_sim 共用;所有抓取函数失败返回 None,调用方回退模拟数据。
"""
from decimal import Decimal, InvalidOperation

TWO = Decimal("0.01")
HISTORY_BARS = 250

# 板块成分(演示股票池内分组);板块行情由成员真实报价/日 K 计算,不再虚构
SECTOR_MEMBERS = {
    "金融": ["601318", "000001"],
    "科技": ["688981", "600410"],
    "消费": ["600519", "000858"],
    "新能源": ["300750", "002594"],
}


def _to_decimal(value, default=None):
    try:
        return Decimal(str(value)).quantize(TWO)
    except (InvalidOperation, TypeError, ValueError):
        return default


def tencent_code(symbol: str) -> str:
    """规范腾讯行情代码:已带 sh/sz 前缀(指数)直接使用;裸代码按规则补前缀。"""
    if symbol[:2] in ("sh", "sz", "bj"):
        return symbol
    return ("sh" if symbol.startswith(("6", "9", "5")) else "sz") + symbol


def fetch_real_daily_tencent(symbol: str, count: int = HISTORY_BARS):
    """
    腾讯行情日 K(前复权):https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
    返回升序 [(date, open, close, high, low, volume)],失败返回 None。
    """
    try:
        import requests
    except ImportError:
        return None
    code = tencent_code(symbol)
    try:
        resp = requests.get(
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            params={"param": f"{code},day,,,{count},qfq"},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (RyQuant demo seed)"},
        )
        payload = resp.json()["data"][code]
        rows = payload.get("qfqday") or payload.get("day") or []
        result = []
        for r in rows:
            o, c, h, l = _to_decimal(r[1]), _to_decimal(r[2]), _to_decimal(r[3]), _to_decimal(r[4])
            vol = int(float(r[5])) * 100 if len(r) > 5 and r[5] else 0  # 手 → 股,与实时 tick 口径一致
            if None in (o, c, h, l) or c <= 0:
                continue
            result.append((str(r[0]), o, c, h, l, vol))
        return result[-count:] if result else None
    except Exception:
        return None


def fetch_real_daily_netease(symbol: str, count: int = HISTORY_BARS):
    """网易历史数据 CSV(备选源)。返回格式同上。"""
    try:
        import requests
    except ImportError:
        return None
    code = ("0" if symbol.startswith(("6", "9", "5")) else "1") + symbol
    try:
        resp = requests.get(
            "http://quotes.money.163.com/service/chddata.html",
            params={"code": code, "fields": "TCLOSE;HIGH;LOW;TOPEN;VOTURNOVER"},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (RyQuant demo seed)"},
        )
        resp.encoding = "gbk"
        lines = resp.text.strip().splitlines()[1:]  # 跳过表头,按日期降序
        result = []
        for line in reversed(lines):  # 转升序
            parts = line.split(",")
            if len(parts) < 8:
                continue
            date, close, high, low, open_, vol = parts[0], parts[3], parts[4], parts[5], parts[6], parts[7]
            c, h, l, o = _to_decimal(close), _to_decimal(high), _to_decimal(low), _to_decimal(open_)
            if None in (c, h, l, o) or c <= 0:
                continue
            result.append((date.replace("-", ""), o, c, h, l, int(float(vol or 0))))
        return result[-count:] if result else None
    except Exception:
        return None