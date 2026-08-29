/** 图表配色:从 CSS 变量读取,随主题切换自动适配 */
import { theme } from "../composables/useTheme";

export function chartColors() {
  const css = getComputedStyle(document.documentElement);
  const get = (name, fallback) => (css.getPropertyValue(name) || "").trim() || fallback;
  return {
    text: get("--chart-text", "#66738b"),
    split: get("--chart-split", "rgba(124,144,196,0.1)"),
    axis: get("--chart-axis", "rgba(124,144,196,0.3)"),
    tooltipBg: get("--chart-tooltip-bg", "rgba(10,15,26,0.94)"),
    tooltipBorder: get("--chart-tooltip-border", "rgba(124,144,196,0.34)"),
    text2: get("--text-2", "#a7b2c7"),
    up: get("--up", "#ff4d5e"),
    down: get("--down", "#00d49c"),
    brandA: get("--brand-a", "#22d3ee"),
    brandB: get("--brand-b", "#8b5cf6"),
  };
}

/** 当前主题(供 watch 重绘) */
export { theme };
