/** 参数控件纯函数:步进 / 钳制 / 轨道填充(供 ParamSlider 与 vitest 复用) */

export function paramStep(p) {
  return p.type === "float" ? 0.1 : 1;
}

export function clampParam(p, raw) {
  if (raw == null || raw === "") return p.default;
  const v = Number(raw);
  if (!Number.isFinite(v)) return p.default;
  const clamped = Math.min(p.max, Math.max(p.min, v));
  return p.type === "float" ? Math.round(clamped * 10) / 10 : Math.round(clamped);
}

export function bumpParam(p, current, dir) {
  return clampParam(p, Number(current) + dir * paramStep(p));
}

export function trackFill(p, value) {
  const span = p.max - p.min || 1;
  const pct = Math.min(100, Math.max(0, ((Number(value) - p.min) / span) * 100));
  return `linear-gradient(90deg, var(--accent) ${pct}%, var(--inset-bg) ${pct}%)`;
}