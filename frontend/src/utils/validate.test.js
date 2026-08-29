import { describe, it, expect } from "vitest";
import { lotError, priceError, estimateFee, parseQuantity } from "./validate";

describe("lotError(与后端手数规则一致)", () => {
  it("买入必须整手", () => {
    expect(lotError(150, 100, { side: "BUY" })).toContain("100 的整数倍");
    expect(lotError(200, 100, { side: "BUY" })).toBeNull();
  });
  it("科创板 200 股一手", () => {
    expect(lotError(100, 200, { side: "BUY" })).toContain("200 的整数倍");
    expect(lotError(200, 200, { side: "BUY" })).toBeNull();
  });
  it("卖出整手或一次性清仓", () => {
    expect(lotError(50, 100, { side: "SELL", available: 150 })).toContain("清仓");
    expect(lotError(150, 100, { side: "SELL", available: 150 })).toBeNull(); // 零股清仓
    expect(lotError(100, 100, { side: "SELL", available: 150 })).toBeNull();
  });
  it("非法数量", () => {
    expect(lotError(0, 100, { side: "BUY" })).toBeTruthy();
    expect(lotError(-1, 100, { side: "BUY" })).toBeTruthy();
    expect(lotError("abc", 100, { side: "BUY" })).toBeTruthy();
  });
});

describe("priceError", () => {
  it("限价必须大于 0", () => {
    expect(priceError(0)).toBe("委托价格必须大于 0");
    expect(priceError("")).toBe("请输入委托价格");
  });
  it("涨跌停区间", () => {
    expect(priceError(20, { low: 11.88, high: 14.52 })).toContain("涨跌停");
    expect(priceError(13.5, { low: 11.88, high: 14.52 })).toBeNull();
  });
  it("市价单不要求价格", () => {
    expect(priceError("", { required: false })).toBeNull();
  });
});

describe("estimateFee(与后端费率一致)", () => {
  it("佣金最低 5 元", () => {
    const f = estimateFee(1000, "BUY"); // 1000*0.00025 = 0.25 → 取最低 5
    expect(f.fee).toBe(5);
    expect(f.total).toBe(1005);
  });
  it("大额按万 2.5", () => {
    const f = estimateFee(100000, "BUY");
    expect(f.commission).toBe(25);
    expect(f.total).toBe(100025);
  });
  it("卖出加印花税万 5", () => {
    const f = estimateFee(100000, "SELL");
    expect(f.commission).toBe(25);
    expect(f.stamp).toBe(50);
    expect(f.fee).toBe(75);
    expect(f.total).toBe(100000 - 75);
  });
});

describe("parseQuantity", () => {
  it("只接受正整数", () => {
    expect(parseQuantity("200")).toBe(200);
    expect(parseQuantity(300)).toBe(300);
    expect(parseQuantity(150.5)).toBeNull();
    expect(parseQuantity(-1)).toBeNull();
    expect(parseQuantity("x")).toBeNull();
  });
});
