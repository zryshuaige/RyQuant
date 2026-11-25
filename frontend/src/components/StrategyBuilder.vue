<script setup>
/** 可视化规则搭建器:选指标 × 条件 × 指标/常量,边搭边看信号预览,保存为「我的策略」 */
import { computed, nextTick, ref, watch, onBeforeUnmount } from "vue";
import { previewStrategy, createCustomStrategy, updateCustomStrategy } from "../api";
import { toast } from "../composables/useToast";
import ParamSlider from "./ParamSlider.vue";
import StrategyPreview from "./StrategyPreview.vue";
import AppIcon from "./AppIcon.vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  initial: { type: Object, default: null }, // 编辑已有自定义策略 {id,name,rule,fits}
  prefill: { type: Object, default: null }, // 内置策略预填 {name,rule,fits}
  symbol: { type: String, default: "" },
});
const emit = defineEmits(["close", "saved"]);

const KINDS = [
  { kind: "sma", label: "均线 SMA" },
  { kind: "ema", label: "指数均线 EMA" },
  { kind: "rsi", label: "强弱值 RSI" },
  { kind: "dif", label: "动能线 DIF" },
  { kind: "dea", label: "信号线 DEA" },
  { kind: "boll_upper", label: "布林上轨" },
  { kind: "boll_mid", label: "布林中轨" },
  { kind: "boll_lower", label: "布林下轨" },
  { kind: "close", label: "收盘价" },
  { kind: "const", label: "固定数值" },
];
const OPS = [
  { op: "cross_up", label: "上穿" },
  { op: "cross_down", label: "下穿" },
  { op: "gt", label: "高于" },
  { op: "lt", label: "低于" },
];
const FITS = { bull: "多头趋势", bear: "空头趋势", range: "震荡", high_vol: "高波动" };

const name = ref("");
const buyLeft = ref("sma");
const buyOp = ref("cross_up");
const buyRight = ref("sma");
const sellMirror = ref(true);
const sellLeft = ref("sma");
const sellOp = ref("cross_down");
const sellRight = ref("sma");
const fits = ref([]);
const paramValues = ref({});
const schema = ref([]);
const previewData = ref(null);
const buyText = ref("");
const sellText = ref("");
const previewLoading = ref(false);
const saving = ref(false);
const error = ref("");

const ruleDraft = computed(() => {
  const rule = {
    buy: { left: { kind: buyLeft.value }, op: buyOp.value, right: { kind: buyRight.value } },
    sell_mirror: sellMirror.value,
  };
  if (!sellMirror.value) {
    rule.sell = { left: { kind: sellLeft.value }, op: sellOp.value, right: { kind: sellRight.value } };
  }
  return rule;
});
const structureKey = computed(() =>
  [buyLeft.value, buyOp.value, buyRight.value, sellMirror.value, sellLeft.value, sellOp.value, sellRight.value].join("|"));

/* 预览请求:结构变化 / 参数拖动 → debounce 刷新,序号守卫防竞态 */
let seq = 0;
let timer = 0;
let suppress = false;
async function refresh() {
  if (!props.open) return;
  if (!props.symbol) { previewData.value = null; return; }
  const my = ++seq;
  previewLoading.value = true;
  try {
    const res = await previewStrategy({
      rule: ruleDraft.value, symbol: props.symbol, days: 120,
      params: paramValues.value, name: name.value || "我的策略",
    });
    if (my !== seq) return;
    schema.value = res.params_schema || [];
    buyText.value = res.buy_text;
    sellText.value = res.sell_text;
    previewData.value = { candles: res.candles, preview: res.preview };
    const next = {};
    let changed = false;
    for (const p of schema.value) {
      next[p.key] = paramValues.value[p.key] ?? res.params[p.key];
      if (paramValues.value[p.key] == null) changed = true;
    }
    if (changed || Object.keys(paramValues.value).length !== schema.value.length) {
      suppress = true;
      paramValues.value = next;
      await nextTick();
      suppress = false;
    }
    error.value = "";
  } catch (e) {
    if (my !== seq) return;
    error.value = e.friendlyMessage || "预览失败";
    previewData.value = null;
  } finally {
    if (my === seq) previewLoading.value = false;
  }
}
function scheduleRefresh(delay = 320) {
  clearTimeout(timer);
  timer = setTimeout(refresh, delay);
}
watch(structureKey, () => scheduleRefresh(120));
watch(paramValues, () => { if (!suppress) scheduleRefresh(); }, { deep: true });
watch(() => props.symbol, () => scheduleRefresh(120));

