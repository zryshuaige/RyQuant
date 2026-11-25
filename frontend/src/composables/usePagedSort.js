/** 分页 + 三态排序(升/降/无):DataTable 与移动卡片共用同一状态 */
import { computed, ref, toValue, watch } from "vue";

function defaultAccessor(row, key) {
  return row?.[key];
}

function compare(a, b) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), "zh-CN");
}

/** 页码序列:≤7 页全列,否则 1 … 当前±1 … 末页 */
export function pageList(page, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const pages = [1];
  const lo = Math.max(2, page - 1);
  const hi = Math.min(totalPages - 1, page + 1);
  if (lo > 2) pages.push("gap-lo");
  for (let p = lo; p <= hi; p++) pages.push(p);
  if (hi < totalPages - 1) pages.push("gap-hi");
  pages.push(totalPages);
  return pages;
}

export function usePagedSort(rows, options = {}) {
  const { pageSize: initialSize = 10, sortKey: initialKey = "", sortDir: initialDir = "desc", accessor = defaultAccessor } = options;
  const page = ref(1);
  const pageSize = ref(initialSize);
  const sortKey = ref(initialKey);
  const sortDir = ref(initialDir);

  const list = computed(() => toValue(rows) || []);
  const sorted = computed(() => {
    if (!sortKey.value) return list.value;
    const dir = sortDir.value === "asc" ? 1 : -1;
    return [...list.value].sort((a, b) => {
      const av = accessor(a, sortKey.value);
      const bv = accessor(b, sortKey.value);
      // 空值无论升降序都沉底
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return dir * compare(av, bv);
    });
  });
  const total = computed(() => sorted.value.length);
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));
  const pageRows = computed(() => {
    const start = (page.value - 1) * pageSize.value;
    return sorted.value.slice(start, start + pageSize.value);
  });

  watch([total, pageSize], () => {
    if (page.value > totalPages.value) page.value = totalPages.value;
    if (page.value < 1) page.value = 1;
  }, { flush: "sync" });

  function toggleSort(key) {
    if (sortKey.value !== key) {
      sortKey.value = key;
      sortDir.value = "desc";
    } else if (sortDir.value === "desc") {
      sortDir.value = "asc";
    } else {
      sortKey.value = "";
      sortDir.value = "desc";
    }
    page.value = 1;
  }
  function setPage(p) {
    page.value = Math.min(Math.max(1, p), totalPages.value);
  }
  function setPageSize(size) {
    pageSize.value = size;
    page.value = 1;
  }

  return { page, pageSize, sortKey, sortDir, sorted, pageRows, total, totalPages, toggleSort, setPage, setPageSize };
}