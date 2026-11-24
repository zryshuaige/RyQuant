"""全链路冒烟:登录→行情/来源→市场脉冲+策略推荐→自选(加入日期)→回测→策略对比→AI"""
import requests

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

# 2. 行情与来源标注
r = s.get(f"{BASE}/stocks/")
stocks = {x["symbol"]: x for x in r.json()}
check("股票列表+来源字段", r.status_code == 200 and len(stocks) >= 8
      and all("quote_source" in x for x in stocks.values()))
r = s.get(f"{BASE}/indices/")
idx = r.json()["indices"]
check("指数(真实行情)", len(idx) == 3 and all(abs(i["change_pct"]) < 11 for i in idx),
      f"{[(i['name'], i['change_pct'], i.get('quote_source')) for i in idx]}")
r = s.get(f"{BASE}/kline/", params={"symbol": "600519", "limit": 30})
kd = r.json()
check("K线+逐根来源", r.status_code == 200 and len(kd["klines"]) == 30 and len(kd["sources"]) == 30)
r = s.get(f"{BASE}/sectors/")
check("板块(真实成分)", r.status_code == 200 and len(r.json()["sectors"]) == 4)

# 3. 市场脉冲 + 当前状态策略推荐
r = s.get(f"{BASE}/market/pulse/")
p = r.json()
check("市场脉冲 regime", r.status_code == 200 and p["regime"] in ("bull", "bear", "range", "high_vol"),
      f"{p['label']} score={p['score']}")
check("脉冲证据链", len(p["evidence"]) >= 3)
check("当前状态适用策略推荐", len(p.get("advice", [])) >= 1 and "reason" in p["advice"][0],
      f"top={p['advice'][0]['name'] if p.get('advice') else '--'}")

# 4. 自选:加入日期可查
r = s.post(f"{BASE}/favorites/", json={"stock_id": stocks["000858"]["id"]})
check("加自选", r.status_code == 201 and r.json().get("created_at"))
fav_id = r.json()["id"]
r = s.get(f"{BASE}/favorites/")
check("自选列表含加入日期", r.status_code == 200 and all(f.get("created_at") for f in r.json()))
r = s.delete(f"{BASE}/favorites/{fav_id}/")
check("移除自选", r.status_code == 204)

# 5. 单策略回测 + 持久化
r = s.post(f"{BASE}/backtest/", json={"strategy": "ma_cross", "symbol": "600519",
                                      "params": {"fast": 5, "slow": 20}, "days": 200})
run = r.json().get("run", {})
m = run.get("metrics", {})
check("回测运行+风险指标", r.status_code == 200 and "sharpe" in m and "profit_factor" in m,
      f"收益 {m.get('total_return_pct')}% Sharpe {m.get('sharpe')} 回撤 {m.get('max_drawdown_pct')}%")
check("回测结果持久化", run.get("id") and len(run.get("equity_curve", [])) > 100)
r = s.get(f"{BASE}/backtest/history/")
check("回测历史", r.status_code == 200 and len(r.json()["runs"]) >= 1)
r = s.get(f"{BASE}/strategies/")
check("策略列表 schema", len(r.json()["strategies"]) == 4)

# 6. 跨策略有效性对比(核心功能)
r = s.post(f"{BASE}/backtest/compare/", json={"symbol": "sh000001", "days": 200})
c = r.json()
results = c.get("results", [])
check("策略对比排名", r.status_code == 200 and len(results) == 4
      and [x["rank"] for x in results] == [1, 2, 3, 4],
      f"top={results[0]['name'] if results else '--'} OOS Sharpe={results[0]['oos']['sharpe'] if results else '--'}")
check("样本外折+regime 分解", all(len(x["oos"]["folds"]) == 3 and "regime" in x for x in results))

# 7. AI 助手(登录即可,离线降级)
r = s.post(f"{BASE}/ai/query/", json={"text": "现在大盘适合什么策略?"})
check("AI 问答(离线降级)", r.status_code == 200 and len(r.json()["answer"]) > 10,
      r.json()["answer"][:40].replace("\n", " "))
r = s.post(f"{BASE}/ai/query/", json={"text": "继续", "conversation_id": r.json()["conversation"]["id"]})
check("AI 会话延续", r.status_code == 200 and len(r.json()["conversation"]["messages"]) == 4)

# 8. 注册与错误密码
r = requests.post(f"{BASE}/register/", json={"username": "smoke_user", "password": "abc123", "email": ""})
check("注册新用户", r.status_code == 200 and r.json()["user"]["username"] == "smoke_user")
r = requests.post(f"{BASE}/login/", json={"username": "smoke_user", "password": "bad"})
check("错误密码 400", r.status_code == 400 and r.json()["detail"] == "Invalid credentials")

# 9. 已下单接口应不存在(产品已移除交易功能)
r = s.post(f"{BASE}/orders/", json={})
check("下单接口已移除", r.status_code == 404)

print(f"\n=== 冒烟结果: {ok_count} 项通过 ===")