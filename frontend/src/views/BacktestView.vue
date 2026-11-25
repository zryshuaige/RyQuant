<script setup>
/** 量化回测:单策略结果 + 跨策略对比(术语分层,先给结论再给细节) */
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useMarketStore } from "../stores/market";
import {
  fetchStrategies, runBacktest, runCompare, fetchBacktestHistory, fetchBacktestDetail,
  previewStrategy, deleteCustomStrategy,
} from "../api";
import { fmtMoney, fmtSigned, fmtPct, fmtDateTime, trendClass } from "../utils/format";
import BacktestChart from "../components/BacktestChart.vue";
import CompareChart from "../components/CompareChart.vue";
import StrategyPreview from "../components/StrategyPreview.vue";
import StrategyBuilder from "../components/StrategyBuilder.vue";
import ParamSlider from "../components/ParamSlider.vue";
import AppIcon from "../components/AppIcon.vue";
import InfoTip from "../components/InfoTip.vue";
import SymbolSearch from "../components/SymbolSearch.vue";
import DataTable from "../components/DataTable.vue";
import DataPagination from "../components/DataPagination.vue";
import { usePagedSort } from "../composables/usePagedSort";
import { useCountUp } from "../composables/useCountUp";
import { toast } from "../composables/useToast";

const auth = useAuthStore();
const market = useMarketStore();
const route = useRoute();

const strategies = ref([]);
const selectedId = ref("");
const params = ref({});
const symbol = ref("");
const days = ref(120);
const capital = ref(100000);
const running = ref(false);
const result = ref(null);
const resultMeta = ref(null);
const resultStale = ref(false);
const history = ref([]);
const loadingHistory = ref(false);
const historyOpen = ref(false);

const mode = ref("single");
const cmpResult = ref(null);
const cmpRunning = ref(false);
const cmpStale = ref(false);
const cmpDays = ref(120);
const showPro = ref(false);
const showRegime = ref(false);
const tradesOpen = ref(false);
const resultsEl = ref(null);
const configEl = ref(null);

const selected = computed(() => strategies.value.find((s) => s.id === selectedId.value));
const symbolName = computed(() => {
  const inStocks = market.stocks.find((s) => s.symbol === symbol.value);
  if (inStocks) return inStocks.name;
  return market.indices.find((i) => i.symbol === symbol.value)?.name || symbol.value;
});
const canRun = computed(() => Boolean(selectedId.value && symbol.value && !running.value));

/* 策略白话解释与现代化参数控件 */
const FITS = { bull: "多头趋势", bear: "空头趋势", range: "震荡", high_vol: "高波动" };
const capitalChips = [10000, 100000, 500000, 1000000];
function ruleText(tpl) {
  return String(tpl || "").replace(/\{(\w+)\}/g, (_, k) => params.value[k] ?? "");
}
function cardEssence(s) {
  // 选中卡用实时参数,其余卡用自身默认值——避免占位符裸露或串用他策参数
  const vals = selectedId.value === s.id
    ? params.value
    : Object.fromEntries(s.params.map((p) => [p.key, p.default]));
  return String(s.essence || "").replace(/\{(\w+)\}/g, (_, k) => vals[k] ?? "");
}
function presetActive(p) {
  return Object.entries(p.values).every(([k, v]) => Number(params.value[k]) === Number(v));
}
const activePresetHint = computed(() => {
  const hit = (selected.value?.presets || []).find(presetActive);
  return hit ? hit.hint : "自定义参数";
});
function applyPreset(p) {
  params.value = { ...params.value, ...p.values };
}
const capitalTrack = computed(() => {
  const pct = Math.min(100, Math.max(0, ((capital.value - 10000) / 990000) * 100));
  return `linear-gradient(90deg, var(--accent) ${pct}%, var(--inset-bg) ${pct}%)`;
});
const tradeLot = computed(() => {
  const stock = market.stocks.find((s) => s.symbol === symbol.value);
  return stock?.lot_size || 100;
});

/* 策略实时预览:参数/对象/区间变化 → debounce 刷新指标与信号(序号守卫防竞态) */
const previewData = ref(null);
const previewLoading = ref(false);
let previewSeq = 0;
let previewTimer = 0;
async function refreshPreview() {
  if (mode.value !== "single" || !selectedId.value || !symbol.value) {
    previewData.value = null;
    return;
  }
  const my = ++previewSeq;
  previewLoading.value = true;
  try {
    const res = await previewStrategy({
      strategy: selectedId.value, symbol: symbol.value,
      days: days.value, params: { ...params.value },
    });
    if (my !== previewSeq) return;
    previewData.value = { candles: res.candles, preview: res.preview };
  } catch {
    if (my === previewSeq) previewData.value = null;
  } finally {
    if (my === previewSeq) previewLoading.value = false;
  }
}
function schedulePreview(delay = 350) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(refreshPreview, delay);
}

