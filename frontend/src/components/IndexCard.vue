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
      <span class="name">
        {{ index.name }}
        <span class="tag src-tag" :class="index.quote_source === 'real' ? 'tag-ok' : 'tag-muted'">
          {{ index.quote_source === "real" ? "真实" : "模拟" }}
        </span>
      </span>
      <span class="pct-pill" :class="cls">{{ arrow }} {{ fmtPct(index.change_pct) }}</span>
    </div>
    <AnimatedNumber class="value" :value="index.current" :duration="700" />
    <div class="sub num" :class="cls">
      {{ index.change > 0 ? "+" : "" }}{{ index.change.toFixed(2) }} 较昨收
    </div>
  </div>
</template>

<style scoped>
.index-card { padding: var(--space-4) 18px; position: relative; overflow: hidden; }
/* token 化微光:整面淡染替代重blur光斑,浅色主题同样干净 */
.index-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: var(--down-bg);
  opacity: 0.55;
  pointer-events: none;
}
.index-card.up::before { background: var(--up-bg); }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2); position: relative; }
.name { color: var(--text-2); font-weight: 600; font-size: 13px; }
.src-tag { font-size: 10px; padding: 1px 6px; margin-left: 6px; vertical-align: 1px; }
.value {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.sub { font-size: 12px; margin-top: 3px; color: var(--text-3); position: relative; }
</style>
