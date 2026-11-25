<script setup>
/** 策略实时预览:K 线 + 指标叠加线/副图 + 买卖信号三角(纯展示,随参数实时重绘) */
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { CandlestickChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, MarkLineComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { chartColors, theme } from "../utils/chartTheme";

echarts.use([CandlestickChart, LineChart, ScatterChart, GridComponent, TooltipComponent,
  LegendComponent, DataZoomComponent, MarkLineComponent, CanvasRenderer]);

const props = defineProps({
  data: { type: Object, default: null }, // {candles, preview:{overlays, subpanel, signals}}
  height: { type: Number, default: 300 },
});

const el = ref(null);
let chart = null;
let resizeObserver = null;

function buildOption(payload) {
  const c = chartColors();
  const candles = payload?.candles || [];
  const preview = payload?.preview || {};
  const overlays = preview.overlays || [];
  const subpanel = preview.subpanel || null;
  const signals = preview.signals || [];
  const dates = candles.map((x) => x.time);
  const closes = candles.map((x) => x.close);

  const buyPoints = signals.filter((s) => s.side === "BUY").map((s) => ({
    value: [s.index, closes[s.index]], symbol: "triangle", symbolSize: 10, itemStyle: { color: c.up },
  }));
  const sellPoints = signals.filter((s) => s.side === "SELL").map((s) => ({
    value: [s.index, closes[s.index]], symbol: "triangle", symbolSize: 12, symbolRotate: 180,
    itemStyle: { color: c.down },
  }));

  const hasPanel = Boolean(subpanel && subpanel.series?.length);
  const grids = hasPanel
    ? [{ left: 56, right: 18, top: 28, height: "46%" }, { left: 56, right: 18, top: "66%", height: "22%" }]
    : [{ left: 56, right: 18, top: 28, height: "72%" }];
  const xAxes = [
    { type: "category", data: dates, axisLine: { lineStyle: { color: c.axis } },
      axisLabel: { color: c.text, fontSize: 12 }, splitLine: { show: false } },
  ];
  const yAxes = [
    { scale: true, axisLabel: { color: c.text, fontSize: 12 }, splitLine: { lineStyle: { color: c.split } } },
  ];
  if (hasPanel) {
    xAxes.push({ type: "category", gridIndex: 1, data: dates, axisLabel: { show: false },
      axisLine: { show: false }, splitLine: { show: false } });
    yAxes.push({ gridIndex: 1, scale: true, axisLabel: { color: c.text, fontSize: 12 },
      splitLine: { lineStyle: { color: c.split } } });
  }

  const legendData = overlays.map((o) => o.label);
  const series = [
    {
      name: "K线", type: "candlestick",
      data: candles.map((x) => [x.open, x.close, x.low, x.high]),
      itemStyle: { color: c.up, color0: c.down, borderColor: c.up, borderColor0: c.down },
    },
    ...overlays.map((o, i) => ({
      name: o.label, type: "line", symbol: "none", data: o.data,
      lineStyle: { width: 1.4, color: c.series[i % c.series.length] },
      itemStyle: { color: c.series[i % c.series.length] },
    })),
    { name: "买入信号", type: "scatter", data: buyPoints, z: 10, tooltip: { show: false } },
    { name: "卖出信号", type: "scatter", data: sellPoints, z: 10, tooltip: { show: false } },
  ];

  if (hasPanel) {
    subpanel.series.forEach((s, i) => {
      legendData.push(s.label);
      series.push({
        name: s.label, type: "line", xAxisIndex: 1, yAxisIndex: 1, symbol: "none", data: s.data,
        lineStyle: { width: 1.4, color: c.series[i % c.series.length] },
        itemStyle: { color: c.series[i % c.series.length] },
        markLine: i === 0 ? {
          silent: true, symbol: "none",
          lineStyle: { color: c.gold, type: "dashed", width: 1 },
          label: { color: c.text, fontSize: 12, formatter: "{b}" },
          data: (subpanel.levels || []).map((lv) => ({ yAxis: lv.value, name: lv.label })),
        } : undefined,
      });
    });
  }

  return {
    animationDuration: 260,
    animationDurationUpdate: 200,
    backgroundColor: "transparent",
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    tooltip: {
      trigger: "axis",
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.text2, fontSize: 12 },
      formatter: (params) => {
        const i = params[0].dataIndex;
        const candle = candles[i];
        if (!candle) return dates[i] || "";
        const prev = i > 0 ? closes[i - 1] : candle.open;
        const pct = prev ? ((candle.close - prev) / prev) * 100 : 0;
        const color = pct > 0 ? c.up : pct < 0 ? c.down : c.text;
        const row = (k, v) => `<div>${k}: <b style="float:right;margin-left:14px">${v}</b></div>`;
        let html = `<div style="font-weight:700;margin-bottom:4px">${dates[i]}</div>`;
        html += row("收盘", `<span style="color:${color}">${candle.close.toFixed(2)} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)</span>`);
        for (const o of overlays) {
          const v = o.data[i];
          if (v != null) html += row(o.label, v.toFixed(2));
        }
        if (hasPanel) {
          for (const s of subpanel.series) {
            const v = s.data[i];
            if (v != null) html += row(s.label, v.toFixed(2));
          }
        }
        return html;
      },
    },
    legend: {
      data: legendData, top: 0,
      textStyle: { color: c.text2, fontSize: 12 },
      itemWidth: 14, itemHeight: 2,
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [{ type: "inside", xAxisIndex: hasPanel ? [0, 1] : [0], start: 0, end: 100 }],
    series,
  };
}

function render() {
  if (!props.data || !el.value) return;
  if (!chart) {
    chart = echarts.init(el.value);
    resizeObserver = new ResizeObserver(() => chart && chart.resize());
    resizeObserver.observe(el.value);
  }
  chart.setOption(buildOption(props.data), { notMerge: true });
}

watch(() => props.data, render, { flush: "post" });
watch(theme, render);
onMounted(render);
onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect();
  if (chart) { chart.dispose(); chart = null; }
});
</script>

<template>
  <div ref="el" class="strategy-preview" :style="{ height: `${height}px` }"></div>
</template>

<style scoped>
.strategy-preview { width: 100%; }
</style>