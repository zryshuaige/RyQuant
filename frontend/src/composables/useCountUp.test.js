import { describe, expect, it } from "vitest";
import { ref, nextTick } from "vue";
import { easeOutCubic, useCountUp } from "./useCountUp";

describe("easeOutCubic", () => {
  it("端点与单调性", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5); // ease-out 前半程更快
    expect(easeOutCubic(0.3)).toBeLessThan(easeOutCubic(0.7));
  });
});

describe("useCountUp", () => {
  it("无 rAF 环境(node/reduced-motion)直接落到目标值", () => {
    const source = ref(12.5);
    const display = useCountUp(source);
    expect(display.value).toBe(12.5);
  });
  it("源变化时同步更新", async () => {
    const source = ref(0);
    const display = useCountUp(source);
    source.value = -8.2;
    await nextTick();
    expect(display.value).toBe(-8.2);
  });
  it("非法值按 0 处理", () => {
    const display = useCountUp(ref("abc"));
    expect(display.value).toBe(0);
  });
});