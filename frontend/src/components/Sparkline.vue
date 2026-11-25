<script setup>
/** 迷你走势:个股(蓝) vs 同期上证(灰虚线),纯 SVG,不引入图表实例。 */
import { computed } from "vue";

const props = defineProps({
  points: { type: Array, default: () => [] },
  width: { type: Number, default: 104 },
  height: { type: Number, default: 30 },
});

function buildPath(key) {
  const pts = props.points;
  if (!pts.length) return "";
  const values = pts.map((p) => Number(p[key] ?? 0));
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = max - min || 1;
  const innerW = props.width - 2;
  const innerH = props.height - 4;
  return values.map((v, i) => {
    const x = 1 + (pts.length === 1 ? innerW / 2 : (i / (pts.length - 1)) * innerW);
    const y = 2 + innerH - ((v - min) / span) * innerH;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

const stockPath = computed(() => buildPath("stock_pct"));
const benchPath = computed(() => buildPath("bench_pct"));
const aria = computed(() => {
  const last = props.points[props.points.length - 1];
  if (!last) return "暂无走势数据";
  return `加入以来 ${last.stock_pct >= 0 ? "+" : ""}${last.stock_pct}%,同期上证 ${last.bench_pct >= 0 ? "+" : ""}${last.bench_pct}%`;
});
</script>

<template>
  <svg :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`" role="img" :aria-label="aria" class="spark">
    <line v-if="points.length" x1="1" :y1="height - 2" :x2="width - 1" :y2="height - 2" class="baseline" />
    <path v-if="benchPath" :d="benchPath" class="bench" />
    <path v-if="stockPath" :d="stockPath" class="stock" />
  </svg>
</template>

<style scoped>
.spark { display: block; overflow: visible; }
.baseline { stroke: var(--border); stroke-width: 1; }
.bench { fill: none; stroke: var(--text-3); stroke-width: 1.2; stroke-dasharray: 3 2; }
.stock { fill: none; stroke: var(--accent); stroke-width: 1.6; }
</style>