<script setup>
/** 市场脉冲面板:规则化 regime 判定 + 广度 + 板块热度 + 证据链(数据由父级注入,60s 刷新)。 */
import { computed } from "vue";
import { fmtSigned, trendClass } from "../utils/format";
import AnimatedNumber from "./AnimatedNumber.vue";

const props = defineProps({
  pulse: { type: Object, default: null },
  compact: { type: Boolean, default: false },
});

const REGIME_TAG = { bull: "tag-bad", bear: "tag-ok", range: "tag-info", high_vol: "tag-warn" };
const regimeTag = computed(() => REGIME_TAG[props.pulse?.regime] || "tag-muted");
const meterLeft = computed(() => `${((props.pulse?.score ?? 0) + 100) / 2}%`);
const maxHeat = computed(() =>
  Math.max(1, ...(props.pulse?.sectors || []).map((s) => Math.abs(s.change_pct)))
);
function heatWidth(pct) {
  return `${Math.min(Math.abs(pct) / maxHeat.value * 100, 100)}%`;
}
</script>

<template>
  <!-- 紧凑模式:匿名首页 hero 右半 -->
  <div v-if="compact" class="pulse-compact">
    <template v-if="pulse">
      <span class="tag" :class="regimeTag">{{ pulse.label }}</span>
      <span class="num pulse-score" :class="trendClass(pulse.score)">
        <AnimatedNumber :value="pulse.score" />
      </span>
      <span class="pulse-breadth">
        涨 {{ pulse.breadth.advance }} / 跌 {{ pulse.breadth.decline }} ·
        均幅 <b class="num" :class="trendClass(pulse.breadth.avg_change_pct)">{{ fmtSigned(pulse.breadth.avg_change_pct) }}%</b>
      </span>
    </template>
    <span v-else class="pulse-breadth">市场脉冲加载中…</span>
  </div>

  <!-- 完整面板 -->
  <div v-else class="panel pulse-panel">
    <h3 class="panel-title">
      市场脉冲
      <span class="hint">规则化推断 · 离线可用</span>
      <span v-if="pulse" class="tag pulse-src" :class="pulse.quote_source === 'real' ? 'tag-ok' : 'tag-muted'">
        {{ pulse.quote_source === "real" ? "真实行情" : "模拟行情" }}
      </span>
    </h3>

    <template v-if="pulse">
      <div class="pulse-head">
        <span class="tag pulse-regime" :class="regimeTag">{{ pulse.label }}</span>
        <span class="num pulse-score" :class="trendClass(pulse.score)">
          <AnimatedNumber :value="pulse.score" />
        </span>
        <div class="meter" role="img" :aria-label="`市场评分 ${pulse.score}`">
          <span class="meter-mark" :style="{ left: meterLeft }"></span>
        </div>
        <span class="pulse-breadth">
          涨 <b class="num up">{{ pulse.breadth.advance }}</b> /
          跌 <b class="num down">{{ pulse.breadth.decline }}</b> /
          平 {{ pulse.breadth.flat }}
          <template v-if="pulse.breadth.pct_above_ma20 != null">
            · 站上MA20 <b class="num">{{ pulse.breadth.pct_above_ma20 }}%</b>
          </template>
        </span>
      </div>

      <div class="pulse-body">
        <div class="pulse-sectors">
          <div v-for="s in pulse.sectors" :key="s.name" class="sector-row">
            <span class="sector-name">{{ s.name }}</span>
            <span class="sector-bar">
              <span class="sector-fill" :class="trendClass(s.change_pct)" :style="{ width: heatWidth(s.change_pct) }"></span>
            </span>
            <span class="num sector-pct" :class="trendClass(s.change_pct)">{{ fmtSigned(s.change_pct) }}%</span>
          </div>
        </div>
        <ul class="pulse-evidence">
          <li v-for="(e, i) in pulse.evidence" :key="i">{{ e }}</li>
        </ul>
      </div>

      <div v-if="pulse.advice?.length" class="pulse-advice">
        <span class="advice-title">当前状态适用策略 <span class="hint">分状态历史表现 + 样本外验证</span></span>
        <div v-for="(a, i) in pulse.advice" :key="a.id" class="advice-row">
          <span class="advice-rank num" :class="{ 'rank-top': i === 0 }">{{ i + 1 }}</span>
          <span class="advice-name">{{ a.name }}</span>
          <span class="num advice-ret" :class="trendClass(a.regime_return_pct ?? a.oos_return_pct)">
            {{ fmtSigned(a.regime_return_pct ?? a.oos_return_pct) }}%
          </span>
          <span class="advice-reason">{{ a.reason }}</span>
        </div>
      </div>
    </template>
    <div v-else class="skeleton" style="height: 120px"></div>
  </div>
</template>

<style scoped>
.pulse-compact {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--inset-bg);
  min-width: 260px;
}
.pulse-panel .panel-title .hint { margin-left: 8px; }
.pulse-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.pulse-regime { font-size: 13px; padding: 4px 12px; }
.pulse-score { font-size: 24px; font-weight: 800; }
.pulse-src { margin-left: auto; }
.meter {
  position: relative;
  flex: 1;
  min-width: 120px;
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--down), var(--flat), var(--up));
  opacity: 0.85;
}
.meter-mark {
  position: absolute;
  top: -4px;
  width: 4px;
  height: 14px;
  border-radius: 2px;
  background: var(--text-1);
  box-shadow: var(--glow-brand);
  transform: translateX(-50%);
  transition: left 0.6s var(--ease-out);
}
.pulse-breadth { font-size: 12px; color: var(--text-2); }
.pulse-body { display: grid; grid-template-columns: 1fr 1.2fr; gap: 18px; margin-top: 14px; }
.sector-row { display: flex; align-items: center; gap: 10px; padding: 5px 0; }
.sector-name { width: 52px; flex: none; font-size: 12px; color: var(--text-2); }
.sector-bar { flex: 1; height: 6px; border-radius: 3px; background: var(--inset-bg); overflow: hidden; }
.sector-fill { display: block; height: 100%; border-radius: 3px; transition: width 0.6s var(--ease-out); }
.sector-fill.up { background: var(--up); }
.sector-fill.down { background: var(--down); }
.sector-fill.flat { background: var(--flat); }
.sector-pct { width: 64px; text-align: right; font-size: 12px; }
.pulse-evidence { list-style: none; margin: 0; padding: 0; }
.pulse-evidence li {
  font-size: 12px;
  color: var(--text-2);
  padding: 4px 0 4px 14px;
  position: relative;
}
.pulse-evidence li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 10px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--brand-a);
}
.pulse-advice { margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--border); }
.advice-title { display: block; font-size: 12px; font-weight: 700; color: var(--text-2); margin-bottom: 8px; }
.advice-title .hint { font-weight: 400; margin-left: 8px; }
.advice-row { display: grid; grid-template-columns: 20px 92px 76px 1fr; gap: 10px; align-items: baseline; padding: 5px 0; }
.advice-rank { font-weight: 800; color: var(--text-3); }
.advice-rank.rank-top { color: var(--gold); }
.advice-name { font-weight: 700; font-size: 13px; }
.advice-ret { font-size: 13px; font-weight: 700; }
.advice-reason { font-size: 11px; color: var(--text-3); line-height: 1.5; }
@media (max-width: 900px) {
  .pulse-body { grid-template-columns: 1fr; }
  .advice-row { grid-template-columns: 20px 1fr 76px; }
  .advice-reason { grid-column: 2 / -1; }
}
</style>