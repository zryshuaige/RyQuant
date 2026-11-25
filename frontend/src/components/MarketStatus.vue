<script setup>
/** 大盘状态:先给结论和策略,再折叠判断依据。 */
import { computed, ref } from "vue";
import { fmtSigned, trendClass } from "../utils/format";
import InfoTip from "./InfoTip.vue";
import AppIcon from "./AppIcon.vue";

const props = defineProps({
  pulse: { type: Object, default: null },
  loading: { type: Boolean, default: false },
});
const emit = defineEmits(["backtest", "compare"]);
const open = ref(false);

const REGIME = {
  bull: { label: "多头", cls: "regime-bull", read: "上证指数在 20 日均线上方,趋势偏强。" },
  bear: { label: "空头", cls: "regime-bear", read: "上证指数在 20 日均线下方,市场整体偏弱。" },
  range: { label: "震荡", cls: "regime-range", read: "指数在均线附近反复,方向尚不明确。" },
  high_vol: { label: "高波动", cls: "regime-high", read: "近期波动明显放大,注意控制风险暴露。" },
};
const regime = computed(() => REGIME[props.pulse?.regime] || REGIME.range);
const advice = computed(() => props.pulse?.advice?.[0] || null);
const breadth = computed(() => props.pulse?.breadth || {});

const adviceText = computed(() => {
  if (!advice.value) return "";
  if (advice.value.regime_trades > 0) {
    return `类似行情下,四种策略中相对最好;区间收益 ${fmtSigned(advice.value.regime_return_pct)}%,共 ${advice.value.regime_trades} 笔交易。`;
  }
  return "这类行情的历史样本较少,暂按样本外表现排序。";
});

function heatWidth(pct) {
  const max = Math.max(1, ...(props.pulse?.sectors || []).map((s) => Math.abs(s.change_pct)));
  return `${Math.min(Math.abs(pct) / max * 100, 100)}%`;
}
</script>

