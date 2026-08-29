/** 主题状态:dark / light,持久化并同步到 <html data-theme>,图表据此重绘 */
import { ref } from "vue";

const stored = localStorage.getItem("fin_theme") === "light" ? "light" : "dark";
export const theme = ref(stored);

function apply() {
  document.documentElement.setAttribute("data-theme", theme.value);
}

apply();

export function toggleTheme() {
  theme.value = theme.value === "dark" ? "light" : "dark";
  localStorage.setItem("fin_theme", theme.value);
  apply();
  return theme.value;
}

export function isLight() {
  return theme.value === "light";
}
