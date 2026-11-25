/** 数字滚动动画(rAF + ease-out);尊重 prefers-reduced-motion,卸载时取消帧 */
import { ref, watch, onBeforeUnmount, getCurrentInstance } from "vue";

export function easeOutCubic(k) {
  return 1 - Math.pow(1 - k, 3);
}

export function useCountUp(source, { duration = 600 } = {}) {
  const display = ref(0);
  let raf = 0;
  const reduced = typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function animate(to) {
    if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf);
    const target = Number(to) || 0;
    if (reduced || duration <= 0 || typeof requestAnimationFrame !== "function") {
      display.value = target;
      return;
    }
    const from = display.value;
    const t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / duration);
      display.value = from + (target - from) * easeOutCubic(k);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
  }

  watch(source, (v) => animate(v), { immediate: true });
  if (getCurrentInstance()) {
    onBeforeUnmount(() => {
      if (typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf);
    });
  }
  return display;
}