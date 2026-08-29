"""全链路冒烟:登录→下单→撮合→撤单→资金/持仓→委托/成交记录→回测→AI"""
import requests
import time
import json

BASE = "http://127.0.0.1:8080/api"
s = requests.Session()
ok_count = 0


def check(name, cond, extra=""):
    global ok_count
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {extra}")
    if cond:
        ok_count += 1
    return cond


# 1. 登录演示账户
r = s.post(f"{BASE}/login/", json={"username": "demo", "password": "demo123456"})
check("登录", r.status_code == 200 and "token" in r.json(), f"user={r.json().get('user', {}).get('username')}")
token = r.json()["token"]
s.headers["Authorization"] = f"Token {token}"

# 2. 行情
r = s.get(f"{BASE}/stocks/")
stocks = {x["symbol"]: x for x in r.json()}
check("股票列表", r.status_code == 200 and len(stocks) >= 8)
r = s.get(f"{BASE}/indices/")
idx = r.json()["indices"]
check("模拟指数", len(idx) == 3, f"{[(i['name'], i['change_pct']) for i in idx]}")
r = s.get(f"{BASE}/kline/", params={"symbol": "600519", "limit": 30})
check("K线(真实历史)", r.status_code == 200 and len(r.json()["klines"]) == 30)
r = s.get(f"{BASE}/news/")
check("资讯", r.status_code == 200 and len(r.json()) >= 3)

# 3. 市价买入 → 立即成交
r = s.post(f"{BASE}/orders/", json={"symbol": "601318", "side": "BUY", "quantity": 100, "order_type": "MARKET"})
d = r.json()
check("市价买入立即成交", r.status_code == 200 and d["order"]["status"] == "FILLED",
      f"均价 {d['order']['avg_fill_price']} 余额 {d['cash']['balance']}")
cash_before = d["cash"]["balance"]

# 4. 低于市价的限价买单 → PENDING 且冻结资金
r = s.post(f"{BASE}/orders/", json={"symbol": "601318", "side": "BUY", "quantity": 100,
                                    "order_type": "LIMIT", "price": round(stocks["601318"]["price"] * 0.97, 2)})
pending = r.json()
check("限价买单挂单", r.status_code == 200 and pending["order"]["status"] == "PENDING",
      f"冻结 {pending['order']['frozen_amount']}")
frozen = pending["cash"]["frozen_cash"]
check("冻结资金入账", frozen > 0, f"frozen_cash={frozen}")

# 5. 撤单 → 解冻
r = s.post(f"{BASE}/orders/{pending['order']['id']}/cancel/")
d = r.json()
check("撤单", r.status_code == 200 and d["order"]["status"] == "CANCELLED")
check("撤单解冻", d["cash"]["frozen_cash"] < frozen and d["cash"]["balance"] > cash_before - 1,
      f"frozen {d['cash']['frozen_cash']} balance {d['cash']['balance']}")

# 6. 高于市价的限价单 → 立即按市价成交(部分成交可能)
r = s.post(f"{BASE}/orders/", json={"symbol": "000858", "side": "BUY", "quantity": 100,
                                    "order_type": "LIMIT", "price": round(stocks["000858"]["price"] * 1.03, 2)})
d = r.json()
check("限价单价格穿越成交", r.status_code == 200 and d["order"]["status"] in ("FILLED", "PARTIAL_FILLED"),
      f"status={d['order']['status']} filled={d['order']['filled_quantity']}")

# 7. 校验:非整手被拒
r = s.post(f"{BASE}/orders/", json={"symbol": "601318", "side": "BUY", "quantity": 50,
                                    "order_type": "LIMIT", "price": 42})
check("整手校验", r.status_code == 400, r.json().get("detail") if isinstance(r.json(), dict) else str(r.json()))
# 校验:科创手数
r = s.post(f"{BASE}/orders/", json={"symbol": "688981", "side": "BUY", "quantity": 100,
                                    "order_type": "LIMIT", "price": 99})
check("科创板 200 股/手", r.status_code == 400, str(r.json())[:60])

# 8. 持仓 / 委托 / 成交
r = s.get(f"{BASE}/positions/")
pos = r.json()
check("持仓汇总", r.status_code == 200 and "total_asset" in pos and len(pos["details"]) >= 3,
      f"总资产 {pos.get('total_asset')} 持仓 {len(pos.get('details', []))} 只")
r = s.get(f"{BASE}/orders/", params={"active": 1})
check("在途委托列表", r.status_code == 200)
r = s.get(f"{BASE}/trades/")
check("成交记录", r.status_code == 200 and len(r.json()["trades"]) >= 5, f"{len(r.json()['trades'])} 笔")

# 9. 等待行情 tick 驱动挂单撮合(挂一张接近市价的单,等待部分成交概率)
r = s.post(f"{BASE}/orders/", json={"symbol": "601318", "side": "BUY", "quantity": 500,
                                    "order_type": "LIMIT", "price": round(stocks["601318"]["price"] * 1.0, 2)})
big = r.json()
time.sleep(8)
r = s.get(f"{BASE}/orders/{big['order']['id'] - 0}/", ) if False else None
r = s.get(f"{BASE}/orders/", params={"active": 1})
mine = [o for o in r.json()["orders"] if o["id"] == big["order"]["id"]]
check("tick 驱动撮合(全量或部分)", not mine or mine[0]["filled_quantity"] > 0 or mine[0]["status"] == "FILLED",
      f"filled={big['order']['filled_quantity']}")
if mine:
    s.post(f"{BASE}/orders/{mine[0]['id']}/cancel/")

# 10. VIP 回测
r = s.post(f"{BASE}/backtest/", json={"strategy": "ma_cross", "symbol": "600519",
                                      "params": {"fast": 5, "slow": 20}, "days": 200})
run = r.json().get("run", {})
m = run.get("metrics", {})
check("VIP 回测运行", r.status_code == 200 and m.get("trade_count") is not None,
      f"收益 {m.get('total_return_pct')}% 回撤 {m.get('max_drawdown_pct')}% 胜率 {m.get('win_rate_pct')}% 交易 {m.get('trade_count')}")
check("回测结果持久化", run.get("id") and len(run.get("equity_curve", [])) > 100)
r = s.get(f"{BASE}/backtest/history/")
check("回测历史", r.status_code == 200 and len(r.json()["runs"]) >= 1)
r = s.get(f"{BASE}/strategies/")
check("策略列表 schema", len(r.json()["strategies"]) == 4)

# 11. AI 助手(VIP)
r = s.post(f"{BASE}/ai/query/", json={"text": "分析我的持仓"})
check("AI 问答(离线降级)", r.status_code == 200 and len(r.json()["answer"]) > 10,
      r.json()["answer"][:40].replace("\n", " "))
r = s.post(f"{BASE}/ai/query/", json={"text": "继续", "conversation_id": r.json()["conversation"]["id"]})
check("AI 会话延续", r.status_code == 200 and len(r.json()["conversation"]["messages"]) == 4)

# 12. 注册与限流外校验
r = requests.post(f"{BASE}/register/", json={"username": "smoke_user", "password": "abc123", "email": ""})
check("注册新用户", r.status_code == 200 and r.json()["user"]["username"] == "smoke_user")
r = requests.post(f"{BASE}/login/", json={"username": "smoke_user", "password": "bad"})
check("错误密码 400", r.status_code == 400 and r.json()["detail"] == "Invalid credentials")

print(f"\n=== 冒烟结果: {ok_count} 项通过 ===")