/* 我的策略:搭建器 / 编辑 / 删除 / 内置预填 */
const builderOpen = ref(false);
const builderInitial = ref(null);
const builderPrefill = ref(null);
const customCount = computed(() => strategies.value.filter((s) => s.custom).length);
function openBuilder() {
  builderInitial.value = null;
  builderPrefill.value = null;
  builderOpen.value = true;
}
function editCustom(s) {
  builderInitial.value = { id: Number(s.id.slice(7)), name: s.name, rule: s.rule, fits: s.fits };
  builderPrefill.value = null;
  builderOpen.value = true;
}
async function removeCustom(s) {
  if (!window.confirm(`删除自定义策略「${s.name}」?历史回测记录仍会保留。`)) return;
  try {
    await deleteCustomStrategy(Number(s.id.slice(7)));
    toast.success("已删除");
    strategies.value = await fetchStrategies();
    if (selectedId.value === s.id && strategies.value.length) selectStrategy(strategies.value[0]);
  } catch (e) {
    toast.error(e.friendlyMessage || "删除失败");
  }
}
const BUILTIN_RULES = {
  ma_cross: (p) => ({
    buy: { left: { kind: "sma", n: p.fast }, op: "cross_up", right: { kind: "sma", n: p.slow } },
    sell_mirror: true,
  }),
  macd: (p) => ({
    buy: {
      left: { kind: "dif", fast: p.fast, slow: p.slow, signal: p.signal },
      op: "cross_up",
      right: { kind: "dea", fast: p.fast, slow: p.slow, signal: p.signal },
    },
    sell_mirror: true,
  }),
  rsi_reversion: (p) => ({
    buy: { left: { kind: "rsi", n: p.period }, op: "cross_up", right: { kind: "const", value: p.oversold } },
    sell: { left: { kind: "rsi", n: p.period }, op: "cross_down", right: { kind: "const", value: p.overbought } },
  }),
  boll_breakout: (p) => ({
    buy: { left: { kind: "close" }, op: "cross_up", right: { kind: "boll_upper", n: p.n, k: p.k } },
    sell: { left: { kind: "close" }, op: "cross_down", right: { kind: "boll_mid", n: p.n, k: p.k } },
  }),
};
function saveAsCustom() {
  const s = selected.value;
  const make = s && BUILTIN_RULES[s.id];
  if (!make) return;
  builderInitial.value = null;
  builderPrefill.value = { name: `${s.name}·我的`, rule: make(params.value), fits: [...s.fits] };
  builderOpen.value = true;
}
async function onCustomSaved(rec) {
  try {
    strategies.value = await fetchStrategies();
    const spec = strategies.value.find((x) => x.id === `custom_${rec.id}`);
    if (spec) selectStrategy(spec);
    schedulePreview(80);
  } catch { /* 列表刷新失败不阻塞保存成功提示 */ }
}

/* 策略卡片小图标(内联 SVG 路径) */
const GLYPHS = {
  ma_cross: ["M2 16 C8 16 10 6 22 6", "M2 8 C10 8 14 18 22 18"],
  macd: ["M4 14v4", "M8 10v8", "M12 5v14", "M16 10v8", "M20 14v4"],
  rsi_reversion: ["M2 15 C6 5 9 19 13 11 S19 7 22 12", "M2 6h20", "M2 18h20"],
  boll_breakout: ["M2 6 C8 10 16 4 22 8", "M2 12 C8 16 16 10 22 14", "M2 18 C8 22 16 16 22 20"],
};
function glyphPaths(s) {
  return GLYPHS[s.id] || ["M4 4h7v7H4z", "M13 4h7v7h-7z", "M13 13h7v7h-7z"];
}

/* 逐笔交易与历史回测:分页 + 排序 */
const tradeRows = computed(() => result.value?.trades || []);
const {
  pageRows: tradePageRows, page: tradePage, pageSize: tradePageSize,
  total: tradeTotal, totalPages: tradeTotalPages,
  sortKey: tradeSortKey, sortDir: tradeSortDir,
  toggleSort: tradeToggleSort, setPage: setTradePage, setPageSize: setTradePageSize,
} = usePagedSort(tradeRows, { pageSize: 10 });
const tradeColumns = [
  { key: "time", label: "日期", mono: true },
  { key: "side", label: "方向" },
  { key: "quantity", label: "数量", align: "right" },
  { key: "price", label: "价格", align: "right" },
  { key: "amount", label: "金额", align: "right" },
  { key: "fee", label: "费用", align: "right" },
  { key: "pnl", label: "盈亏", align: "right", sortable: true },
];
const {
  pageRows: historyPageRows, page: historyPage, pageSize: historyPageSize,
  total: historyTotal, totalPages: historyTotalPages,
  sortKey: historySortKey, sortDir: historySortDir,
  toggleSort: historyToggleSort, setPage: setHistoryPage, setPageSize: setHistoryPageSize,
} = usePagedSort(history, { pageSize: 8, sortKey: "created_at", sortDir: "desc" });
const historyColumns = [
  { key: "created_at", label: "时间", mono: true, sortable: true },
  { key: "strategy_name", label: "策略" },
  { key: "symbol", label: "代码", mono: true },
  { key: "return", label: "总收益", align: "right", sortable: true, value: (h) => h.metrics?.total_return_pct ?? 0 },
];

/* 结果英雄区:总收益大数字滚动 + 相对买入持有的超额 */
const heroReturn = useCountUp(computed(() => result.value?.metrics?.total_return_pct ?? 0));
const heroExcess = computed(() => {
  const m = result.value?.metrics;
  if (!m) return 0;
  return (m.total_return_pct ?? 0) - (m.benchmark_return_pct ?? 0);
});
const winLoss = computed(() => {
  const sells = (result.value?.trades || []).filter((t) => t.side === "SELL" && t.pnl != null);
  const wins = sells.filter((t) => t.pnl > 0).length;
  return { wins, losses: sells.length - wins, total: sells.length };
});
const drawdownSpan = computed(() => {
  const curve = result.value?.equity_curve || [];
  let peak = 0; let best = 0; let from = ""; let to = "";
  for (let i = 0; i < curve.length; i++) {
    if (curve[i].equity > curve[peak].equity) peak = i;
    const dd = curve[peak].equity ? curve[i].equity / curve[peak].equity - 1 : 0;
    if (dd < best) { best = dd; from = curve[peak].date; to = curve[i].date; }
  }
  return from && to ? `${from} → ${to}` : "";
});
const primaryMetrics = computed(() => {
  const m = result.value?.metrics;
  if (!m) return [];
  return [
    { label: "最大回撤", value: fmtPct(m.max_drawdown_pct, false), cls: "", sub: drawdownSpan.value || "区间最深跌幅" },
    { label: "胜率", value: `${m.win_rate_pct}%`, cls: "", sub: `${winLoss.value.wins} 胜 ${winLoss.value.losses} 负`, bar: true },
    { label: "交易次数", value: String(m.trade_count), cls: "", sub: `平均持有 ${m.avg_hold_days} 天` },
    { label: "年化收益", value: `${fmtSigned(m.annualized_return_pct)}%`, cls: trendClass(m.annualized_return_pct), sub: `波动率 ${m.volatility_pct}%` },
  ];
});
const detailMetrics = computed(() => {
  const m = result.value?.metrics;
  if (!m) return [];
  return [
    { label: "最终权益", value: `¥${fmtMoney(m.final_equity)}`, cls: trendClass(m.final_equity - m.initial_capital) },
    { label: "夏普比率", value: m.sharpe ?? "--", cls: "" },
    { label: "盈亏比", value: m.profit_factor == null ? "--" : m.profit_factor, cls: "" },
    { label: "在场时间", value: `${m.exposure_pct}%`, cls: "" },
  ];
});
const regimeKeys = computed(() => Object.keys(cmpResult.value?.regime_labels || {}));
const compareConclusion = computed(() => {
  const rows = cmpResult.value?.results || [];
  const best = rows[0];
  if (!best) return "";
  if (!best.metrics?.trade_count) {
    return "本轮对比中没有策略产生交易,通常是初始资金不足或回测区间太短。";
  }
  const base = `最近 ${cmpDays.value} 个交易日中,${best.name}的样本外表现`;
  const detail = `(收益 ${fmtSigned(best.oos.return_pct)}%,夏普 ${best.oos.sharpe}),最大回撤 ${fmtPct(best.metrics.max_drawdown_pct, false)}`;
  return best.oos.sharpe < 0
    ? `当前区间 ${rows.length} 种策略整体偏弱,${best.name}相对最好${detail}。`
    : `${base}最好${detail}。`;
});

