<script setup>
/** 指数卡片:点击查看 K 线。 */
import { computed } from "vue";
import { fmtMoney, fmtPct, trendClass } from "../utils/format";

const props = defineProps({ index: { type: Object, required: true } });
const emit = defineEmits(["select"]);
const cls = computed(() => trendClass(props.index.change));
</script>

<template>
  <button class="panel index-card" :class="['dir-' + cls, { clickable: index.symbol }]" :disabled="!index.symbol"
    :aria-label="`${index.name} ${fmtMoney(index.current)} ${fmtPct(index.change_pct)}`"
    @click="emit('select', index)">
    <span class="head">
      <span class="name">{{ index.name }}</span>
      <span class="pct-pill" :class="cls">{{ fmtPct(index.change_pct) }}</span>
    </span>
    <span class="value num">{{ fmtMoney(index.current) }}</span>
  </button>
</template>

<style scoped>
.index-card {
  position: relative;
  display: block;
  width: 100%;
  padding: 16px 18px 16px 20px;
  text-align: left;
  color: var(--text-1);
  cursor: default;
  overflow: hidden;
}
.index-card::before {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--flat);
}
.index-card.dir-up::before { background: var(--up); }
.index-card.dir-down::before { background: var(--down); }
.index-card.clickable { cursor: pointer; }
.index-card.clickable:hover { border-color: var(--border-strong); background: var(--panel-hover); box-shadow: var(--shadow-2); }
.head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
.name { color: var(--text-2); font-weight: 600; font-size: var(--fs-sm); }
.value { display: block; font-family: var(--font-display); font-size: var(--fs-3xl); font-weight: 600; line-height: 1.2; letter-spacing: -0.02em; }
.index-card:disabled { cursor: default; }
</style>