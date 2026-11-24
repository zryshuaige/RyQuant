# RyQuant · 模拟交易终端

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2%20LTS-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.16-D7000F?logo=djangoRESTFramework&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-646CFF?logo=vite&logoColor=white)
![Pinia](https://img.shields.io/badge/Pinia-3-F7D336?logo=pinia&logoColor=black)
![ECharts](https://img.shields.io/badge/ECharts-6-AA344D?logo=apacheecharts&logoColor=white)
![Axios](https://img.shields.io/badge/Axios-1.x-5A29E4?logo=axios&logoColor=white)
![Vitest](https://img.shields.io/badge/Vitest-3-6E9F18?logo=vitest&logoColor=white)

一个功能闭环的**模拟股票交易平台**:Django + DRF 后端(撮合引擎 / 真实行情接入 / 资金冻结结算 / 市场脉冲推断 / 策略有效性对比 / VIP 量化回测)+ Vue 3 深色金融终端前端。指数与个股实时行情、历史日 K 均来自真实数据源(失败自动回退模拟并全程标注来源),离线亦可运行;所有资金均为模拟数据。

![RyQuant 首页](docs/home.png)

## 功能总览

**交易闭环(真实业务规则)**

- 下单:限价 / 市价,整手校验(主板 100 股、科创板 688 每手 200 股)、涨跌停价格区间校验
- 撮合引擎:限价单价格穿越市价即撮合(成交价 = 市价,对用户有利),每个行情 tick 提供随机深度,**支持部分成交**
- 撤单:仅本人、仅未成交 / 部分成交可撤;**买单报单即冻结资金、卖单冻结持仓**,成交结算 / 撤单解冻,多退少补
- 订单状态机:`PENDING → PARTIAL_FILLED → FILLED / CANCELLED`,当前委托 / 成交记录 / 历史委托全链路可查

**行情与真实数据**

- 个股与指数:每 tick 一次批量抓取**腾讯实时真实行情**(完整格式,字段自校验防错位),逐标的失败回退随机游走(受涨跌停约束),聚合分钟 / 日 K 线并驱动撮合
- 来源可追溯:`Stock.quote_source` / `Candle.source` 记录真实 / 模拟,前端列表、指数卡、K 线头部全程「真实 / 模拟」徽章
- 历史日 K:`seed_demo` 优先抓取腾讯真实数据(前复权 250 根),失败回退网易源、再回退随机模拟;运行期每交易日自动增量补抓真实日 K,离线不受影响
- 一键升级 / 刷新真实历史:`python manage.py seed_demo --refresh-history`
- 板块行情由成分股真实日 K / 报价计算,不再虚构

**市场脉冲与策略有效性**

- 市场脉冲 `GET /api/market/pulse/`:涨跌家数 / 站上 MA20 比例 / 均线趋势与斜率 / 20 日波动率分位 → 规则化判定多头 / 空头 / 震荡 / 高波动,附证据链;离线可用,60s 缓存
- AI 投研助手离线与 DeepSeek 双路径均注入脉冲上下文
- 策略对比 `POST /api/backtest/compare/`:四策略同窗口默认参数 → 全窗口指标 + 滚动 3 折样本外 + 分 regime 条件化评估 + 排名(OOS Sharpe 主排序);信号仅用历史收盘,无未来函数
- 回测指标含 Sharpe / 波动率 / 盈亏比 / Calmar / 仓位暴露 / 平均持仓天数

**VIP 量化回测**

- 4 个内置策略:双均线交叉 / MACD 金叉死叉 / RSI 均值回归 / 布林带突破,参数 schema 驱动前端动态表单
- 回测标的支持**个股与真实指数**
- 回测引擎:信号**次日开盘成交**(无未来函数)、全仓进出;输出资金曲线 vs 买入持有基准(百分比刻度)、最大回撤、胜率、逐笔交易
- 回测结果持久化,支持历史回看;服务端 VIP 强制校验

**其他**

- 深 / 浅双主题:头部 ☀️/🌙 一键切换,偏好持久化,图表配色联动重绘
- AI 投研助手:配置 `DEEPSEEK_API_KEY` 调用真实大模型;未配置自动降级内置离线分析,会话可延续
- 自选股、财经快讯、Django Admin 后台

## 架构

```
financeapp/
├── backend/                    # Django + DRF
│   ├── manage.py  requirements.txt  .env.example  smoke_test.py
│   ├── finproj/                # 配置(env 驱动)与根路由
│   └── trading/
│       ├── models/             # stock / account / order / market / ai / backtest / favorite
│       ├── services/           # trading(领域) / matching(撮合) / market_sim(行情) / fees / ai_client
│       │   └── quant/          # indicators / strategies(注册表) / engine(回测)
│       ├── api/                # 按域拆分的视图 + 权限 + 限流 + 统一异常
│       ├── management/commands/seed_demo.py
│       └── tests/              # 64 个后端测试
└── frontend/                   # Vue 3 + Vite + Pinia
    └── src/
        ├── api/  stores/  router/          # 接口层 / 状态 / 路由守卫
        ├── components/                     # OrderModal(唯一) / KlineChart / BacktestChart / StockTable …
        ├── views/                          # 行情总览 / 持仓四Tab / 自选 / 量化回测 / AI / 登录注册
        └── styles/                         # 深浅双主题设计系统 tokens / base / components
```

## 快速开始

要求:Python ≥ 3.9、Node ≥ 18。

**1. 后端**(默认端口 8000;被占用可换 8080)

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # 一键生成演示数据(幂等,自动抓取真实历史)
python manage.py runserver 127.0.0.1:8080
```

**2. 前端**

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173(默认代理指向 127.0.0.1:8080)
```

> 前端代理目标可用环境变量覆盖:`BACKEND_ORIGIN=http://127.0.0.1:8000 npm run dev`

**3. 体验**

- 演示账号:`demo / demo123456`(VIP 已开通,预置持仓 / 委托 / 成交)
- 管理后台:`http://127.0.0.1:8080/admin/`(`admin / admin123456`)
- 注册后自动创建资金账户;VIP 可在量化回测 / AI 页一键开通

## 环境变量(`backend/.env`,参考 `.env.example`)

| 变量 | 说明 | 默认 |
|---|---|---|
| `SECRET_KEY` / `DEBUG` / `ALLOWED_HOSTS` | Django 基础配置 | dev 默认 |
| `CORS_ALLOWED_ORIGINS` | 跨域白名单 | localhost:5173 |
| `INITIAL_CAPITAL` | 新账户初始模拟资金 | 100000 |
| `MARKET_SIMULATION` | 行情模拟器开关 | 1 |
| `SIMULATOR_TICK_SECONDS` | 模拟 tick 间隔(秒) | 3 |
| `DEEPSEEK_API_KEY` | 留空则 AI 走离线模拟回答 | 空 |

## API 一览(前缀 `/api/`,Token 认证)

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/register/` `/login/` | 注册 / 登录 → `{token, user}` |
| GET | `/stocks/` `/indices/` `/kline/` `/sectors/` `/news/` | 行情(公开,含来源标注) |
| GET | `/market/pulse/` | 市场脉冲:regime / 广度 / 板块热度(公开) |
| GET/POST/DELETE | `/favorites/` `(/<id>/)` | 自选股 |
| POST | `/order/`(旧别名)`/orders/` | 下单 → `{order, cash}` |
| GET | `/orders/?status=&active=1` | 委托列表(含状态) |
| POST | `/orders/<id>/cancel/` | 撤单并解冻 |
| GET | `/trades/` | 成交记录(逐笔) |
| GET | `/positions/` | 持仓 + 资金汇总 |
| POST | `/ai/activate/` `/ai/query/` | VIP 开通 / AI 问答(VIP) |
| GET | `/strategies/` | 回测策略与参数 schema |
| POST | `/backtest/` | 运行回测(VIP,限流 10/min) |
| POST | `/backtest/compare/` | 跨策略有效性对比(VIP,限流 10/min,不持久化) |
| GET | `/backtest/history/(/<id>/)` | 回测历史 / 详情 |

## 测试

```bash
# 后端(94 个用例:下单校验 / 撮合 / 部分成交 / 冻结结算 / 撤单 / 权限 / 回测引擎 / 指标 / 报价parser / 行情推断 / 策略对比)
cd backend && python manage.py test trading

# 前端(20 个用例:格式化 / 下单校验 / 涨停基准)
cd frontend && npm test

# 全链路冒烟(需后端已启动)
cd backend && python smoke_test.py
```

## 生产部署提示

- 设置强 `SECRET_KEY`、`DEBUG=0`、明确的 `ALLOWED_HOSTS` 与 `CORS_ALLOWED_ORIGINS`
- 前端 `npm run build` 后由 Nginx 托管 `dist/`,并将 `/api` 反代到 Django(gunicorn / uwsgi);
  行情模拟器随 runserver 自动启动;生产部署另起常驻进程:`python manage.py run_simulator`
- SQLite 适用于演示;高并发建议切换 PostgreSQL(仅改 `DATABASES`)
- 真实行情依赖腾讯公网接口,若有代理 / 白名单要求请自行调整 `services/market_sim.py` 与 `seed_demo`

## 路线图(与轻量目标权衡后留待后续)

- 策略评估进阶:Deflated Sharpe Ratio / PBO(CPCV)/ 参数网格优化与参数高原分析
- 行情推断进阶:HMM regime switching、情绪因子(FinBERT 类)
- 组合 / 多标的回测、仓位管理选项、滑点模型
- WebSocket 推送替代轮询;原生 App 打包

## 免责声明

本项目仅用于技术学习与演示,不构成任何投资建议。
