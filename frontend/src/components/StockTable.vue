<script setup>
/** 标的表:分页 + 排序 + 数字右对齐;点击行看 K 线,右侧明确「加入自选 / 移除」。 */
import { computed } from "vue";
import DataTable from "./DataTable.vue";
import DataPagination from "./DataPagination.vue";
import AppIcon from "./AppIcon.vue";
import { usePagedSort } from "../composables/usePagedSort";
import { fmtMoney, fmtPct, trendClass } from "../utils/format";

const props = defineProps({
  stocks: { type: Array, required: true },
  favoriteIds: { type: Set, default: () => new Set() },
  selectedSymbol: { type: String, default: "" },
  pendingIds: { type: Array, default: () => [] },
  showFavorite: { type: Boolean, default: true },
});
const emit = defineEmits(["toggle-fav", "select"]);

const rows = computed(() => props.stocks);
const { page, pageSize, sortKey, sortDir, pageRows, total, totalPages, toggleSort, setPage, setPageSize } =
  usePagedSort(rows, { pageSize: 10 });

const columns = computed(() => [
  { key: "name", label: "名称" },
  { key: "symbol", label: "代码", mono: true, hideMobile: true },
  { key: "price", label: "现价", align: "right", sortable: true },
  { key: "change_pct", label: "涨跌幅", align: "right", sortable: true },
  ...(props.showFavorite ? [{ key: "fav", label: "自选", align: "right" }] : []),
]);
</script>

<template>
  <DataTable :columns="columns" :rows="pageRows" :sort-key="sortKey" :sort-dir="sortDir"
    row-key="symbol" :selected-key="selectedSymbol" @sort="toggleSort" @select="emit('select', $event)">
    <template #cell-name="{ row }">
      <span class="stock-name">{{ row.name }}</span>
      <span v-if="row.quote_source === 'sim'" class="tag tag-muted sim-tag">模拟</span>
      <span class="mobile-code num">{{ row.symbol }}</span>
    </template>
    <template #cell-symbol="{ row }"><span class="symbol-badge">{{ row.symbol }}</span></template>
    <template #cell-price="{ row }"><span :class="trendClass(row.change)">{{ fmtMoney(row.price) }}</span></template>
    <template #cell-change_pct="{ row }">
      <span class="pct-pill" :class="trendClass(row.change_pct)">{{ fmtPct(row.change_pct) }}</span>
    </template>
    <template #cell-fav="{ row }">
      <button class="btn btn-sm fav-btn" :class="{ 'fav-on': favoriteIds.has(row.id) }"
        :disabled="pendingIds.includes(row.id)"
        :aria-pressed="favoriteIds.has(row.id)"
        :aria-label="favoriteIds.has(row.id) ? `移除自选 ${row.name}` : `加入自选 ${row.name}`"
        @click.stop="emit('toggle-fav', row)">
        <span v-if="pendingIds.includes(row.id)" class="spinner"></span>
        <AppIcon v-else :name="favoriteIds.has(row.id) ? 'star-filled' : 'star'" :size="13" />
        <span class="fav-label">{{ favoriteIds.has(row.id) ? "移除" : "加入自选" }}</span>
      </button>
    </template>
    <template #empty>
      <div class="empty">
        <div class="title">没有匹配的股票</div>
        <div class="sub">换个代码或名称试试,也可以直接在上方搜索框输入。</div>
      </div>
    </template>
  </DataTable>
  <DataPagination :page="page" :page-size="pageSize" :total="total" :total-pages="totalPages"
    @update:page="setPage" @update:page-size="setPageSize" />
</template>

<style scoped>
.stock-name { font-weight: 600; }
.sim-tag { margin-left: 6px; }
.mobile-code { display: none; }
.fav-btn { min-width: 76px; }
.fav-on { color: var(--gold); border-color: var(--gold-border); background: var(--gold-bg); }
.fav-on:hover { color: var(--gold); border-color: var(--gold); background: var(--gold-bg); }
@media (max-width: 600px) {
  .mobile-code { display: inline; margin-left: 6px; font-size: var(--fs-xs); color: var(--text-3); }
  .fav-btn { min-width: 34px; padding: 4px 8px; }
  .fav-label { display: none; }
}
</style>