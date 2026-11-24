<script setup>
/** 量化回测:策略选择 → 参数 → 运行 → 绩效展示 + 历史回看(需 VIP) */
import { ref, computed, onMounted } from "vue";
import { useAuthStore } from "../stores/auth";
import { useMarketStore } from "../stores/market";
import {
  fetchStrategies, runBacktest, runCompare, fetchBacktestHistory, fetchBacktestDetail,
} from "../api";
import { fmtMoney, fmtSigned, fmtPct, fmtDateTime, trendClass } from "../utils/format";
import BacktestChart from "../components/BacktestChart.vue";
import CompareChart from "../components/CompareChart.vue";
import AppIcon from "../components/AppIcon.vue";
import AnimatedNumber from "../components/AnimatedNumber.vue";
import EmptyState from "../components/EmptyState.vue";
import { toast } from "../composables/useToast";

const auth = useAuthStore();
const market = useMarketStore();

const strategies = ref([]);
const selectedId = ref("");
const params = ref({});
const symbol = ref("");
const days = ref(120);
const capital = ref(100000);
const running = ref(false);
const result = ref(null);
const history = ref([]);
const loadingHistory = ref(false);

const mode = ref("single"); // single=单策略回测 / compare=跨策略有效性对比
const cmpResult = ref(null);
const cmpRunning = ref(false);
const regimeKeys = computed(() => Object.keys(cmpResult.value?.regime_labels || {}));

async function runCompareAction() {
  if (!symbol.value) return toast.error("请选择对比标的");
  cmpRunning.value = true;
  try {
    cmpResult.value = await runCompare({
      symbol: symbol.value,
      days: days.value,
      initial_capital: Number(capital.value) || 100000,
    });
    toast.success("策略对比完成");
  } catch (e) {
    toast.error(e.friendlyMessage || "对比失败");
  } finally {
    cmpRunning.value = false;
  }
}

function pickStrategy(r) {
  // 点击对比行 → 回填单策略表单继续细调参数
  const spec = strategies.value.find((s) => s.id === r.id);
  if (spec) selectStrategy(spec);
  params.value = { ...r.params };
  mode.value = "single";
}

function regimeCell(r, key) {
  return r.regime?.[key] || null;
}

const selected = computed(() => strategies.value.find((s) => s.id === selectedId.value));
const realIndices = computed(() => market.indices.filter((i) => i.symbol));
const symbolName = computed(() => {
  const inStocks = market.stocks.find((s) => s.symbol === symbol.value);
  if (inStocks) return inStocks.name;
  return market.indices.find((i) => i.symbol === symbol.value)?.name || symbol.value;
});

const metricCards = computed(() => {
  const m = result.value?.metrics;
  if (!m) return [];
  return [
    { label: "总收益率", value: fmtSigned(m.total_return_pct) + "%", cls: trendClass(m.total_return_pct) },
    { label: "年化收益", value: fmtSigned(m.annualized_return_pct) + "%", cls: trendClass(m.annualized_return_pct) },
    { label: "最大回撤", value: fmtPct(m.max_drawdown_pct, false), cls: "down" },
    { label: "胜率", value: `${m.win_rate_pct}%`, cls: m.win_rate_pct >= 50 ? "up" : "flat" },
    { label: "交易次数", value: String(m.trade_count), cls: "flat" },
    { label: "最终权益", value: fmtMoney(m.final_equity), cls: trendClass(m.final_equity - m.initial_capital) },
    { label: "Sharpe", value: String(m.sharpe ?? "--"), cls: trendClass(m.sharpe ?? 0) },
    { label: "盈亏比", value: m.profit_factor == null ? "--" : String(m.profit_factor), cls: (m.profit_factor ?? 0) >= 1 ? "up" : "down" },
  ];
});

async function loadHistory() {
  loadingHistory.value = true;
  try {
    history.value = await fetchBacktestHistory();
  } catch { /* 非 VIP 静默 */ }
  loadingHistory.value = false;
}


async function run() {
  if (!selectedId.value) return toast.error("请先选择一个策略");
  if (!symbol.value) return toast.error("请选择回测标的");
  running.value = true;
  try {
    result.value = await runBacktest({
      strategy: selectedId.value,
      symbol: symbol.value,
      params: { ...params.value },
      days: days.value,
      initial_capital: Number(capital.value) || 100000,
    });
    toast.success("回测完成");
    loadHistory();
  } catch (e) {
    toast.error(e.friendlyMessage || "回测失败");
  } finally {
    running.value = false;
  }
}

async function viewHistory(run) {
  try {
    result.value = await fetchBacktestDetail(run.id);
    selectedId.value = run.strategy;
    symbol.value = run.symbol;
  } catch (e) {
    toast.error(e.friendlyMessage || "加载历史回测失败");
  }
}

