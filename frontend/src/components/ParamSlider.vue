<script setup>
/** 现代表达式参数控件:−/+ 步进夹数值徽章 + 渐变轨道滑杆;control=number 时改数字输入 */
import { computed } from "vue";
import { bumpParam, clampParam, paramStep, trackFill } from "../utils/params";

const props = defineProps({
  param: { type: Object, required: true }, // schema: key/label/unit/type/min/max/default/help/control
  modelValue: { type: [Number, String], required: true },
});
const emit = defineEmits(["update:modelValue"]);

const step = computed(() => paramStep(props.param));
const isNumber = computed(() => props.param.control === "number");
const atMin = computed(() => Number(props.modelValue) <= props.param.min);
const atMax = computed(() => Number(props.modelValue) >= props.param.max);
const fill = computed(() => trackFill(props.param, props.modelValue));

function bump(dir) {
  emit("update:modelValue", bumpParam(props.param, props.modelValue, dir));
}
function onSlide(raw) {
  emit("update:modelValue", clampParam(props.param, raw));
}
function onType(raw) {
  if (raw === "" || raw == null) return;
  emit("update:modelValue", clampParam(props.param, raw));
}
</script>

<template>
  <div class="param-slider">
    <div class="param-top">
      <label :for="`param-${param.key}`">{{ param.label }}</label>
      <span class="param-stepper">
        <button type="button" class="step-btn" :disabled="atMin" :aria-label="`${param.label} 减小`"
          @click="bump(-1)">−</button>
        <span class="param-value num">{{ modelValue }}<i v-if="param.unit">{{ param.unit }}</i></span>
        <button type="button" class="step-btn" :disabled="atMax" :aria-label="`${param.label} 增大`"
          @click="bump(1)">+</button>
      </span>
    </div>
    <input v-if="!isNumber" :id="`param-${param.key}`" type="range" class="range"
      :min="param.min" :max="param.max" :step="step" :value="modelValue" :style="{ background: fill }"
      :aria-label="`${param.label} ${modelValue}${param.unit || ''}`" @input="onSlide($event.target.value)" />
    <input v-else :id="`param-${param.key}`" type="number" class="input param-number"
      :min="param.min" :max="param.max" :step="step" :value="modelValue"
      :aria-label="param.label" @change="onType($event.target.value)" />
    <div class="param-scale mono"><span>{{ param.min }}</span><span>{{ param.max }}</span></div>
    <p class="param-help">{{ param.help }}</p>
  </div>
</template>

<style scoped>
.param-slider { margin-bottom: 12px; }
.param-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.param-top label { font-size: var(--fs-xs); color: var(--text-2); font-weight: 600; }
.param-stepper { display: inline-flex; align-items: center; gap: 6px; }
.step-btn {
  width: 26px; height: 26px;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--panel);
  color: var(--text-2);
  font-size: 15px; line-height: 1;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.step-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--accent-text); background: var(--accent-bg); }
.step-btn:disabled { opacity: 0.35; cursor: default; }
.step-btn:focus-visible { box-shadow: var(--ring); outline: none; }
.param-value { font-family: var(--font-mono); font-size: var(--fs-sm); font-weight: 700; color: var(--text-1); min-width: 44px; text-align: center; }
.param-value i { font-style: normal; font-size: var(--fs-xs); font-weight: 400; color: var(--text-3); margin-left: 2px; }
.range {
  appearance: none;
  -webkit-appearance: none;
  width: 100%;
  height: 4px;
  margin: 8px 0 2px;
  border-radius: 2px;
  background: var(--inset-bg);
  outline: none;
  cursor: pointer;
}
.range::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--panel-solid);
  border: 2px solid var(--accent);
  box-shadow: 0 1px 4px var(--shadow-color);
  cursor: grab;
}
.range::-moz-range-thumb {
  width: 12px; height: 12px;
  border-radius: 50%;
  background: var(--panel-solid);
  border: 2px solid var(--accent);
  box-shadow: 0 1px 4px var(--shadow-color);
  cursor: grab;
}
.range:focus-visible { box-shadow: var(--ring); }
.param-number { margin: 8px 0 2px; padding: 6px 10px; font-family: var(--font-mono); }
.param-scale { display: flex; justify-content: space-between; gap: 8px; font-size: var(--fs-xs); color: var(--text-3); }
.param-help { margin: 3px 0 0; font-size: var(--fs-xs); color: var(--text-3); line-height: 1.55; }
</style>