/** 图表配色:从 CSS 变量读取,随 Reverie / Yonder 切换自动适配 */
import { theme } from "../composables/useTheme";

export function chartColors() {
  const css = getComputedStyle(document.documentElement);
  const get = (name, fallback) => (css.getPropertyValue(name) || "").trim() || fallback;
  return {
    text: get("--chart-text", "#56657c"),
    split: get("--chart-split", "rgba(29,41,64,0.08)"),
    axis: get("--chart-axis", "rgba(29,41,64,0.22)"),
    tooltipBg: get("--chart-tooltip-bg", "#f7fafd"),
    tooltipBorder: get("--chart-tooltip-border", "rgba(29,41,64,0.18)"),
    text2: get("--text-2", "#4a5a70"),
    up: get("--up", "#c2453a"),
    down: get("--down", "#2f8f6b"),
    brandA: get("--accent", "#3d87b8"),
    brandB: get("--gold", "#a8823c"),
    gold: get("--gold", "#a8823c"),
    series: [
      get("--accent", "#3d87b8"),
      get("--gold", "#a8823c"),
      get("--text-3", "#56657c"),
      get("--down", "#2f8f6b"),
      get("--chart-s5", "#7a63c9"),
      get("--chart-s6", "#3f9e8f"),
    ],
  };
}

/** 当前主题(供 watch 重绘) */
export { theme };