<template>
  <section class="panel status-panel">
    <template v-if="pulse">
      <div class="status-main">
        <div class="status-head">
          <span class="regime" :class="regime.cls">{{ regime.label }}</span>
          <span class="status-time">
            多空评分 <b class="num" :class="trendClass(pulse.score)">{{ fmtSigned(Math.round(pulse.score), 0) }}</b>
            <InfoTip text="由趋势、市场广度与波动率规则综合得到,-100 为最弱、+100 为最强,仅作参考。" />
          </span>
        </div>
        <p class="status-read">{{ regime.read }}</p>
        <div class="status-kpis">
          <div class="status-kpi">
            <b class="num"><span class="up">{{ breadth.advance }}</span> / <span class="down">{{ breadth.decline }}</span></b>
            <span>上涨 / 下跌</span>
          </div>
          <div class="status-kpi">
            <b class="num">{{ breadth.pct_above_ma20 ?? "--" }}%</b>
            <span>站上 20 日均线</span>
          </div>
          <div class="status-kpi">
            <b class="num">{{ pulse.trend?.vol_percentile ?? "--" }}%</b>
            <span>
              20 日波动分位
              <InfoTip text="当前 20 日波动率在过去 250 个交易日中的位置,越高代表波动越大。" />
            </span>
          </div>
        </div>
        <button class="disclosure" :class="{ open }" :aria-expanded="open" @click="open = !open">
          判断依据
          <AppIcon name="chevron-down" :size="14" class="chev" />
        </button>
      </div>

      <div class="advice-card">
        <template v-if="advice">
          <span class="advice-eyebrow">当前行情更适合</span>
          <b class="advice-name">{{ advice.name }}</b>
          <p class="advice-text">{{ adviceText }}</p>
          <div class="advice-actions">
            <button class="btn btn-primary btn-sm" @click="emit('backtest', advice.id)">用此策略回测</button>
            <button class="btn btn-sm" @click="emit('compare')">对比全部策略</button>
          </div>
        </template>
        <template v-else>
          <span class="advice-eyebrow">策略建议</span>
          <b class="advice-name">历史数据不足</b>
          <p class="advice-text">至少需要 60 个交易日的数据才能判断当前行情下的策略表现。</p>
        </template>
      </div>

      <div v-if="open" class="status-detail">
        <div class="detail-sectors">
          <h4 class="detail-title">板块平均涨跌</h4>
          <div v-for="s in pulse.sectors" :key="s.name" class="sector-row">
            <span class="sector-name">{{ s.name }}</span>
            <span class="sector-bar">
              <span class="sector-fill" :class="trendClass(s.change_pct)" :style="{ width: heatWidth(s.change_pct) }"></span>
            </span>
            <span class="num sector-pct" :class="trendClass(s.change_pct)">{{ fmtSigned(s.change_pct) }}%</span>
          </div>
        </div>
        <div class="detail-evidence">
          <h4 class="detail-title">规则信号</h4>
          <ul class="evidence-list">
            <li v-for="(e, i) in pulse.evidence" :key="i">{{ e }}</li>
          </ul>
          <div v-if="pulse.advice?.length > 1" class="rank-list">
            <h4 class="detail-title">策略排名</h4>
            <div v-for="(a, i) in pulse.advice" :key="a.id" class="rank-row">
              <span class="rank-no num">{{ i + 1 }}</span>
              <span class="rank-name">{{ a.name }}</span>
              <span class="num" :class="trendClass(a.regime_return_pct ?? a.oos_return_pct)">
                {{ a.regime_trades > 0 ? fmtSigned(a.regime_return_pct) + "%" : "无成交" }}
              </span>
              <span class="rank-meta">{{ a.regime_trades > 0 ? `${a.regime_trades} 笔` : "按样本外排序" }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
    <div v-else class="status-skeleton">
      <div class="skeleton" style="width: 140px; height: 26px"></div>
      <div class="skeleton" style="width: 60%; height: 16px; margin-top: 14px"></div>
      <div class="skeleton" style="width: 100%; height: 52px; margin-top: 18px"></div>
    </div>
  </section>
</template>

<style scoped>
.status-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 1fr);
  gap: var(--space-5);
  align-items: center;
}
.status-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.regime { padding: 3px 14px; border-radius: var(--radius-pill); font-size: var(--fs-md); font-weight: 700; letter-spacing: 0.02em; }
.regime-bull { color: var(--up); background: var(--up-bg); }
.regime-bear { color: var(--down); background: var(--down-bg); }
.regime-range { color: var(--accent-text); background: var(--accent-bg); }
.regime-high { color: var(--warn); background: var(--warn-bg); }
.status-time { color: var(--text-3); font-size: var(--fs-xs); display: inline-flex; align-items: center; gap: 2px; }
.status-time b { color: var(--text-2); font-weight: 700; }
.status-read { color: var(--text-2); font-size: var(--fs-md); margin: 10px 0 14px; }
.status-kpis { display: flex; gap: 0; flex-wrap: wrap; }
.status-kpi { display: grid; gap: 2px; padding-right: 24px; margin-right: 24px; border-right: 1px solid var(--border); }
.status-kpi:last-child { border-right: none; margin-right: 0; padding-right: 0; }
.status-kpi b { font-family: var(--font-display); font-size: 24px; font-weight: 600; line-height: 1.25; letter-spacing: -0.02em; }
.status-kpi span { font-size: var(--fs-xs); color: var(--text-3); display: inline-flex; align-items: center; }
.advice-card {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-left: 2px solid var(--accent);
  border-radius: var(--radius);
  background: var(--accent-bg);
}
.advice-eyebrow { font-family: var(--font-mono); font-size: var(--fs-xs); letter-spacing: 0.06em; color: var(--text-3); }
.advice-name { font-family: var(--font-display); font-size: 20px; font-weight: 600; letter-spacing: -0.02em; margin: 4px 0 6px; }
.advice-text { font-size: var(--fs-sm); color: var(--text-2); margin: 0 0 12px; line-height: 1.55; }
.advice-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.status-detail {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
  margin-top: -4px;
}
.detail-title { font-family: var(--font-mono); font-size: var(--fs-xs); letter-spacing: 0.06em; color: var(--text-3); font-weight: 600; margin-bottom: 8px; }
.sector-row { display: flex; align-items: center; gap: 10px; padding: 4px 0; }
.sector-name { width: 48px; flex: none; font-size: var(--fs-xs); color: var(--text-2); }
.sector-bar { flex: 1; height: 6px; border-radius: 3px; background: var(--inset-bg); overflow: hidden; }
.sector-fill { display: block; height: 100%; border-radius: 3px; }
.sector-fill.up { background: var(--up); }
.sector-fill.down { background: var(--down); }
.sector-fill.flat { background: var(--flat); }
.sector-pct { width: 62px; text-align: right; font-size: var(--fs-xs); }
.evidence-list { list-style: none; margin: 0 0 12px; padding: 0; }
.evidence-list li { position: relative; padding: 3px 0 3px 12px; font-size: var(--fs-xs); color: var(--text-2); line-height: 1.6; }
.evidence-list li::before { content: ""; position: absolute; left: 0; top: 10px; width: 4px; height: 4px; border-radius: 50%; background: var(--text-3); }
.rank-row { display: flex; align-items: center; gap: 10px; padding: 3px 0; font-size: var(--fs-xs); }
.rank-no { width: 14px; color: var(--text-3); }
.rank-name { flex: 1; color: var(--text-1); font-weight: 600; }
.rank-meta { color: var(--text-3); }
.status-skeleton { grid-column: 1 / -1; }
@media (max-width: 900px) {
  .status-panel { grid-template-columns: 1fr; gap: var(--space-4); }
  .status-detail { grid-template-columns: 1fr; gap: var(--space-4); }
  .status-kpis { gap: var(--space-5); }
}
</style>