function loadRule(rule) {
  buyLeft.value = rule?.buy?.left?.kind || "sma";
  buyOp.value = rule?.buy?.op || "cross_up";
  buyRight.value = rule?.buy?.right?.kind || "sma";
  sellMirror.value = rule ? Boolean(rule.sell_mirror) : true; // 新建默认镜像(趋势策略最常见)
  sellLeft.value = rule?.sell?.left?.kind || "sma";
  sellOp.value = rule?.sell?.op || "cross_down";
  sellRight.value = rule?.sell?.right?.kind || "sma";
}
watch(() => props.open, (open) => {
  if (!open) return;
  error.value = "";
  paramValues.value = {};
  schema.value = [];
  previewData.value = null;
  const src = props.initial || props.prefill;
  name.value = src?.name || "";
  fits.value = [...(src?.fits || [])];
  loadRule(src?.rule);
  scheduleRefresh(60);
}, { immediate: true });

/* Esc 关闭 */
function onKey(e) { if (e.key === "Escape" && props.open) emit("close"); }
watch(() => props.open, (open) => {
  if (open) document.addEventListener("keydown", onKey);
  else document.removeEventListener("keydown", onKey);
});
onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKey);
  clearTimeout(timer);
});

function toggleFit(f) {
  fits.value = fits.value.includes(f) ? fits.value.filter((x) => x !== f) : [...fits.value, f];
}
async function save() {
  error.value = "";
  if (!name.value.trim()) { error.value = "请给策略起个名字(1~20 字)"; return; }
  saving.value = true;
  try {
    const payload = {
      name: name.value.trim(), rule: ruleDraft.value,
      fits: fits.value, params: paramValues.value,
    };
    const rec = props.initial
      ? await updateCustomStrategy(props.initial.id, payload)
      : await createCustomStrategy(payload);
    toast.success(props.initial ? "策略已更新" : "已加入「我的策略」");
    emit("saved", rec);
    emit("close");
  } catch (e) {
    error.value = e.friendlyMessage || "保存失败";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="builder-overlay" @click.self="emit('close')">
      <div class="builder-panel" role="dialog" aria-modal="true" aria-label="搭建我的策略">
        <header class="builder-head">
          <h2>{{ initial ? "编辑我的策略" : "搭建我的策略" }}</h2>
          <button class="icon-btn" aria-label="关闭" @click="emit('close')">
            <AppIcon name="close" :size="16" />
          </button>
        </header>
        <div class="builder-body">
          <div class="builder-form">
            <div class="field">
              <label for="builder-name">策略名称</label>
              <input id="builder-name" v-model="name" class="input" maxlength="20" placeholder="例如:我的均线突破" />
            </div>

            <div class="rule-block">
              <div class="rule-line">
                <span class="rule-chip buy">买入</span>
                <select v-model="buyLeft" class="select" aria-label="买入左侧指标">
                  <option v-for="k in KINDS" :key="k.kind" :value="k.kind">{{ k.label }}</option>
                </select>
                <select v-model="buyOp" class="select op-select" aria-label="买入比较方式">
                  <option v-for="o in OPS" :key="o.op" :value="o.op">{{ o.label }}</option>
                </select>
                <select v-model="buyRight" class="select" aria-label="买入右侧指标">
                  <option v-for="k in KINDS" :key="k.kind" :value="k.kind">{{ k.label }}</option>
                </select>
              </div>
              <label class="mirror-toggle">
                <input v-model="sellMirror" type="checkbox" /> 卖出与买入镜像(条件反向)
              </label>
              <div class="rule-line" :class="{ disabled: sellMirror }">
                <span class="rule-chip sell">卖出</span>
                <select v-model="sellLeft" class="select" :disabled="sellMirror" aria-label="卖出左侧指标">
                  <option v-for="k in KINDS" :key="k.kind" :value="k.kind">{{ k.label }}</option>
                </select>
                <select v-model="sellOp" class="select op-select" :disabled="sellMirror" aria-label="卖出比较方式">
                  <option v-for="o in OPS" :key="o.op" :value="o.op">{{ o.label }}</option>
                </select>
                <select v-model="sellRight" class="select" :disabled="sellMirror" aria-label="卖出右侧指标">
                  <option v-for="k in KINDS" :key="k.kind" :value="k.kind">{{ k.label }}</option>
                </select>
              </div>
            </div>

            <div v-if="schema.length" class="builder-params">
              <ParamSlider v-for="p in schema" :key="p.key" :param="p"
                :model-value="paramValues[p.key] ?? p.default"
                @update:model-value="paramValues[p.key] = $event" />
            </div>

            <div class="field">
              <label>适合行情(可选)</label>
              <div class="fits-row">
                <button v-for="(label, f) in FITS" :key="f" type="button" class="preset-chip"
                  :class="{ on: fits.includes(f) }" :aria-pressed="fits.includes(f)"
                  @click="toggleFit(f)">{{ label }}</button>
              </div>
            </div>

            <p v-if="error" class="builder-error" role="alert">{{ error }}</p>
            <div class="builder-actions">
              <button class="btn" @click="emit('close')">取消</button>
              <button class="btn btn-primary" :disabled="saving" @click="save">
                <span v-if="saving" class="spinner"></span>
                {{ saving ? "保存中…" : (initial ? "保存修改" : "保存策略") }}
              </button>
            </div>
          </div>

          <div class="builder-preview">
            <div class="preview-head">
              <span class="mono">实时预览</span>
              <span v-if="previewLoading" class="spinner"></span>
            </div>
            <template v-if="symbol">
              <div v-if="buyText" class="preview-rules">
                <div class="rule-row"><span class="rule-chip buy">买</span><span>{{ buyText }}</span></div>
                <div class="rule-row"><span class="rule-chip sell">卖</span><span>{{ sellText }}</span></div>
              </div>
              <StrategyPreview v-if="previewData" :data="previewData" :height="320" />
              <div v-else class="preview-empty">
                {{ previewLoading ? "正在计算信号…" : "调整左侧规则,这里会实时画出指标与买卖点。" }}
              </div>
            </template>
            <div v-else class="preview-empty">先在页面选择回测对象,即可边搭边看信号预览。</div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.builder-overlay {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(8, 19, 27, 0.4);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.builder-panel {
  width: min(980px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-2);
}
.builder-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--panel);
  z-index: 2;
}
.builder-head h2 { margin: 0; font-family: var(--font-display); font-size: var(--fs-lg); letter-spacing: -0.02em; }
.builder-body { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 20px; padding: 20px; }
.builder-form { display: grid; gap: 14px; align-content: start; }
.rule-block { display: grid; gap: 8px; padding: 12px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--inset-bg-soft); }
.rule-line { display: grid; grid-template-columns: auto minmax(0, 1fr) 74px minmax(0, 1fr); gap: 6px; align-items: center; }
.rule-line.disabled { opacity: 0.5; }
.rule-line .select { padding: 6px 8px; font-size: var(--fs-xs); min-width: 0; }
.op-select { text-align: center; }
.rule-chip {
  flex: none;
  padding: 0 9px;
  border-radius: var(--radius-pill);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.8;
}
.rule-chip.buy { background: var(--up-bg); color: var(--up); }
.rule-chip.sell { background: var(--down-bg); color: var(--down); }
.mirror-toggle { display: flex; align-items: center; gap: 6px; font-size: var(--fs-xs); color: var(--text-2); cursor: pointer; }
.mirror-toggle input { accent-color: var(--accent); width: 14px; height: 14px; margin: 0; }
.builder-params { padding-top: 2px; }
.fits-row { display: flex; gap: 6px; flex-wrap: wrap; }
.preset-chip {
  padding: 3px 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--panel);
  color: var(--text-2);
  font-size: var(--fs-xs);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.preset-chip:hover { border-color: var(--text-3); color: var(--text-1); }
.preset-chip.on { background: var(--btn-primary-bg); border-color: transparent; color: var(--btn-primary-fg); }
.builder-error { margin: 0; color: var(--up); font-size: var(--fs-xs); }
.builder-actions { display: flex; justify-content: flex-end; gap: 8px; }
.builder-preview { display: grid; gap: 10px; align-content: start; }
.preview-head { display: flex; align-items: center; gap: 8px; font-size: var(--fs-xs); color: var(--text-3); letter-spacing: 0.06em; }
.preview-rules { display: grid; gap: 6px; }
.rule-row { display: flex; align-items: flex-start; gap: 8px; font-size: var(--fs-xs); color: var(--text-1); line-height: 1.55; }
.preview-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--text-3);
  font-size: var(--fs-sm);
  border: 1px dashed var(--border);
  border-radius: var(--radius);
}
@media (max-width: 860px) {
  .builder-body { grid-template-columns: minmax(0, 1fr); }
  .builder-overlay { padding: 10px; align-items: flex-start; }
  .builder-panel { max-height: calc(100vh - 20px); }
}
</style>