function markStale() {
  if (result.value) resultStale.value = true;
  if (cmpResult.value) cmpStale.value = true;
}

function selectStrategy(s) {
  selectedId.value = s.id;
  params.value = Object.fromEntries(s.params.map((p) => [p.key, p.default]));
}
function onSymbol(stock) { symbol.value = stock.symbol; }

async function run() {
  if (!selectedId.value) return toast.error("请先选择策略");
  if (!symbol.value) return toast.error("请选择回测对象");
  running.value = true;
  const snapshot = {
    strategy: selected.value?.name || selectedId.value,
    symbolName: symbolName.value,
    days: days.value,
    capital: Number(capital.value),
    params: { ...params.value },
    paramsText: (selected.value?.params || [])
      .map((p) => `${p.label} ${params.value[p.key]}`).join(" · "),
  };
  try {
    result.value = await runBacktest({
      strategy: selectedId.value,
      symbol: symbol.value,
      params: { ...params.value },
      days: days.value,
      initial_capital: snapshot.capital || 100000,
    });
    resultMeta.value = snapshot;
    resultStale.value = false;
    tradesOpen.value = false;
    toast.success("回测完成");
    loadHistory();
    await nextTick();
    resultsEl.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    toast.error(e.friendlyMessage || "回测失败");
  } finally {
    running.value = false;
  }
}

async function runCompareAction() {
  if (!symbol.value) return toast.error("请选择对比对象");
  cmpRunning.value = true;
  try {
    cmpResult.value = await runCompare({
      symbol: symbol.value,
      days: days.value,
      initial_capital: Number(capital.value) || 100000,
      strategies: strategies.value.map((s) => s.id), // 内置 + 我的策略同场竞技
    });
    cmpDays.value = days.value;
    cmpStale.value = false;
    toast.success("策略对比完成");
  } catch (e) {
    toast.error(e.friendlyMessage || "对比失败");
  } finally {
    cmpRunning.value = false;
  }
}

async function pickStrategy(row) {
  const spec = strategies.value.find((s) => s.id === row.id);
  if (!spec) return;
  mode.value = "single";
  selectStrategy(spec);
  params.value = { ...row.params };
  await nextTick();
  configEl.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  run();
}

function regimeCell(row, key) {
  return row.regime?.[key] || null;
}

async function loadHistory() {
  loadingHistory.value = true;
  try {
    history.value = await fetchBacktestHistory();
  } catch { /* 历史记录失败不影响本次结果 */ }
  loadingHistory.value = false;
}

async function viewHistory(run) {
  try {
    const detail = await fetchBacktestDetail(run.id);
    result.value = detail;
    selectedId.value = run.strategy;
    params.value = { ...(run.params || {}) };
    days.value = run.days;
    capital.value = Number(run.initial_capital);
    symbol.value = run.symbol;
    resultMeta.value = {
      strategy: run.strategy_name || strategyName(run.strategy),
      symbolName: market.stocks.find((s) => s.symbol === run.symbol)?.name
        || market.indices.find((i) => i.symbol === run.symbol)?.name || run.symbol,
      days: run.days,
      capital: Number(run.initial_capital),
      params: { ...(run.params || {}) },
      paramsText: paramSummary(run.params || {}, run.strategy),
    };
    resultStale.value = false;
    mode.value = "single";
    await nextTick();
    resultsEl.value?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    toast.error(e.friendlyMessage || "加载历史回测失败");
  }
}

function strategyName(id) {
  const hit = strategies.value.find((s) => s.id === id);
  if (hit) return hit.name;
  return String(id).startsWith("custom_") ? "自定义策略(已删除)" : id;
}

function paramSummary(values, strategyId) {
  const spec = strategies.value.find((s) => s.id === strategyId);
  return (spec?.params || [])
    .map((p) => `${p.label} ${values[p.key]}`).join(" · ");
}

watch([selectedId, symbol, days, capital], markStale);
watch(params, markStale, { deep: true });
watch([selectedId, symbol, days], () => schedulePreview(120));
watch(params, () => schedulePreview(), { deep: true });
watch(mode, (m) => { if (m === "single") schedulePreview(80); });

