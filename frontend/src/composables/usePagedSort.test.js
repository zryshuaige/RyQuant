import { describe, expect, it } from "vitest";
import { ref } from "vue";
import { pageList, usePagedSort } from "./usePagedSort";

const rows = () => ref([
  { id: 1, name: "贵州茅台", price: 1474.84, pct: 1.2 },
  { id: 2, name: "中国平安", price: 54.88, pct: -0.4 },
  { id: 3, name: "宁德时代", price: 208.42, pct: -2.1 },
  { id: 4, name: "比亚迪", price: 74.45, pct: 0.8 },
  { id: 5, name: "五粮液", price: 71.61, pct: -0.2 },
]);

describe("usePagedSort", () => {
  it("无排序时保持原顺序", () => {
    const s = usePagedSort(rows(), { pageSize: 10 });
    expect(s.pageRows.value.map((r) => r.id)).toEqual([1, 2, 3, 4, 5]);
  });

  it("排序三态:降 → 升 → 无", () => {
    const s = usePagedSort(rows(), { pageSize: 10 });
    s.toggleSort("price");
    expect(s.sortDir.value).toBe("desc");
    expect(s.pageRows.value[0].id).toBe(1);
    s.toggleSort("price");
    expect(s.sortDir.value).toBe("asc");
    expect(s.pageRows.value[0].id).toBe(2);
    s.toggleSort("price");
    expect(s.sortKey.value).toBe("");
    expect(s.pageRows.value.map((r) => r.id)).toEqual([1, 2, 3, 4, 5]);
  });

  it("数值列按数值而非字符串排序", () => {
    const s = usePagedSort(rows(), { pageSize: 10 });
    s.toggleSort("price");
    s.toggleSort("price");
    expect(s.pageRows.value.map((r) => r.price)).toEqual([54.88, 71.61, 74.45, 208.42, 1474.84]);
  });

  it("分页切片与总数", () => {
    const s = usePagedSort(rows(), { pageSize: 2 });
    expect(s.total.value).toBe(5);
    expect(s.totalPages.value).toBe(3);
    expect(s.pageRows.value.map((r) => r.id)).toEqual([1, 2]);
    s.setPage(3);
    expect(s.pageRows.value.map((r) => r.id)).toEqual([5]);
  });

  it("数据收缩时页码钳制", () => {
    const data = rows();
    const s = usePagedSort(data, { pageSize: 2 });
    s.setPage(3);
    data.value = data.value.slice(0, 2);
    expect(s.page.value).toBe(1);
    expect(s.pageRows.value).toHaveLength(2);
  });

  it("切换页大小回到第一页", () => {
    const s = usePagedSort(rows(), { pageSize: 2 });
    s.setPage(3);
    s.setPageSize(50);
    expect(s.page.value).toBe(1);
    expect(s.pageRows.value).toHaveLength(5);
  });

  it("空数据:1 页 0 行", () => {
    const s = usePagedSort(ref([]), { pageSize: 10 });
    expect(s.total.value).toBe(0);
    expect(s.totalPages.value).toBe(1);
    expect(s.pageRows.value).toEqual([]);
  });

  it("自定义 accessor 支持嵌套字段", () => {
    const data = ref([{ id: 1, stock: { name: "乙" } }, { id: 2, stock: { name: "甲" } }]);
    const s = usePagedSort(data, { pageSize: 10, accessor: (r, k) => r.stock[k] });
    s.toggleSort("name");
    s.toggleSort("name");
    expect(s.pageRows.value.map((r) => r.id)).toEqual([2, 1]);
  });

  it("null 值排序时沉底", () => {
    const data = ref([{ id: 1, v: null }, { id: 2, v: 3 }, { id: 3, v: 1 }]);
    const s = usePagedSort(data, { pageSize: 10 });
    s.toggleSort("v");
    expect(s.pageRows.value.map((r) => r.id)).toEqual([2, 3, 1]);
  });
});

describe("pageList", () => {
  it("≤7 页全列", () => {
    expect(pageList(1, 3)).toEqual([1, 2, 3]);
  });
  it(">7 页省略号", () => {
    expect(pageList(5, 10)).toEqual([1, "gap-lo", 4, 5, 6, "gap-hi", 10]);
    expect(pageList(1, 10)).toEqual([1, 2, "gap-hi", 10]);
    expect(pageList(10, 10)).toEqual([1, "gap-lo", 9, 10]);
  });
});