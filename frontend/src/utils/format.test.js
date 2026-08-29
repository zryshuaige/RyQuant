import { describe, it, expect } from "vitest";
import { fmtMoney, fmtSigned, fmtPct, trendClass, orderStatus } from "./format";

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

describe("orderStatus", () => {
  it("全部状态都有中文标签", () => {
    for (const s of ["PENDING", "PARTIAL_FILLED", "FILLED", "CANCELLED", "REJECTED"]) {
      expect(orderStatus(s).label).toBeTruthy();
    }
  });
  it("未知状态回退", () => {
    expect(orderStatus("UNKNOWN").label).toBe("UNKNOWN");
  });
});
