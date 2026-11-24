<script setup>
/** K 线图:头部现价/涨跌幅 + tooltip 涨跌幅 + 成交量 + 主题联动重绘 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { CandlestickChart, LineChart, BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { fetchKline } from "../api";
import { useMarketStore } from "../stores/market";
import { chartColors, theme } from "../utils/chartTheme";
import { fmtMoney, fmtPct, fmtDate, trendClass } from "../utils/format";

echarts.use([CandlestickChart, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent, CanvasRenderer]);

const props = defineProps({
  symbol: { type: String, required: true },
  name: { type: String, default: "" },
  height: { type: Number, default: 380 },
  limit: { type: Number, default: 90 },
  pollSeconds: { type: Number, default: 15 },
});

const el = ref(null);
const loading = ref(false);
const error = ref("");
const lastData = ref(null); // 缓存数据,主题切换时重绘
const market = useMarketStore();
// 头部口径与行情卡片统一:优先 store 实时报价(change_pct 基于昨收),无则回退 K 线推导
const liveQuote = computed(() => {
  const s = market.stocks.find((x) => x.symbol === props.symbol)
    || market.indices.find((x) => x.symbol === props.symbol);
  if (!s) return null;
  return { price: Number(s.price ?? s.current), change: Number(s.change), changePct: Number(s.change_pct), source: s.quote_source };
});
// 自选加入日期:K 线金色虚线 + 区间底色醒目标注
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

  const option = {
    animationDuration: 600,
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
      textStyle: { color: c.text2, fontSize: 11 },
      itemWidth: 14, itemHeight: 2,
    },
    grid: [
      { left: 54, right: 20, top: 28, height: "56%" },
      { left: 54, right: 20, top: "74%", height: "14%" },
    ],
    xAxis: [
      { type: "category", data: timestamps, boundaryGap: true, axisLine: { lineStyle: { color: c.axis } }, axisLabel: { color: c.text, fontSize: 10 }, splitLine: { show: false } },
      { type: "category", gridIndex: 1, data: timestamps, axisLabel: { show: false }, axisLine: { show: false } },
    ],
    yAxis: [
      { scale: true, axisLabel: { color: c.text, fontSize: 10 }, splitLine: { lineStyle: { color: c.split } } },
      { gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 40, end: 100 },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: klines,
        itemStyle: { color: c.up, color0: c.down, borderColor: c.up, borderColor0: c.down },
      },
      { name: "MA5", type: "line", data: ma(closes, 5), symbol: "none", lineStyle: { width: 1.4, color: c.brandA }, emphasis: { disabled: true } },
      { name: "MA10", type: "line", data: ma(closes, 10), symbol: "none", lineStyle: { width: 1.4, color: c.brandB }, emphasis: { disabled: true } },
      {
        name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1,
        data: volumes || [],
        itemStyle: {
          // 量柱颜色读主题 token(浅色主题不再残留深色 rgba)
          color: (p) => (klines[p.dataIndex] && klines[p.dataIndex][1] >= klines[p.dataIndex][0]
            ? c.up + "8c"
            : c.down + "8c"),
          borderRadius: 1,
        },
        barWidth: "60%",
      },
    ],
  };
  // 自选加入日期标注:金色虚线 markLine + 加入后区间底色 markArea
  // 加入日若为周末/节假日或早于可视窗口,吸附到其后首个交易日,保证标注始终可见
  const markDate = favDate.value ? timestamps.find((t) => t >= favDate.value) : null;
  if (markDate) {
    const last = timestamps[timestamps.length - 1];
    option.series[0].markLine = {
      symbol: ["none", "none"], silent: true,
      lineStyle: { color: c.gold, width: 2, type: "dashed" },
      label: { formatter: `加入自选 ${favDate.value}`, color: c.gold, fontSize: 11, position: "insideEndTop", rotate: 0 },
      data: [{ xAxis: markDate }],
    };
    option.series[0].markArea = {
      silent: true,
      itemStyle: { color: c.gold + "1f" },
      data: [[{ xAxis: markDate }, { xAxis: last }]],
    };
  }
  return option;
}

async function load() {
  if (!props.symbol) return;
  const requested = props.symbol;
  loading.value = true;
  error.value = "";
  try {
    const data = await fetchKline({ symbol: requested, limit: props.limit });
    if (disposed || props.symbol !== requested) return;  // 丢弃过期响应,防竞态覆盖
    lastData.value = data;
    render();
  } catch (e) {
    if (!disposed) error.value = e.friendlyMessage || "K 线加载失败";
  } finally {
    if (!disposed) loading.value = false;
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

watch(() => props.symbol, load);
watch(theme, render); // 主题切换重绘
watch(favDate, render); // 自选加载晚于首绘时补画加入日期标注

onMounted(() => {
  load();
  timer = setInterval(() => {
    if (!document.hidden) load();
  }, Math.max(props.pollSeconds, 5) * 1000);
});

onBeforeUnmount(() => {
  disposed = true;
  if (timer) clearInterval(timer);
  if (resizeObserver) resizeObserver.disconnect();
  if (chart) { chart.dispose(); chart = null; }
});
</script>

<template>
  <div class="kline-wrap">
    <div class="kline-head">
      <h3 class="panel-title" style="margin: 0">
        <span class="kline-title">
          {{ name || symbol }}
          <span class="symbol-badge">{{ symbol }}</span>
          <span v-if="quote?.source" class="tag src-tag" :class="quote.source === 'real' ? 'tag-ok' : 'tag-muted'">
            {{ quote.source === "real" ? "真实" : "模拟" }}
          </span>
          <span v-if="favDate" class="tag tag-gold fav-tag">自选于 {{ favDate }}</span>
          <template v-if="quote">
            <span class="quote-price num" :class="trendClass(quote.change)">{{ fmtMoney(quote.price) }}</span>
            <span class="pct-pill" :class="trendClass(quote.change)">{{ fmtPct(quote.changePct) }}</span>
          </template>
        </span>
        <span class="hint">
          <span v-if="loading" class="spinner"></span>
          {{ quote?.source === "real" ? "实时行情 · 腾讯" : "模拟行情" }}
        </span>
      </h3>
    </div>
    <div v-if="error" class="kline-error">{{ error }}</div>
    <div ref="el" class="chart" :style="{ height: `${height}px` }"></div>
  </div>
</template>

<style scoped>
.kline-wrap { position: relative; }
.chart { width: 100%; }
.kline-title { display: inline-flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.src-tag { font-size: 10px; padding: 1px 6px; }
.fav-tag { font-size: 10px; padding: 1px 8px; }
.quote-price { font-size: 19px; font-weight: 800; }
.kline-error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  background: var(--inset-bg);
  border-radius: var(--radius);
  font-size: 13px;
}
</style>
