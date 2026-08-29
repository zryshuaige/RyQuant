<script setup>
/** 回测结果图:上层 K 线(涨跌幅)+ 买卖点,下层资金曲线 vs 基准(含累计收益率%),联动缩放,主题联动重绘 */
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { CandlestickChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkPointComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { chartColors, theme } from "../utils/chartTheme";

echarts.use([CandlestickChart, LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkPointComponent, CanvasRenderer]);

const props = defineProps({
  result: { type: Object, required: true }, // BacktestRun 详情:candles / markers / equity_curve / metrics
  height: { type: Number, default: 460 },
});

const el = ref(null);
let chart = null;
let resizeObserver = null;

function buildOption(run) {
  const c = chartColors();
  const candles = run.candles || [];
  const curve = run.equity_curve || [];
  const markers = run.markers || [];
  const dates = candles.map((c) => c.time);
  const initial = run.metrics?.initial_capital || curve[0]?.equity || 1;
  const closes = candles.map((x) => x.close);

  const pctOf = (v) => `${v >= 0 ? "+" : ""}${((v / initial - 1) * 100).toFixed(2)}%`;
  const colorOf = (v) => (v > initial ? c.up : v < initial ? c.down : c.text);

  const buyPoints = markers
    .filter((m) => m.side === "BUY")
    .map((m) => ({
      value: [m.index, m.price],
      symbol: "triangle",
      symbolSize: 13,
      itemStyle: { color: c.up, shadowBlur: 10, shadowColor: c.up },
    }));
  const sellPoints = markers
    .filter((m) => m.side === "SELL")
    .map((m) => ({
      value: [m.index, m.price],
      symbol: "triangle",
      symbolSize: 13,
      symbolRotate: 180,
      itemStyle: { color: c.down, shadowBlur: 10, shadowColor: c.down },
    }));

  return {
    animationDuration: 700,
    backgroundColor: "transparent",
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    tooltip: {
      trigger: "axis",
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.text2, fontSize: 12 },
      formatter: (params) => {
        const i = params[0].dataIndex;
        const head = `<div style="font-weight:700;margin-bottom:4px">${dates[i]}</div>`;
        const candle = candles[i];
        if (!candle) return head;
        const prevClose = i > 0 ? closes[i - 1] : candle.open;
        const pct = prevClose ? ((candle.close - prevClose) / prevClose) * 100 : 0;
        const pctColor = pct > 0 ? c.up : pct < 0 ? c.down : c.text;
        const row = (k, v) => `<div>${k}: <b style="float:right;margin-left:14px">${v}</b></div>`;
        let html =
          head +
          row("收盘", `<span style="color:${pctColor}">${candle.close.toFixed(2)} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)</span>`) +
          row("开盘 / 最高", `${candle.open.toFixed(2)} / ${candle.high.toFixed(2)}`) +
          row("最低", candle.low.toFixed(2));
        const equity = curve[i];
        if (equity) {
          html += `<div style="margin-top:4px;border-top:1px solid ${c.tooltipBorder};padding-top:4px"></div>`;
          html += row("资金曲线", `<span style="color:${colorOf(equity.equity)}">${equity.equity.toLocaleString()} (${pctOf(equity.equity)})</span>`);
          html += row("买入持有", `${equity.benchmark.toLocaleString()} (${pctOf(equity.benchmark)})`);
        }
        return html;
      },
    },
    legend: {
      data: ["资金曲线", "买入持有基准"],
      top: 0,
      textStyle: { color: c.text2, fontSize: 11 },
      itemWidth: 14, itemHeight: 2,
    },
    grid: [
      { left: 62, right: 24, top: 30, height: "42%" },
      { left: 62, right: 24, top: "62%", height: "24%" },
    ],
    xAxis: [
      { type: "category", data: dates, axisLine: { lineStyle: { color: c.axis } }, axisLabel: { color: c.text, fontSize: 10 }, splitLine: { show: false } },
      { type: "category", gridIndex: 1, data: dates, axisLabel: { color: c.text, fontSize: 10 }, axisLine: { show: false }, splitLine: { show: false } },
    ],
    yAxis: [
      { scale: true, axisLabel: { color: c.text, fontSize: 10 }, splitLine: { lineStyle: { color: c.split } } },
      {
        gridIndex: 1, scale: true,
        axisLabel: {
          color: c.text, fontSize: 10,
          formatter: (v) => `${((v / initial - 1) * 100).toFixed(0)}%`, // 纵轴以收益率百分比呈现
        },
        splitLine: { lineStyle: { color: c.split } },
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: "slider", xAxisIndex: [0, 1], bottom: 2, height: 16, borderColor: c.axis, backgroundColor: "rgba(124,144,196,0.08)", fillerColor: "rgba(34,211,238,0.15)", handleStyle: { color: c.brandA }, textStyle: { color: c.text, fontSize: 10 } },
    ],
    series: [
      {
        name: "K线", type: "candlestick",
        data: candles.map((x) => [x.open, x.close, x.low, x.high]),
        itemStyle: { color: c.up, color0: c.down, borderColor: c.up, borderColor0: c.down },
      },
      { name: "买入信号", type: "scatter", data: buyPoints, z: 10, tooltip: { show: false } },
      { name: "卖出信号", type: "scatter", data: sellPoints, z: 10, tooltip: { show: false } },
      {
        name: "资金曲线", type: "line", xAxisIndex: 1, yAxisIndex: 1, symbol: "none",
        data: curve.map((p) => p.equity),
        lineStyle: { width: 2.2, color: c.brandA, shadowBlur: 12, shadowColor: c.brandA },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: c.brandA + "4d" },
            { offset: 1, color: c.brandA + "05" },
          ]),
        },
      },
      {
        name: "买入持有基准", type: "line", xAxisIndex: 1, yAxisIndex: 1, symbol: "none",
        data: curve.map((p) => p.benchmark),
        lineStyle: { width: 1.4, color: c.brandB, type: "dashed" },
      },
    ],
  };
}

function render() {
  if (!props.result) return;
  if (!chart) {
    chart = echarts.init(el.value);
    resizeObserver = new ResizeObserver(() => chart && chart.resize());
    resizeObserver.observe(el.value);
  }
  chart.setOption(buildOption(props.result), { notMerge: true });
}

watch(() => props.result, render, { flush: "post" });
watch(theme, render);
onMounted(render);
onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect();
  if (chart) { chart.dispose(); chart = null; }
});
</script>

<template>
  <div ref="el" class="bt-chart" :style="{ height: `${height}px` }"></div>
</template>

<style scoped>
.bt-chart { width: 100%; }
</style>