onMounted(async () => {
  if (!market.stocks.length) await market.refreshAll();
  try {
    strategies.value = await fetchStrategies();
    if (strategies.value.length) selectStrategy(strategies.value[0]);
  } catch (e) {
    toast.error(e.friendlyMessage || "策略加载失败");
  }
  if (!symbol.value && market.activeStocks.length) symbol.value = market.activeStocks[0].symbol;
  if (auth.isLoggedIn) loadHistory();
});

function selectStrategy(s) {
  selectedId.value = s.id;
  params.value = Object.fromEntries(s.params.map((p) => [p.key, p.default]));
}

function strategyName(id) {
  return strategies.value.find((s) => s.id === id)?.name || id;
}
</script>

<template>
  <div class="page">
    <div class="bt-head">
      <h1 class="page-title">量化回测</h1>
        <p class="page-sub">信号次日开盘成交 · 全仓进出 · 计入佣金与印花税</p>
      </div>

      <div class="tabs bt-tabs">
        <button class="tab" :class="{ active: mode === 'single' }" @click="mode = 'single'">单策略回测</button>
        <button class="tab" :class="{ active: mode === 'compare' }" @click="mode = 'compare'">策略有效性对比</button>
      </div>

      <!-- 跨策略对比 -->
      <div v-if="mode === 'compare'" class="cmp-wrap">
        <section class="panel cmp-toolbar">
          <div class="field">
            <label for="cmp-symbol">对比标的</label>
            <select id="cmp-symbol" v-model="symbol" class="select">
              <optgroup v-if="realIndices.length" label="指数(真实行情)">
                <option v-for="i in realIndices" :key="i.symbol" :value="i.symbol">{{ i.name }}({{ i.symbol }})</option>
              </optgroup>
              <optgroup label="个股">
                <option v-for="s in market.activeStocks" :key="s.id" :value="s.symbol">{{ s.name }}({{ s.symbol }})</option>
              </optgroup>
            </select>
          </div>
          <div class="field">
            <label for="cmp-days">区间:<span class="num gold-text">{{ days }}</span> 交易日</label>
            <input id="cmp-days" v-model.number="days" type="range" min="60" max="250" step="10" class="range" />
          </div>
          <button class="btn btn-primary" :disabled="cmpRunning" @click="runCompareAction">
            <span v-if="cmpRunning" class="spinner"></span>
            {{ cmpRunning ? "对比运行中…" : "▶ 运行对比" }}
          </button>
          <span class="hint cmp-note">同窗口默认参数 · 滚动样本外 3 折 · 分行情状态评估 · 排名按 OOS Sharpe</span>
        </section>

        <template v-if="cmpResult">
          <section class="panel section-gap">
            <h3 class="panel-title">
              有效性排名 · {{ cmpResult.name }}
              <span class="hint">点击行回填单策略表单</span>
            </h3>
            <div class="table-wrap">
              <table class="data cmp-table">
                <thead>
                  <tr>
                    <th>#</th><th>策略</th><th>总收益</th><th>OOS收益</th><th>OOS Sharpe</th>
                    <th>最大回撤</th><th>胜率</th><th>盈亏比</th><th>折稳定性</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in cmpResult.results" :key="r.id" class="cmp-row" @click="pickStrategy(r)">
                    <td class="num rank" :class="{ 'rank-top': r.rank === 1 }">{{ r.rank }}</td>
                    <td class="bold">{{ r.name }}</td>
                    <td class="num" :class="trendClass(r.metrics.total_return_pct)">{{ fmtSigned(r.metrics.total_return_pct) }}%</td>
                    <td class="num" :class="trendClass(r.oos.return_pct)">{{ fmtSigned(r.oos.return_pct) }}%</td>
                    <td class="num bold" :class="trendClass(r.oos.sharpe)">{{ r.oos.sharpe }}</td>
                    <td class="num down">{{ fmtPct(r.metrics.max_drawdown_pct, false) }}</td>
                    <td class="num">{{ r.metrics.win_rate_pct }}%</td>
                    <td class="num">{{ r.metrics.profit_factor == null ? "--" : r.metrics.profit_factor }}</td>
                    <td class="num dim">{{ r.oos.positive_folds }}/{{ r.oos.folds.length }} 折盈利</td>
                    <td><button class="btn btn-sm" @click.stop="pickStrategy(r)">细调</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="panel section-gap">
            <h3 class="panel-title">累计收益率对比 <span class="hint">百分比刻度 · 首席策略加粗</span></h3>
            <CompareChart :comparison="cmpResult" />
          </section>

          <section class="panel section-gap">
            <h3 class="panel-title">分行情状态表现 <span class="hint">regime 由指数日 K 规则判定(无未来函数)</span></h3>
            <div class="table-wrap">
              <table class="data">
                <thead>
                  <tr>
                    <th>策略</th>
                    <th v-for="k in regimeKeys" :key="k">{{ cmpResult.regime_labels[k] }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="r in cmpResult.results" :key="r.id">
                    <td class="bold">{{ r.name }}</td>
                    <td v-for="k in regimeKeys" :key="k">
                      <template v-if="regimeCell(r, k)">
                        <span class="num" :class="trendClass(regimeCell(r, k).return_pct)">
                          {{ fmtSigned(regimeCell(r, k).return_pct) }}%
                        </span>
                        <span class="dim regime-meta">{{ regimeCell(r, k).trade_count }} 笔 · 胜率 {{ regimeCell(r, k).win_rate_pct }}%</span>
                      </template>
                      <span v-else class="dim">--</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
        <section v-else class="panel section-gap">
          <EmptyState icon="scale" title="选择标的后点击「运行对比」"
            sub="四大策略同场竞技:样本外收益、Sharpe、分行情状态表现与折间稳定性" />
        </section>
      </div>

      <div v-else class="bt-grid">
        <!-- 配置区 -->
        <section class="panel config-panel">
          <h3 class="panel-title">1 · 选择策略</h3>
          <div class="strategy-list">
            <button v-for="s in strategies" :key="s.id" class="strategy-card" :class="{ on: selectedId === s.id }"
              @click="selectStrategy(s)">
              <span class="s-name">{{ s.name }}</span>
              <span class="s-desc">{{ s.description }}</span>
            </button>
          </div>

          <h3 class="panel-title" style="margin-top: 18px">2 · 策略参数</h3>
          <div v-if="selected" class="param-grid">
            <div v-for="p in selected.params" :key="p.key" class="field">
              <label :for="`param-${p.key}`">{{ p.label }}</label>
              <input :id="`param-${p.key}`" v-model.number="params[p.key]" class="input num" type="number"
                :min="p.min" :max="p.max" :step="p.type === 'float' ? 0.1 : 1" />
            </div>
          </div>

          <h3 class="panel-title" style="margin-top: 18px">3 · 回测设置</h3>
          <div class="field">
            <label for="bt-symbol">回测标的</label>
            <select id="bt-symbol" v-model="symbol" class="select">
              <optgroup v-if="realIndices.length" label="指数(真实行情)">
                <option v-for="i in realIndices" :key="i.symbol" :value="i.symbol">{{ i.name }}({{ i.symbol }})</option>
              </optgroup>
              <optgroup label="个股">
                <option v-for="s in market.activeStocks" :key="s.id" :value="s.symbol">{{ s.name }}({{ s.symbol }})</option>
              </optgroup>
            </select>
          </div>
          <div class="field">
            <label for="bt-days">回测区间:<span class="num gold-text">{{ days }}</span> 个交易日</label>
            <input id="bt-days" v-model.number="days" type="range" min="60" max="250" step="10" class="range" />
          </div>
          <div class="field">
            <label for="bt-capital">初始资金</label>
            <input id="bt-capital" v-model.number="capital" class="input num" type="number" min="10000" step="10000" />
          </div>

          <button class="btn btn-primary btn-block" :disabled="running" @click="run">
            <span v-if="running" class="spinner"></span>
            {{ running ? "回测运行中…" : "▶ 运行回测" }}
          </button>
        </section>

        <!-- 结果区 -->
        <section class="result-panel">
            <div v-if="result" class="result">
              <div v-if="!result.markers.length" class="panel section-gap hint-bar">
                <AppIcon name="warn" :size="14" /> 本次回测没有产生任何成交——通常是初始资金不足买入一手(该标的现价约 {{ fmtMoney(result.candles.at(-1)?.close) }}/股,一手需 {{ fmtMoney((result.candles.at(-1)?.close || 0) * 100) }}),试着调高初始资金或换标的。
              </div>
            <div class="metric-row">
              <div v-for="m in metricCards" :key="m.label" class="panel stat-card">
                <span class="stat-label">{{ m.label }}</span>
                <span class="stat-value num" :class="m.cls">{{ m.value }}</span>
              </div>
            </div>
            <div class="panel section-gap">
              <h3 class="panel-title">
                策略走势 · {{ symbolName }}
                <span class="hint">▲买点 ▼卖点 · 虚线为买入持有基准</span>
              </h3>
              <BacktestChart :result="result" />
            </div>
            <div v-if="result.trades.length" class="panel section-gap">
              <h3 class="panel-title">逐笔交易 <span class="hint">{{ result.trades.length }} 笔</span></h3>
              <div class="table-wrap">
                <table class="data">
                  <thead>
                    <tr><th>日期</th><th>方向</th><th>数量</th><th>价格</th><th>金额</th><th>费用</th><th>盈亏</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(t, i) in result.trades" :key="i">
                      <td class="num dim">{{ t.time }}</td>
                      <td><span :class="t.side === 'BUY' ? 'up' : 'down'" class="bold">{{ t.side === 'BUY' ? '买入' : '卖出' }}</span></td>
                      <td class="num">{{ t.quantity }}</td>
                      <td class="num">{{ fmtMoney(t.price) }}</td>
                      <td class="num">{{ fmtMoney(t.amount) }}</td>
                      <td class="num dim">{{ fmtMoney(t.fee) }}</td>
                      <td class="num" :class="t.pnl == null ? 'flat' : trendClass(t.pnl)">
                        {{ t.pnl == null ? "--" : fmtSigned(t.pnl) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div v-else class="panel section-gap">
            <EmptyState icon="chart" title="配置策略后点击「运行回测」"
              sub="结果将展示资金曲线、买卖点标记与逐笔绩效" />
          </div>

          <!-- 历史 -->
          <div v-if="history.length" class="panel section-gap">
            <h3 class="panel-title">历史回测 <span class="hint">点击查看完整结果</span></h3>
            <div class="history-list">
              <button v-for="h in history" :key="h.id" class="history-item" @click="viewHistory(h)">
                <span class="symbol-badge">{{ h.symbol }}</span>
                <span class="h-strategy">{{ strategyName(h.strategy) }}</span>
                <span class="num" :class="trendClass(h.metrics?.total_return_pct)">
                  {{ fmtSigned(h.metrics?.total_return_pct ?? 0) }}%
                </span>
                <span class="h-time dim">{{ fmtDateTime(h.created_at) }}</span>
              </button>
            </div>
          </div>
        </section>
      </div>
  </div>
</template>

<style scoped>

.page-title { font-size: 24px; display: flex; align-items: center; gap: 10px; }
.page-sub { color: var(--text-3); font-size: 13px; margin: 6px 0 18px; }
.bt-grid { display: grid; grid-template-columns: 360px 1fr; gap: 16px; align-items: start; }
.strategy-list { display: grid; gap: 9px; }
.strategy-card {
  text-align: left;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--inset-bg);
  color: var(--text-2);
  cursor: pointer;
  display: grid;
  gap: 4px;
  transition: all 0.2s var(--ease-out);
}
.strategy-card:hover { border-color: var(--border-strong); transform: translateX(3px); }
.strategy-card.on {
  border-color: var(--brand-a);
  background: rgba(34, 211, 238, 0.1);
  box-shadow: var(--glow-brand);
}
.s-name { font-weight: 700; color: var(--text-1); }
.s-desc { font-size: 12px; line-height: 1.5; }
.param-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.range { width: 100%; accent-color: var(--brand-a); }
.gold-text { color: var(--gold); font-weight: 700; }
.metric-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.bt-tabs { margin-bottom: 14px; }
.cmp-toolbar { display: flex; align-items: end; gap: 16px; flex-wrap: wrap; }
.cmp-toolbar .field { margin: 0; min-width: 180px; }
.cmp-note { flex: 1; min-width: 220px; }
.cmp-row { cursor: pointer; }
.cmp-row:hover td { background: rgba(34, 211, 238, 0.06); }
.rank { font-weight: 800; }
.rank-top { color: var(--gold); }
.regime-meta { display: block; font-size: 11px; margin-top: 2px; }
.stat-card { padding: 12px 14px; }
.stat-label { display: block; font-size: 11px; color: var(--text-3); margin-bottom: 4px; }
.stat-value { font-size: 19px; font-weight: 800; }
.history-list { display: grid; gap: 7px; max-height: 260px; overflow-y: auto; }
.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--inset-bg-soft);
  color: var(--text-2);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.18s;
}
.history-item:hover { border-color: var(--brand-a); background: rgba(34, 211, 238, 0.06); }
.h-strategy { flex: 1; text-align: left; font-weight: 600; color: var(--text-1); }
.h-time { font-size: 11px; }
.dim { color: var(--text-3); }
.bold { font-weight: 700; }
.hint-bar {
  padding: 10px 14px;
  border: 1px solid rgba(255, 180, 84, 0.4);
  background: rgba(255, 180, 84, 0.08);
  border-radius: var(--radius);
  color: var(--warn);
  font-size: 13px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}
@media (max-width: 1020px) {
  .bt-grid { grid-template-columns: 1fr; }
  .metric-row { grid-template-columns: repeat(2, 1fr); }
}
</style>
