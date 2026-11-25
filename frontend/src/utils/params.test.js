import { describe, expect, it } from "vitest";
import { bumpParam, clampParam, paramStep, trackFill } from "./params";

const intParam = { key: "n", type: "int", min: 2, max: 60, default: 20 };
const floatParam = { key: "k", type: "float", min: 0.5, max: 4, default: 2 };

describe("paramStep", () => {
  it("int 步长 1,float 步长 0.1", () => {
    expect(paramStep(intParam)).toBe(1);
    expect(paramStep(floatParam)).toBe(0.1);
  });
});

describe("clampParam", () => {
  it("越界截断到 min/max", () => {
    expect(clampParam(intParam, 999)).toBe(60);
    expect(clampParam(intParam, -5)).toBe(2);
    expect(clampParam(floatParam, 9)).toBe(4);
  });
  it("int 取整,float 保留一位小数", () => {
    expect(clampParam(intParam, 7.6)).toBe(8);
    expect(clampParam(floatParam, 2.34)).toBe(2.3);
  });
  it("非法输入回退默认值", () => {
    expect(clampParam(intParam, "abc")).toBe(20);
    expect(clampParam(floatParam, null)).toBe(2);
  });
});

describe("bumpParam", () => {
  it("按步长增减", () => {
    expect(bumpParam(intParam, 20, 1)).toBe(21);
    expect(bumpParam(intParam, 20, -1)).toBe(19);
    expect(bumpParam(floatParam, 2, 1)).toBe(2.1);
  });
  it("边界处不再越界", () => {
    expect(bumpParam(intParam, 60, 1)).toBe(60);
    expect(bumpParam(intParam, 2, -1)).toBe(2);
    expect(bumpParam(floatParam, 4, 1)).toBe(4);
  });
});

describe("trackFill", () => {
  it("按当前值生成渐变填充", () => {
    expect(trackFill(intParam, 2)).toContain("0%");
    expect(trackFill(intParam, 60)).toContain("100%");
    const mid = trackFill({ key: "x", type: "int", min: 0, max: 10 }, 5);
    expect(mid).toBe("linear-gradient(90deg, var(--accent) 50%, var(--inset-bg) 50%)");
  });
});