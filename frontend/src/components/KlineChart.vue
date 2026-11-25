<script setup>
/** K 线:K 线 + 成交量 + 自选加入日金色标注 + 主题联动。 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { CandlestickChart, LineChart, BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { fetchKline } from "../api";
import { useMarketStore } from "../stores/market";
import { chartColors, theme } from "../utils/chartTheme";
import { fmtMoney, fmtPct, fmtDate, trendClass } from "../utils/format";
import AppIcon from "./AppIcon.vue";

echarts.use([CandlestickChart, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent, CanvasRenderer]);

const props = defineProps({
  symbol: { type: String, required: true },
  name: { type: String, default: "" },
  height: { type: Number, default: 380 },
  limit: { type: Number, default: 90 },
  pollSeconds: { type: Number, default: 15 },
  favorite: { type: Boolean, default: false },
  favoritePending: { type: Boolean, default: false },
  favoriteEnabled: { type: Boolean, default: true },
});
const emit = defineEmits(["toggle-favorite"]);

const el = ref(null);
const range = ref(props.limit);
const loading = ref(false);
const error = ref("");
const lastData = ref(null);
const market = useMarketStore();

const liveQuote = computed(() => {
  const s = market.stocks.find((x) => x.symbol === props.symbol)
    || market.indices.find((x) => x.symbol === props.symbol);
  if (!s) return null;
  return { price: Number(s.price ?? s.current), change: Number(s.change), changePct: Number(s.change_pct), source: s.quote_source };
});
const favDate = computed(() => {
  const f = market.favorites.find((x) => x.stock?.symbol === props.symbol);
  return f ? fmtDate(f.created_at) : null;
});
const quote = computed(() => {
  if (liveQuote.value) return liveQuote.value;
  const d = lastData.value;
  if (!d || d.klines.length < 2) return null;
  const closes = d.klines.map((k) => k[1]);
  const last = closes[closes.length - 1];
  const prev = closes[closes.length - 2];
  const change = last - prev;
  return { price: last, change, changePct: prev ? (change / prev) * 100 : 0, source: d.quote_source };
});

let chart = null;
let resizeObserver = null;
let timer = null;
let disposed = false;
let requestSeq = 0;

function ma(closes, n) {
  return closes.map((_, i) => {
    if (i < n - 1) return null;
    let s = 0;
    for (let j = i - n + 1; j <= i; j++) s += closes[j];
    return +(s / n).toFixed(2);
  });
}

function buildOption(data) {
  const c = chartColors();
  const { timestamps, klines, volumes } = data;
  const closes = klines.map((k) => k[1]);
  const markDate = favDate.value ? timestamps.find((t) => t >= favDate.value) : null;
  const markIndex = markDate ? timestamps.indexOf(markDate) : -1;
  // 加入日早于默认可视窗口时,把缩放起点前移,保证标记一定可见
  const zoomStart = markIndex >= 0 && markIndex < timestamps.length * 0.6
    ? Math.max(0, Math.floor(markIndex / timestamps.length * 100) - 8)
    : 40;

  const option = {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross", crossStyle: { color: c.text } },
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.text2, fontSize: 12 },
      formatter: (params) => {
        const i = params[0].dataIndex;
        const [open, close, low, high] = klines[i];
        const prevClose = i > 0 ? closes[i - 1] : open;
        const pct = prevClose ? ((close - prevClose) / prevClose) * 100 : 0;
        const color = pct > 0 ? c.up : pct < 0 ? c.down : c.text;
        const row = (k, v) => `<div>${k}: <b style="float:right;margin-left:14px">${v}</b></div>`;
        return (
          `<div style="font-weight:700;margin-bottom:4px">${timestamps[i]}</div>` +
          row("开盘", open.toFixed(2)) +
          row("收盘", `<span style="color:${color}">${close.toFixed(2)} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)</span>`) +
          row("最高", high.toFixed(2)) +
          row("最低", low.toFixed(2)) +
          row("成交量", (volumes?.[i] ?? 0).toLocaleString())
        );
      },
    },
    legend: {
      data: ["MA5", "MA10"],
      top: 0,
      right: 8,
      textStyle: { color: c.text2, fontSize: 12 },
      itemWidth: 14, itemHeight: 2,
    },
    grid: [
      { left: 56, right: 18, top: 30, height: "56%" },
      { left: 56, right: 18, top: "74%", height: "14%" },
    ],
    xAxis: [
      { type: "category", data: timestamps, boundaryGap: true, axisLine: { lineStyle: { color: c.axis } }, axisLabel: { color: c.text, fontSize: 12 }, splitLine: { show: false } },
      { type: "category", gridIndex: 1, data: timestamps, axisLabel: { show: false }, axisLine: { show: false } },
    ],
    yAxis: [
      { scale: true, axisLabel: { color: c.text, fontSize: 12 }, splitLine: { lineStyle: { color: c.split } } },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: zoomStart, end: 100 },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: klines,
        itemStyle: { color: c.up, color0: c.down, borderColor: c.up, borderColor0: c.down },
      },
      { name: "MA5", type: "line", data: ma(closes, 5), symbol: "none", lineStyle: { width: 1.3, color: c.brandA }, emphasis: { disabled: true } },
      { name: "MA10", type: "line", data: ma(closes, 10), symbol: "none", lineStyle: { width: 1.3, color: c.brandB }, emphasis: { disabled: true } },
      {
        name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1,
        data: volumes || [],
        itemStyle: {
          color: (p) => (klines[p.dataIndex] && klines[p.dataIndex][1] >= klines[p.dataIndex][0]
            ? c.up + "8c"
            : c.down + "8c"),
        },
        barWidth: "60%",
      },
    ],
  };

  if (markDate) {
    const last = timestamps[timestamps.length - 1];
    option.series[0].markLine = {
      symbol: ["none", "none"], silent: true,
      lineStyle: { color: c.gold, width: 1.5, type: "dashed" },
      label: { formatter: `加入自选 ${favDate.value}`, color: c.gold, fontSize: 12, position: "insideEndTop", rotate: 0 },
      data: [{ xAxis: markDate }],
    };
    option.series[0].markArea = {
      silent: true,
      itemStyle: { color: c.gold + "14" },
      data: [[{ xAxis: markDate }, { xAxis: last }]],
    };
  }
  return option;
}

async function load() {
  if (!props.symbol) return;
  const requested = props.symbol;
  const seq = ++requestSeq;
  loading.value = true;
  error.value = "";
  try {
    const data = await fetchKline({ symbol: requested, limit: range.value });
    if (disposed || props.symbol !== requested || seq !== requestSeq) return;
    lastData.value = data;
    if (!data.klines?.length) error.value = "该区间暂无 K 线数据";
    else render();
  } catch (e) {
    if (!disposed && seq === requestSeq) error.value = e.friendlyMessage || "K 线加载失败";
  } finally {
    if (!disposed && seq === requestSeq) loading.value = false;
  }
}

function render() {
  if (!lastData.value) return;
  if (!chart) {
    chart = echarts.init(el.value);
    resizeObserver = new ResizeObserver(() => chart && chart.resize());
    resizeObserver.observe(el.value);
  }
  chart.setOption(buildOption(lastData.value), { notMerge: true });
}

function onVisibility() {
  if (!document.hidden) load();
}

function setRange(r) {
  if (range.value === r) return;
  range.value = r;
  load();
}

watch(() => props.symbol, load);
watch(theme, render);
watch(favDate, render);

onMounted(() => {
  load();
  timer = setInterval(() => { if (!document.hidden) load(); }, Math.max(props.pollSeconds, 5) * 1000);
  document.addEventListener("visibilitychange", onVisibility);
});

onBeforeUnmount(() => {
  disposed = true;
  if (timer) clearInterval(timer);
  if (resizeObserver) resizeObserver.disconnect();
  if (chart) { chart.dispose(); chart = null; }
  document.removeEventListener("visibilitychange", onVisibility);
});
</script>

<template>
  <div class="kline-wrap" :data-fav-date="favDate || ''">
    <div class="kline-head">
      <div class="kline-title">
        <span class="name">{{ name || symbol }}</span>
        <span class="symbol-badge">{{ symbol }}</span>
        <span v-if="quote && quote.source === 'sim'" class="tag tag-muted">模拟</span>
        <template v-if="quote">
          <span class="quote-price num" :class="trendClass(quote.change)">{{ fmtMoney(quote.price) }}</span>
          <span class="pct-pill" :class="trendClass(quote.change)">{{ fmtPct(quote.changePct) }}</span>
        </template>
        <span v-if="loading" class="spinner"></span>
      </div>
      <div class="kline-actions">
      <div class="segmented" role="group" aria-label="K 线区间">
        <button v-for="r in [30, 60, 90, 180]" :key="r" class="seg" :class="{ on: range === r }"
          :aria-pressed="range === r" @click="setRange(r)">{{ r }}日</button>
      </div>
      <button v-if="favoriteEnabled" class="btn btn-sm" :class="{ 'fav-on': favorite }" :disabled="favoritePending"
        :aria-pressed="favorite"
        :aria-label="favorite ? `移除自选 ${name || symbol}` : `加入自选 ${name || symbol}`"
        @click="emit('toggle-favorite')">
        <span v-if="favoritePending" class="spinner"></span>
        <AppIcon v-else :name="favorite ? 'star-filled' : 'star'" :size="13" />
        {{ favorite ? "已自选" : "加入自选" }}
      </button>
      </div>
    </div>
    <div v-if="error" class="kline-error" role="alert">
      <span>{{ error }}</span>
      <button class="btn btn-sm" @click="load">重试</button>
    </div>
    <div ref="el" class="chart" :style="{ height: `${height}px` }" role="img"
      :aria-label="`${name || symbol} K 线图${favDate ? `,加入自选日期 ${favDate}` : ''}`"></div>
  </div>
</template>

<style scoped>
.kline-wrap { position: relative; }
.chart { width: 100%; }
.kline-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.kline-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kline-title { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.name { font-family: var(--font-display); font-size: var(--fs-xl); font-weight: 600; letter-spacing: -0.02em; }
.quote-price { font-family: var(--font-display); font-size: 24px; font-weight: 600; letter-spacing: -0.02em; }
.fav-on { color: var(--gold); border-color: var(--gold-border); background: var(--gold-bg); }
.kline-error {
  position: absolute;
  inset: 40px 0 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-2);
  background: var(--panel);
  border-radius: var(--radius);
  font-size: var(--fs-sm);
}
</style>