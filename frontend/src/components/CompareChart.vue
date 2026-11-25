<script setup>
/** 策略对比图:各策略累计收益率(%)叠加曲线,主题联动重绘(按需注册 ECharts 模块)。 */
import { ref, watch, onMounted, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { chartColors, theme } from "../utils/chartTheme";

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);

const props = defineProps({
  comparison: { type: Object, required: true }, // compare 端点结果:results[].curve[{date,pct}]
  height: { type: Number, default: 320 },
});

const el = ref(null);
let chart = null;
let resizeObserver = null;

function buildOption(cmp) {
  const c = chartColors();
  const results = cmp.results || [];
  const dates = (results[0]?.curve || []).map((p) => p.date);
  const palette = c.series;
  return {
    animationDuration: 0,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.text2, fontSize: 12 },
      valueFormatter: (v) => `${v >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`,
    },
    legend: {
      data: results.map((r) => r.name),
      top: 0,
      textStyle: { color: c.text2, fontSize: 12 },
      itemWidth: 14, itemHeight: 2,
    },
    grid: { left: 56, right: 24, top: 30, bottom: 46 },
    xAxis: {
      type: "category", data: dates,
      axisLine: { lineStyle: { color: c.axis } },
      axisLabel: { color: c.text, fontSize: 12 },
      splitLine: { show: false },
    },
    yAxis: {
      scale: true,
      axisLabel: { color: c.text, fontSize: 12, formatter: (v) => `${v.toFixed(0)}%` },
      splitLine: { lineStyle: { color: c.split } },
    },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
      {
        type: "slider", bottom: 2, height: 16, borderColor: c.axis,
        backgroundColor: c.split, fillerColor: c.brandA + "26",
        handleStyle: { color: c.brandA }, textStyle: { color: c.text, fontSize: 12 },
      },
    ],
    series: results.map((r, i) => ({
      name: r.name, type: "line", symbol: "none",
      data: r.curve.map((p) => p.pct),
      lineStyle: { width: i === 0 ? 2 : 1.5, color: palette[i % palette.length] },
      emphasis: { focus: "series" },
    })),
  };
}

function render() {
  if (!props.comparison?.results?.length) return;
  if (!chart) {
    chart = echarts.init(el.value);
    resizeObserver = new ResizeObserver(() => chart && chart.resize());
    resizeObserver.observe(el.value);
  }
  chart.setOption(buildOption(props.comparison), { notMerge: true });
}

watch(() => props.comparison, render, { flush: "post" });
watch(theme, render);
onMounted(render);
onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect();
  if (chart) { chart.dispose(); chart = null; }
});
</script>

<template>
  <div ref="el" class="cmp-chart" :style="{ height: `${height}px` }"></div>
</template>

<style scoped>
.cmp-chart { width: 100%; }
</style>