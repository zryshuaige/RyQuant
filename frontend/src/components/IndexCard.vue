<script setup>
import { computed } from "vue";
import AnimatedNumber from "./AnimatedNumber.vue";
import { fmtPct, trendClass } from "../utils/format";

const props = defineProps({ index: { type: Object, required: true } });

const cls = computed(() => trendClass(props.index.change));
const arrow = computed(() => (props.index.change > 0 ? "▲" : props.index.change < 0 ? "▼" : "—"));
</script>

<template>
  <div class="panel hoverable index-card" :class="cls">
    <div class="head">
      <span class="name">{{ index.name }}</span>
      <span class="pct-pill" :class="cls">{{ arrow }} {{ fmtPct(index.change_pct) }}</span>
    </div>
    <AnimatedNumber class="value" :value="index.current" :duration="700" />
    <div class="sub num" :class="cls">
      {{ index.change > 0 ? "+" : "" }}{{ index.change.toFixed(2) }} 较昨收
    </div>
  </div>
</template>

<style scoped>
.index-card { padding: 16px 18px; position: relative; overflow: hidden; }
.index-card::before {
  content: "";
  position: absolute;
  inset: auto -30% -60% auto;
  width: 70%;
  height: 90%;
  border-radius: 50%;
  filter: blur(30px);
  opacity: 0.35;
  background: var(--down);
  pointer-events: none;
}
.index-card.up::before { background: var(--up); }
.index-card.down::before { background: var(--down); }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.name { color: var(--text-2); font-weight: 600; font-size: 13px; }
.value {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.sub { font-size: 12.5px; margin-top: 3px; color: var(--text-3); }
</style>
