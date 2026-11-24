<script setup>
import { useMarketStore } from "../stores/market";
import { fmtMoney, fmtPct, trendClass } from "../utils/format";

const market = useMarketStore();
// 滚动列表复制两份实现无缝循环
const items = () => (market.indices.length ? [...market.indices, ...market.indices] : []);
</script>

<template>
  <div class="tape" aria-hidden="true">
    <div class="tape-track" v-if="market.indices.length">
      <span v-for="(idx, i) in items()" :key="i" class="tape-item">
        <span class="tape-name">{{ idx.name }}</span>
        <span class="num" :class="trendClass(idx.change)">{{ fmtMoney(idx.current) }}</span>
        <span class="num" :class="trendClass(idx.change)">{{ fmtPct(idx.change_pct) }}</span>
      </span>
    </div>
    <div v-else class="tape-track"><span class="tape-item tape-loading">行情连接中…</span></div>
  </div>
</template>

<style scoped>
.tape {
  overflow: hidden;
  border-bottom: 1px solid var(--border);
  background: var(--header-bg);
  white-space: nowrap;
  /* 边缘渐隐,避免跑马灯条目在viewport边缘被拦腰截断 */
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent);
  mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent);
}
.tape-track {
  display: inline-flex;
  align-items: center;
  padding: 6px 0;
  animation: tape-marquee 30s linear infinite;
}
.tape:hover .tape-track { animation-play-state: paused; }
.tape-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 26px;
  font-size: 12px;
  border-right: 1px solid var(--border);
}
.tape-name { color: var(--text-2); font-weight: 600; }
.tape-loading { color: var(--text-3); border: none; animation: none; }
@keyframes tape-marquee {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
</style>
