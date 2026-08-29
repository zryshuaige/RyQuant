/** 全局 Toast(替代 alert):任意组件 import { toast } 即可弹出 */
import { reactive } from "vue";

export const toastState = reactive({ toasts: [] });

let seq = 0;

function push(message, type, duration) {
  const id = ++seq;
  toastState.toasts.push({ id, message, type });
  setTimeout(() => {
    const idx = toastState.toasts.findIndex((t) => t.id === id);
    if (idx !== -1) toastState.toasts.splice(idx, 1);
  }, duration);
}

export const toast = Object.assign((message, type = "info", duration = 3200) => push(message, type, duration), {
  success: (msg, duration) => push(msg, "success", duration ?? 3200),
  error: (msg, duration) => push(msg, "error", duration ?? 4200),
  info: (msg, duration) => push(msg, "info", duration ?? 3200),
});
