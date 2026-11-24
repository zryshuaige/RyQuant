import { describe, it, expect } from "vitest";
import { fmtMoney, fmtSigned, fmtPct, trendClass, fmtDate } from "./format";

describe("fmtMoney", () => {
  it("千分位与两位小数", () => {
    expect(fmtMoney(1234567.891)).toBe("1,234,567.89");
    expect(fmtMoney(0)).toBe("0.00");
  });
  it("非数字返回占位符", () => {
    expect(fmtMoney(NaN)).toBe("--");
    expect(fmtMoney(undefined)).toBe("--");
  });
});

describe("fmtSigned / fmtPct", () => {
  it("正数带加号", () => {
    expect(fmtSigned(1234.5)).toBe("+1,234.50");
    expect(fmtPct(3.1415)).toBe("+3.14%");
  });
  it("负数与零", () => {
    expect(fmtSigned(-2)).toBe("-2.00");
    expect(fmtPct(0, false)).toBe("0.00%");
  });
});

describe("trendClass", () => {
  it("涨跌平映射 A 股配色类名", () => {
    expect(trendClass(1.5)).toBe("up");
    expect(trendClass(-0.01)).toBe("down");
    expect(trendClass(0)).toBe("flat");
  });
});

describe("fmtDate(自选加入日期标注)", () => {
  it("ISO 转 YYYY-MM-DD", () => {
    expect(fmtDate("2026-10-09T12:34:56+08:00")).toBe("2026-10-09");
  });
  it("空值占位", () => {
    expect(fmtDate(null)).toBe("--");
    expect(fmtDate("")).toBe("--");
  });
});
