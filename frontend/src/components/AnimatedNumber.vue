<script setup>
/** 数字滚动补间 + 涨跌闪烁:任何变化的金额/价格用它展示即有"活的行情"感 */
import { ref, watch, onBeforeUnmount, computed } from "vue";
import { fmtMoney } from "../utils/format";

const props = defineProps({
  value: { type: Number, default: 0 },
  digits: { type: Number, default: 2 },
  duration: { type: Number, default: 500 },
  tween: { type: Boolean, default: true },
});

const display = ref(props.value);
const flash = ref("");
let rafId = null;
let flashTimer = null;
let fromValue = props.value;

const flashClass = computed(() => (flash.value ? `flash-${flash.value}` : ""));

function stopAll() {
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
  if (flashTimer) clearTimeout(flashTimer);
}

watch(
  () => props.value,
  (to) => {
    const from = display.value;
    if (!props.tween || from === to) return;
    stopAll();
    flash.value = to > from ? "up" : to < from ? "down" : "";
    flashTimer = setTimeout(() => (flash.value = ""), 700);

    const start = performance.now();
    fromValue = from;
    const step = (now) => {
      const t = Math.min((now - start) / props.duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      display.value = fromValue + (to - fromValue) * eased;
      if (t < 1) rafId = requestAnimationFrame(step);
      else display.value = to;
    };
    rafId = requestAnimationFrame(step);
  }
);

onBeforeUnmount(stopAll);
</script>

<template>
  <span class="num animated-num" :class="flashClass">{{ fmtMoney(display, digits) }}</span>
</template>

<style scoped>
.animated-num { display: inline-block; }
</style>