onMounted(async () => {
  await market.ensureLoaded();
  try {
    strategies.value = await fetchStrategies();
  } catch (e) {
    toast.error(e.friendlyMessage || "策略加载失败");
  }
  const queryStrategy = String(route.query.strategy || "");
  const found = strategies.value.find((s) => s.id === queryStrategy);
  if (found) selectStrategy(found);
  else if (strategies.value.length) selectStrategy(strategies.value[0]);

  const qSymbol = String(route.query.symbol || "");
  symbol.value = qSymbol || market.activeStocks[0]?.symbol || market.indices[0]?.symbol || "";
  if (String(route.query.tab || "") === "compare") mode.value = "compare";
  schedulePreview(150);

  if (auth.isLoggedIn) loadHistory();

  if (String(route.query.autorun || "") === "1") {
    await nextTick();
    if (mode.value === "compare") runCompareAction();
    else run();
  }
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">量化回测</h1>
        <p class="page-sub">在历史行情上检验策略,并对比当前行情下哪种策略更有效。</p>
      </div>
      <div class="segmented" role="tablist" aria-label="回测模式">
        <button class="seg" :class="{ on: mode === 'single' }" role="tab" :aria-selected="mode === 'single'"
          @click="mode = 'single'">单策略</button>
        <button class="seg" :class="{ on: mode === 'compare' }" role="tab" :aria-selected="mode === 'compare'"
          @click="mode = 'compare'">策略对比</button>
      </div>
    </div>

    <div v-if="mode === 'compare'" class="cmp-wrap">
      <section class="panel cmp-toolbar">
        <div class="toolbar-field symbol-field">
          <label>对比对象</label>
          <SymbolSearch placeholder="输入代码或名称" @select="onSymbol" />
        </div>
        <div class="toolbar-field">
          <label>回测区间</label>
          <div class="segmented">
            <button v-for="d in [60, 120, 250]" :key="d" class="seg" :class="{ on: days === d }"
              @click="days = d">{{ d }} 日</button>
          </div>
        </div>
        <button class="btn btn-primary" :disabled="cmpRunning" @click="runCompareAction">
          <span v-if="cmpRunning" class="spinner"></span>
          {{ cmpRunning ? "对比中…" : "运行对比" }}
        </button>
        <div class="selected-line">
          当前对象:<b>{{ symbolName }}</b>
          <InfoTip text="全部策略(含「我的策略」)使用同一股票或指数、同一区间与默认参数,按样本外表现排序。" label="对比说明" />
        </div>
      </section>

      <div v-if="cmpResult" :class="{ 'stale-dim': cmpStale }">
        <div v-if="cmpStale" class="stale-bar">参数已修改,下面是上一次对比的结果。点击「运行对比」更新。</div>
        <section class="panel section-gap">
          <div class="panel-head">
            <div>
              <h2 class="panel-title" style="margin: 0">策略对比 · {{ cmpResult.name }}</h2>
              <p class="panel-sub">
                {{ compareConclusion }}
                <InfoTip text="样本外:把区间切成 3 段,用前面的数据检验策略在后续未见数据上的表现,避免只看一段行情。" />
              </p>
            </div>
            <label class="pro-toggle">
              <input v-model="showPro" type="checkbox" /> 专业指标
              <InfoTip text="夏普比率衡量单位波动获得的收益;盈亏比是总盈利与总亏损之比;稳定性指 3 段检验中有几段盈利。" />
            </label>
          </div>
          <div v-if="cmpResult.results[0]?.metrics.trade_count" class="winner-banner">
            <span class="winner-label mono">本轮冠军</span>
            <b class="winner-name">{{ cmpResult.results[0].name }}</b>
            <span class="winner-ret num" :class="trendClass(cmpResult.results[0].oos.return_pct)">
              {{ fmtSigned(cmpResult.results[0].oos.return_pct) }}%
            </span>
            <span class="winner-sub">样本外收益 · 夏普 {{ cmpResult.results[0].oos.sharpe }}</span>
          </div>
          <div class="table-wrap cmp-table-wrap">
            <table class="data cmp-table">
              <thead>
                <tr>
                  <th scope="col">
                    排名
                    <InfoTip text="按样本外夏普比率排序;夏普越高,代表单位波动获得的收益越高。" />
                  </th>
                  <th scope="col">策略</th>
                  <th scope="col" class="right">
                    样本外收益
                    <InfoTip text="把区间切成 3 段,用前面的数据检验策略在后续未见数据上的表现。" />
                  </th>
                  <th scope="col" class="right">最大回撤</th>
                  <th scope="col" class="right">交易次数</th>
                  <th v-if="showPro" scope="col" class="right">样本外夏普</th>
                  <th v-if="showPro" scope="col" class="right">胜率</th>
                  <th v-if="showPro" scope="col" class="right">盈亏比</th>
                  <th v-if="showPro" scope="col" class="right">稳定性</th>
                  <th scope="col" class="right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in cmpResult.results" :key="r.id">
                  <td class="num rank" :class="{ 'rank-top': r.rank === 1 }">{{ r.rank }}</td>
                  <td class="bold">{{ r.name }}</td>
                  <td class="num right" :class="trendClass(r.oos.return_pct)">
                    <span v-if="r.metrics.trade_count === 0" class="tag tag-muted">无交易</span>
                    <template v-else>{{ fmtSigned(r.oos.return_pct) }}%</template>
                  </td>
                  <td class="num right">{{ r.metrics.trade_count === 0 ? "--" : fmtPct(r.metrics.max_drawdown_pct, false) }}</td>
                  <td class="num right">{{ r.metrics.trade_count }}</td>
                  <td v-if="showPro" class="num right">{{ r.oos.sharpe }}</td>
                  <td v-if="showPro" class="num right">{{ r.metrics.trade_count === 0 ? "--" : r.metrics.win_rate_pct + "%" }}</td>
                  <td v-if="showPro" class="num right">{{ r.metrics.trade_count === 0 ? "--" : (r.metrics.profit_factor ?? "--") }}</td>
                  <td v-if="showPro" class="num right">
                    {{ r.metrics.trade_count === 0 ? "--" : `${r.oos.positive_folds}/${r.oos.folds.length} 段盈利` }}
                  </td>
                  <td class="right">
                    <button class="btn btn-sm" @click="pickStrategy(r)">回测此策略</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="cmp-cards">
            <div v-for="r in cmpResult.results" :key="r.id" class="cmp-card">
              <div class="cmp-card-head">
                <span class="rank" :class="{ 'rank-top': r.rank === 1 }">#{{ r.rank }}</span>
                <b>{{ r.name }}</b>
                <span class="num cmp-card-ret" :class="trendClass(r.oos.return_pct)">
                  {{ r.metrics.trade_count === 0 ? "无交易" : fmtSigned(r.oos.return_pct) + "%" }}
                </span>
              </div>
              <div class="cmp-card-stats">
                <span>最大回撤 {{ r.metrics.trade_count === 0 ? "--" : fmtPct(r.metrics.max_drawdown_pct, false) }}</span>
                <span>交易 {{ r.metrics.trade_count }} 次</span>
                <span v-if="showPro">夏普 {{ r.oos.sharpe }}</span>
                <span v-if="showPro">胜率 {{ r.metrics.trade_count === 0 ? "--" : r.metrics.win_rate_pct + "%" }}</span>
              </div>
              <button class="btn btn-sm" @click="pickStrategy(r)">回测此策略</button>
            </div>
          </div>
        </section>

        <section class="panel section-gap">
          <h2 class="panel-title">累计收益对比</h2>
          <CompareChart :comparison="cmpResult" />
        </section>

        <section class="panel section-gap">
          <button class="disclosure" :class="{ open: showRegime }" :aria-expanded="showRegime"
            @click="showRegime = !showRegime">
            分行情状态表现
            <InfoTip text="把每个交易日按大盘状态分组,统计策略在多头、空头、震荡、高波动行情里的历史表现。" />
            <AppIcon name="chevron-down" :size="14" class="chev" />
          </button>
          <div v-if="showRegime" class="table-wrap section-gap">
            <table class="data">
              <thead>
                <tr>
                  <th scope="col">策略</th>
                  <th v-for="k in regimeKeys" :key="k" scope="col" class="right">{{ cmpResult.regime_labels[k] }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in cmpResult.results" :key="r.id">
                  <td class="bold">{{ r.name }}</td>
                  <td v-for="k in regimeKeys" :key="k" class="right">
                    <template v-if="regimeCell(r, k)">
                      <span class="num" :class="trendClass(regimeCell(r, k).return_pct)">
                        {{ fmtSigned(regimeCell(r, k).return_pct) }}%
                      </span>
                      <span class="regime-meta">{{ regimeCell(r, k).trade_count }} 笔 · 胜率 {{ regimeCell(r, k).win_rate_pct }}%</span>
                    </template>
                    <span v-else class="dim">--</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
      <section v-else class="panel section-gap">
        <div class="empty">
          <div class="title">运行后查看跨策略对比</div>
          <div class="sub">会给出样本外收益、最大回撤、胜率与交易次数,并生成一句结论。「我的策略」也会同场竞技。</div>
        </div>
      </section>
    </div>

    <div v-else class="bt-grid">
      <section ref="configEl" class="panel config-panel">
        <div class="config-head">
          <h2 class="panel-title">策略</h2>
          <button class="btn btn-sm builder-entry" @click="openBuilder">
            <AppIcon name="plus" :size="13" /> 搭建我的策略
          </button>
        </div>
        <div class="strategy-list">
          <div v-for="s in strategies" :key="s.id" class="strategy-card" :class="{ on: selectedId === s.id }"
            role="button" tabindex="0" :aria-pressed="selectedId === s.id"
            @click="selectStrategy(s)" @keydown.enter="selectStrategy(s)">
            <span class="s-head">
              <svg class="s-glyph" viewBox="0 0 24 24" aria-hidden="true">
                <path v-for="(d, i) in glyphPaths(s)" :key="i" :d="d" />
              </svg>
              <span class="s-name">{{ s.name }}</span>
              <span v-if="s.custom" class="tag tag-info custom-tag">自定义</span>
            </span>
            <span v-if="s.fits.length" class="s-fits">
              <span v-for="f in s.fits" :key="f" class="fits-tag">{{ FITS[f] }}</span>
            </span>
            <span class="s-essence">{{ cardEssence(s) }}</span>
            <span v-if="s.custom" class="s-actions">
              <button class="mini-btn" @click.stop="editCustom(s)">编辑</button>
              <button class="mini-btn danger" @click.stop="removeCustom(s)">删除</button>
            </span>
          </div>
        </div>

        <div v-if="selected" class="explainer section-gap">
          <div class="rule-row"><span class="rule-chip buy">买入</span><span>{{ ruleText(selected.buy_rule) }}</span></div>
          <div class="rule-row"><span class="rule-chip sell">卖出</span><span>{{ ruleText(selected.sell_rule) }}</span></div>
          <p class="risk-line"><AppIcon name="warn" :size="13" /> {{ selected.risk }}</p>
          <button v-if="!selected.custom && BUILTIN_RULES[selected.id]" class="save-as-link" @click="saveAsCustom">
            调好参数后「存为我的策略」→
          </button>
        </div>

        <div v-if="selected" class="param-block section-gap">
          <div class="preset-row">
            <button v-for="p in selected.presets" :key="p.name" class="preset-chip" :class="{ on: presetActive(p) }"
              :title="p.hint" :aria-pressed="presetActive(p)" @click="applyPreset(p)">{{ p.name }}</button>
            <span class="preset-hint">{{ activePresetHint }}</span>
          </div>
          <ParamSlider v-for="p in selected.params" :key="p.key" :param="p" v-model="params[p.key]" />
        </div>

        <h2 class="panel-title section-gap">回测设置</h2>
        <div class="field">
          <label>回测对象</label>
          <SymbolSearch placeholder="输入代码或名称" @select="onSymbol" />
          <p class="selected-line">当前:<b>{{ symbolName }}</b></p>
        </div>
        <div class="field">
          <label>回测区间</label>
          <div class="segmented">
            <button v-for="d in [60, 120, 250]" :key="d" class="seg" :class="{ on: days === d }"
              :aria-label="`${d} 个交易日`" @click="days = d">{{ d }} 日</button>
          </div>
        </div>
        <div class="field">
          <label>初始资金</label>
          <div class="capital-chips">
            <button v-for="c in capitalChips" :key="c" class="preset-chip" :class="{ on: capital === c }"
              :aria-pressed="capital === c" :aria-label="`初始资金 ${fmtMoney(c, 0)} 元`"
              @click="capital = c">{{ c / 10000 }}万</button>
          </div>
          <input type="range" class="range" min="10000" max="1000000" step="10000" :value="capital"
            :style="{ background: capitalTrack }" aria-label="初始资金" @input="capital = Number($event.target.value)" />
          <div class="param-scale mono"><span>1万</span><span class="param-value num">¥{{ fmtMoney(capital, 0) }}</span><span>100万</span></div>
        </div>

        <button class="btn btn-primary btn-block" :disabled="!canRun" @click="run">
          <span v-if="running" class="spinner"></span>
          {{ running ? "回测中…" : "运行回测" }}
        </button>
        <p class="assumptions">回测假设:信号次日开盘成交,全仓买卖,计入佣金与印花税。</p>
      </section>

      <section ref="resultsEl" class="result-panel">
        <section class="panel preview-panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title" style="margin: 0">策略实时预览</h2>
              <p class="panel-sub">拖动左侧参数,指标线与买卖点实时更新——先看清策略怎么出手,再运行回测。</p>
            </div>
            <span v-if="previewLoading" class="spinner"></span>
          </div>
          <StrategyPreview v-if="previewData" :data="previewData" :height="320" />
          <div v-else class="preview-empty">
            {{ symbol ? "正在计算指标与信号…" : "选择回测对象后,这里会画出策略的指标线与买卖点。" }}
          </div>
        </section>

        <div v-if="result" :class="{ 'stale-dim': resultStale }" class="section-gap">
          <div v-if="resultStale" class="stale-bar">参数或对象已修改,下面是上一次回测的结果。</div>
          <div v-if="resultMeta" class="result-meta">
            <b>{{ resultMeta.strategy }}</b>
            <span>{{ resultMeta.symbolName }}</span>
            <span>{{ resultMeta.days }} 个交易日</span>
            <span>初始资金 ¥{{ fmtMoney(resultMeta.capital, 0) }}</span>
            <span v-if="resultMeta.paramsText">参数 {{ resultMeta.paramsText }}</span>
          </div>
          <div v-if="!result.markers.length" class="warn-bar">
            <AppIcon name="warn" :size="15" />
            <span>该区间没有成交:买入一手({{ tradeLot }} 股)约需 ¥{{ fmtMoney((result.candles.at(-1)?.close || 0) * tradeLot) }},高于初始资金时无法买入。调高资金或换对象再试。</span>
          </div>
          <div class="result-hero" :class="trendClass(result.metrics.total_return_pct)">
            <div class="hero-main">
              <span class="hero-label">总收益</span>
              <span class="hero-value num">{{ fmtSigned(heroReturn) }}<small>%</small></span>
              <span class="verdict-pill" :class="heroExcess >= 0 ? 'good' : 'bad'">
                {{ heroExcess >= 0 ? "跑赢" : "跑输" }}买入持有 {{ fmtPct(Math.abs(heroExcess), false) }}
              </span>
            </div>
            <div class="hero-sub">
              最终权益 <b class="num">¥{{ fmtMoney(result.metrics.final_equity) }}</b>
              · 初始 <b class="num">¥{{ fmtMoney(result.metrics.initial_capital, 0) }}</b>
              · 同期买入持有 <b class="num" :class="trendClass(result.metrics.benchmark_return_pct)">{{ fmtSigned(result.metrics.benchmark_return_pct) }}%</b>
            </div>
          </div>
          <div class="kpi-grid">
            <div v-for="m in primaryMetrics" :key="m.label" class="kpi">
              <span class="kpi-label">{{ m.label }}</span>
              <span class="kpi-value" :class="m.cls">{{ m.value }}</span>
              <span v-if="m.bar && winLoss.total" class="winloss-bar" :aria-label="`${winLoss.wins} 胜 ${winLoss.losses} 负`">
                <span class="win" :style="{ width: `${(winLoss.wins / winLoss.total) * 100}%` }"></span>
                <span class="loss" :style="{ width: `${(winLoss.losses / winLoss.total) * 100}%` }"></span>
              </span>
              <span class="kpi-sub">{{ m.sub }}</span>
            </div>
          </div>

          <section class="panel section-gap">
            <h2 class="panel-title">策略走势 · {{ resultMeta?.symbolName }}</h2>
            <BacktestChart :result="result" />
          </section>

          <section class="panel section-gap">
            <button class="disclosure" :class="{ open: tradesOpen }" :aria-expanded="tradesOpen"
              @click="tradesOpen = !tradesOpen">
              更多指标与逐笔交易
              <InfoTip text="夏普比率衡量单位波动获得的收益;盈亏比是总盈利与总亏损之比;在场时间指持有标的的交易日占比。" />
              <AppIcon name="chevron-down" :size="14" class="chev" />
            </button>
            <template v-if="tradesOpen">
              <div class="detail-grid section-gap">
                <div v-for="m in detailMetrics" :key="m.label" class="detail-item">
                  <span>{{ m.label }}</span>
                  <b class="num" :class="m.cls">{{ m.value }}</b>
                </div>
              </div>
              <div v-if="result.trades.length" class="section-gap">
                <DataTable :columns="tradeColumns" :rows="tradePageRows" :sort-key="tradeSortKey" :sort-dir="tradeSortDir"
                  :row-key="(t) => result.trades.indexOf(t)" :clickable="false" @sort="tradeToggleSort">
                  <template #cell-time="{ row }"><span class="dim">{{ row.time }}</span></template>
                  <template #cell-side="{ row }">
                    <span :class="row.side === 'BUY' ? 'up' : 'down'" class="bold">{{ row.side === "BUY" ? "买入" : "卖出" }}</span>
                  </template>
                  <template #cell-price="{ row }">{{ fmtMoney(row.price) }}</template>
                  <template #cell-amount="{ row }">{{ fmtMoney(row.amount) }}</template>
                  <template #cell-fee="{ row }"><span class="dim">{{ fmtMoney(row.fee) }}</span></template>
                  <template #cell-pnl="{ row }">
                    <span :class="row.pnl == null ? 'flat' : trendClass(row.pnl)">{{ row.pnl == null ? "--" : fmtSigned(row.pnl) }}</span>
                  </template>
                </DataTable>
                <DataPagination :page="tradePage" :page-size="tradePageSize" :total="tradeTotal" :total-pages="tradeTotalPages"
                  @update:page="setTradePage" @update:page-size="setTradePageSize" />
              </div>
            </template>
          </section>
        </div>
        <div v-else class="panel">
          <div class="empty">
            <div class="title">回测结果会显示在这里</div>
            <div class="sub">选择策略与回测对象,点击「运行回测」后查看资金曲线、买卖点与逐笔交易。</div>
          </div>
        </div>
      </section>
    </div>

    <section v-if="mode === 'single' && (history.length || loadingHistory)" class="panel section-gap">
      <button class="disclosure" :class="{ open: historyOpen }" :aria-expanded="historyOpen"
        @click="historyOpen = !historyOpen">
        最近回测
        <span v-if="loadingHistory" class="spinner"></span>
        <AppIcon name="chevron-down" :size="14" class="chev" />
      </button>
      <div v-if="historyOpen && history.length" class="section-gap">
        <DataTable :columns="historyColumns" :rows="historyPageRows" :sort-key="historySortKey" :sort-dir="historySortDir"
          row-key="id" @sort="historyToggleSort" @select="viewHistory">
          <template #cell-created_at="{ row }">{{ fmtDateTime(row.created_at) }}</template>
          <template #cell-strategy_name="{ row }">
            <span class="bold">{{ row.strategy_name && !row.strategy_name.startsWith("custom_") ? row.strategy_name : strategyName(row.strategy) }}</span>
          </template>
          <template #cell-symbol="{ row }"><span class="symbol-badge">{{ row.symbol }}</span></template>
          <template #cell-return="{ row }">
            <span :class="trendClass(row.metrics?.total_return_pct)">{{ fmtSigned(row.metrics?.total_return_pct ?? 0) }}%</span>
          </template>
        </DataTable>
        <DataPagination :page="historyPage" :page-size="historyPageSize" :total="historyTotal" :total-pages="historyTotalPages"
          :sizes="[8, 20, 50]" @update:page="setHistoryPage" @update:page-size="setHistoryPageSize" />
      </div>
      <p v-else-if="historyOpen" class="dim section-gap">还没有历史回测记录。</p>
    </section>

    <StrategyBuilder :open="builderOpen" :initial="builderInitial" :prefill="builderPrefill" :symbol="symbol"
      @close="builderOpen = false" @saved="onCustomSaved" />
  </div>
</template>

<style scoped>
.bt-grid { display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: var(--space-4); align-items: start; }
.strategy-list { display: grid; gap: 6px; }
.strategy-card {
  text-align: left;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--inset-bg-soft);
  color: var(--text-2);
  cursor: pointer;
  display: grid;
  gap: 3px;
}
.strategy-card:hover { border-color: var(--border-strong); }
.strategy-card:focus-visible { outline: none; box-shadow: var(--ring); }
.strategy-card.on { position: relative; border-color: var(--accent); background: var(--accent-bg); box-shadow: inset 0 0 0 1px var(--accent); }
.strategy-card.on::after { content: ""; position: absolute; right: 12px; top: 12px; width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px var(--accent-bg); }
.s-head { display: flex; align-items: center; gap: 6px; padding-right: 14px; }
.s-name { font-weight: 600; color: var(--text-1); font-size: var(--fs-sm); flex: 1; min-width: 0; }
.s-fits { display: flex; gap: 4px; flex-wrap: wrap; }
.fits-tag {
  padding: 0 8px;
  border-radius: var(--radius-pill);
  background: var(--hover-bg);
  color: var(--text-2);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.04em;
  line-height: 1.7;
  white-space: nowrap;
}
.s-essence { font-size: var(--fs-xs); color: var(--text-2); line-height: 1.55; }
.explainer {
  display: grid;
  gap: 7px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--inset-bg-soft);
}
.rule-row { display: flex; align-items: flex-start; gap: 8px; font-size: var(--fs-sm); color: var(--text-1); line-height: 1.55; }
.rule-chip {
  flex: none;
  padding: 0 9px;
  border-radius: var(--radius-pill);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.8;
}
.rule-chip.buy { background: var(--up-bg); color: var(--up); }
.rule-chip.sell { background: var(--down-bg); color: var(--down); }
.risk-line { display: flex; align-items: flex-start; gap: 6px; margin: 2px 0 0; color: var(--warn); font-size: var(--fs-xs); line-height: 1.55; }
.preset-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.preset-chip {
  padding: 3px 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--panel);
  color: var(--text-2);
  font-size: var(--fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.preset-chip:hover { border-color: var(--text-3); color: var(--text-1); }
.preset-chip.on { background: var(--btn-primary-bg); border-color: transparent; color: var(--btn-primary-fg); }
.preset-hint { font-size: var(--fs-xs); color: var(--text-3); }
.param-value { font-family: var(--font-mono); font-size: var(--fs-sm); font-weight: 700; color: var(--text-1); }
.param-scale { display: flex; justify-content: space-between; gap: 8px; font-size: var(--fs-xs); color: var(--text-3); }
.range {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  margin: 8px 0 2px;
  border-radius: 2px;
  background: var(--inset-bg);
  outline: none;
  cursor: pointer;
}
.range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--panel-solid);
  border: 2px solid var(--accent);
  box-shadow: 0 1px 4px var(--shadow-color);
  cursor: grab;
}
.range::-moz-range-thumb {
  width: 12px; height: 12px;
  border-radius: 50%;
  background: var(--panel-solid);
  border: 2px solid var(--accent);
  box-shadow: 0 1px 4px var(--shadow-color);
  cursor: grab;
}
.range:focus-visible { box-shadow: var(--ring); }
.config-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.config-head .panel-title { margin: 0; }
.builder-entry { display: inline-flex; align-items: center; gap: 4px; flex: none; }
.s-glyph { width: 20px; height: 20px; flex: none; fill: none; stroke: var(--text-3); stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.strategy-card.on .s-glyph { stroke: var(--accent-text); }
.custom-tag { flex: none; font-size: 11px; line-height: 1.6; padding: 0 7px; }
.s-actions { display: flex; gap: 6px; margin-top: 2px; }
.mini-btn {
  border: none; background: none; padding: 0;
  font-size: var(--fs-xs); color: var(--text-3); cursor: pointer;
  text-decoration: underline dotted; text-underline-offset: 3px;
}
.mini-btn:hover { color: var(--accent-text); }
.mini-btn.danger:hover { color: var(--up); }
.save-as-link {
  border: none; background: none; padding: 0; margin-top: 2px;
  font-size: var(--fs-xs); color: var(--accent-text); cursor: pointer; text-align: left;
}
.save-as-link:hover { text-decoration: underline; text-underline-offset: 3px; }
.preview-panel { margin-bottom: var(--space-4); }
.preview-empty {
  padding: 48px 16px;
  text-align: center;
  color: var(--text-3);
  font-size: var(--fs-sm);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
}
.result-hero {
  padding: 18px 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--panel);
  box-shadow: var(--shadow-1);
  margin-bottom: 10px;
}
.hero-main { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.hero-label { font-size: var(--fs-xs); color: var(--text-3); font-weight: 600; letter-spacing: 0.06em; }
.hero-value { font-family: var(--font-display); font-size: 44px; font-weight: 600; letter-spacing: -0.03em; line-height: 1.1; }
.hero-value small { font-size: 22px; margin-left: 2px; }
.result-hero.up .hero-value { color: var(--up); }
.result-hero.down .hero-value { color: var(--down); }
.verdict-pill {
  padding: 2px 12px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-xs);
  font-weight: 700;
  font-family: var(--font-mono);
  letter-spacing: 0.03em;
}
.verdict-pill.good { background: var(--up-bg); color: var(--up); }
.verdict-pill.bad { background: var(--down-bg); color: var(--down); }
.hero-sub { margin-top: 8px; font-size: var(--fs-xs); color: var(--text-2); }
.hero-sub b { color: var(--text-1); }
.winloss-bar { display: flex; height: 5px; border-radius: 3px; overflow: hidden; margin: 6px 0 2px; background: var(--inset-bg); }
.winloss-bar .win { background: var(--up); }
.winloss-bar .loss { background: var(--down); }
.winner-banner {
  display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
  padding: 12px 16px; margin-bottom: 12px;
  border: 1px solid var(--gold-border);
  border-radius: var(--radius);
  background: var(--gold-bg);
}
.winner-label { font-size: var(--fs-xs); color: var(--gold); letter-spacing: 0.08em; }
.winner-name { font-family: var(--font-display); font-size: var(--fs-lg); letter-spacing: -0.02em; }
.winner-ret { font-family: var(--font-display); font-size: var(--fs-xl); font-weight: 600; }
.winner-sub { font-size: var(--fs-xs); color: var(--text-2); }
.capital-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 4px; }
.selected-line { color: var(--text-3); font-size: var(--fs-xs); margin-top: 6px; display: flex; align-items: center; gap: 4px; }
.selected-line b { color: var(--text-1); }
.assumptions { color: var(--text-3); font-size: var(--fs-xs); line-height: 1.5; margin: 10px 0 0; }
.result-panel { scroll-margin-top: 72px; }
.result-meta { display: flex; gap: 12px; flex-wrap: wrap; color: var(--text-2); font-size: var(--fs-xs); margin-bottom: 10px; }
.result-meta b { color: var(--text-1); }
.stale-bar, .warn-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius);
  font-size: var(--fs-xs);
  margin-bottom: 10px;
}
.stale-dim { opacity: 0.55; filter: saturate(0.7); }
.stale-dim .stale-bar { opacity: 1; filter: none; }
.stale-bar { color: var(--warn); background: var(--warn-bg); border: 1px solid var(--gold-border); }
.warn-bar { color: var(--warn); background: var(--warn-bg); border: 1px solid transparent; line-height: 1.5; }
.detail-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.detail-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: var(--fs-xs);
  color: var(--text-3);
}
.detail-item b { color: var(--text-1); }
.cmp-toolbar { display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
.toolbar-field { display: grid; gap: 5px; }
.toolbar-field label { font-size: var(--fs-xs); color: var(--text-2); font-weight: 600; }
.symbol-field { min-width: 260px; flex: 1; }
.cmp-toolbar .selected-line { width: 100%; margin-top: 0; }
.cmp-table .right, .right { text-align: right; }
.cmp-cards { display: none; }
.rank { font-family: var(--font-display); font-size: var(--fs-lg); font-weight: 600; color: var(--text-3); }
.rank-top { color: var(--gold); }
.regime-meta { display: block; font-size: var(--fs-xs); color: var(--text-3); }
.pro-toggle { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-xs); color: var(--text-2); cursor: pointer; flex: none; white-space: nowrap; }
.pro-toggle input {
  appearance: none;
  width: 14px; height: 14px;
  margin: 0;
  border: 1px solid var(--border-strong);
  border-radius: 3px;
  background: var(--inset-bg);
  cursor: pointer;
  position: relative;
}
.pro-toggle input:checked { background: var(--accent); border-color: var(--accent); }
.pro-toggle input:checked::after {
  content: "";
  position: absolute;
  left: 3px; top: 0;
  width: 5px; height: 8px;
  border: solid var(--on-accent);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}
@media (max-width: 1020px) {
  /* minmax(0,1fr):否则 ECharts canvas 的固有宽度会撑开轨道,ResizeObserver 永远等不到收缩 */
  .bt-grid { grid-template-columns: minmax(0, 1fr); }
  .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .cmp-table-wrap { display: none; }
  .cmp-cards { display: grid; gap: 8px; }
  .cmp-card { padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--inset-bg-soft); }
  .cmp-card-head { display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }
  .cmp-card-ret { margin-left: auto; font-weight: 700; }
  .cmp-card-stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 3px 12px; color: var(--text-3); font-size: var(--fs-xs); margin-bottom: 8px; }
  .cmp-card .btn { width: 100%; }
  .symbol-field, .cmp-toolbar { width: 100%; }
  .cmp-toolbar .btn { width: 100%; }
}
</style>