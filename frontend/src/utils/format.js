/** 格式化与状态映射工具(纯函数,可单测) */

export function fmtMoney(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return n.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtSigned(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${n > 0 ? "+" : ""}${fmtMoney(n, digits)}`;
}

export function fmtPct(value, signed = true) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  const sign = signed && n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export function trendClass(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "flat";
  return n > 0 ? "up" : "down";
}

export function fmtDateTime(iso) {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

export function fmtDate(iso) {
  if (!iso) return "--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

