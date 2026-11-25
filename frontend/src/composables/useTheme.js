/** 主题状态:reverie(浅)/ yonder(深),持久化并同步到 <html data-theme>,图表据此重绘 */
import { ref } from "vue";

function normalize(raw) {
  if (raw === "yonder" || raw === "dark") return "yonder";
  return "reverie";
}

const stored = normalize(localStorage.getItem("fin_theme"));
export const theme = ref(stored);

function apply() {
  document.documentElement.setAttribute("data-theme", theme.value);
}

apply();

export function toggleTheme() {
  theme.value = theme.value === "yonder" ? "reverie" : "yonder";
  localStorage.setItem("fin_theme", theme.value);
  apply();
  return theme.value;
}

export function isLight() {
  return theme.value === "reverie";
}