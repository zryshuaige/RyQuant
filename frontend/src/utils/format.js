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

export const SIDE_LABEL = { BUY: "买入", SELL: "卖出" };

export const ORDER_STATUS = {
  PENDING: { label: "未成交", tone: "info" },
  PARTIAL_FILLED: { label: "部分成交", tone: "warn" },
  FILLED: { label: "已成交", tone: "ok" },
  CANCELLED: { label: "已撤单", tone: "muted" },
  REJECTED: { label: "已废单", tone: "bad" },
};

export function orderStatus(status) {
  return ORDER_STATUS[status] || { label: status, tone: "muted" };
}
