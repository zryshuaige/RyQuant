<script setup>
import { computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useMarketStore } from "../stores/market";
import { useAuthStore } from "../stores/auth";
import { fmtMoney, fmtSigned } from "../utils/format";
import { usePagedSort } from "../composables/usePagedSort";
import { toast } from "../composables/useToast";
import SymbolSearch from "../components/SymbolSearch.vue";
import Sparkline from "../components/Sparkline.vue";
import DataTable from "../components/DataTable.vue";
import DataPagination from "../components/DataPagination.vue";
import AppIcon from "../components/AppIcon.vue";

const market = useMarketStore();
const auth = useAuthStore();
const router = useRouter();
let timer = null;

const summary = computed(() => market.favoritesSummary);
const items = computed(() => summary.value?.items || []);
const benchmarkName = computed(() => summary.value?.benchmark?.name || "上证指数");
const loading = computed(() => market.summaryLoading && !summary.value);

const {
  pageRows, page, pageSize, total, totalPages,
  sortKey, sortDir, toggleSort, setPage, setPageSize,
} = usePagedSort(items, { pageSize: 10 });

const columns = computed(() => [
  { key: "name", label: "名称" },
  { key: "joined_at", label: "加入日期", mono: true, sortable: true },
  { key: "join_price", label: "加入价", align: "right", sortable: true },
  { key: "current_price", label: "现价", align: "right" },
  { key: "return_pct", label: "加入以来", align: "right", sortable: true },
  { key: "benchmark_return_pct", label: `同期${benchmarkName.value}`, align: "right" },
  { key: "excess_pct", label: "超额", align: "right", sortable: true },
  { key: "series", label: "走势" },
  { key: "action", label: "操作", align: "right" },
]);

async function refresh() {
  await market.fetchFavorites();
  await market.fetchFavoritesSummary();
}

async function addStock(stock) {
  if (!stock?.id) return;
  if (market.favoriteStockIds.has(stock.id)) {
    toast.info(`${stock.name} 已在自选中`);
    return;
  }
  await market.toggleFavorite(stock);
}

async function removeStock(item) {
  await market.toggleFavorite(item.stock);
}

function viewKline(item) {
  router.push({ name: "home", query: { symbol: item.stock.symbol } });
}

function onVisibility() {
  if (!document.hidden) refresh();
}

onMounted(async () => {
  await market.ensureLoaded();
  if (!auth.isLoggedIn) return;
  await refresh();
  timer = setInterval(() => { if (!document.hidden) market.fetchFavoritesSummary(); }, 60000);
  document.addEventListener("visibilitychange", onVisibility);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
  document.removeEventListener("visibilitychange", onVisibility);
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">自选跟踪</h1>
        <p class="page-sub">记录加入自选后的表现,并与同期{{ benchmarkName }}对比。</p>
      </div>
      <SymbolSearch placeholder="输入名称或代码,添加到自选" @select="addStock" />
    </div>

    <div class="kpi-grid">
      <div class="kpi">
        <span class="kpi-label">自选数量</span>
        <span class="kpi-value">{{ summary?.count ?? "--" }}<small class="kpi-unit">只</small></span>
        <span class="kpi-sub">加入日期已记录</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">平均加入以来</span>
        <span class="kpi-value" :class="(summary?.avg_return_pct ?? 0) >= 0 ? 'up' : 'down'">
          {{ summary ? fmtSigned(summary.avg_return_pct) + "%" : "--" }}
        </span>
        <span class="kpi-sub">等权平均</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">跑赢{{ benchmarkName }}</span>
        <span class="kpi-value">{{ summary ? `${summary.beat_count} / ${summary.count}` : "--" }}</span>
        <span class="kpi-sub">按超额收益统计</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">表现最佳</span>
        <span class="kpi-value best">
          {{ summary?.best?.name || "--" }}
          <small v-if="summary?.best" class="num" :class="summary.best.return_pct >= 0 ? 'up' : 'down'">
            {{ fmtSigned(summary.best.return_pct) }}%
          </small>
        </span>
        <span class="kpi-sub">加入以来</span>
      </div>
    </div>

    <section class="panel section-gap">
      <div class="panel-head">
        <div>
          <h2 class="panel-title" style="margin: 0">加入以来表现</h2>
          <p class="panel-sub">加入价取加入日后首个交易日收盘;现价随行情更新。</p>
        </div>
        <button class="icon-btn" aria-label="刷新自选表现" title="刷新" @click="refresh">
          <AppIcon name="refresh" :size="15" />
        </button>
      </div>

      <div v-if="loading" class="stack">
        <div v-for="i in 4" :key="i" class="skeleton" style="height: 46px"></div>
      </div>

      <template v-else-if="items.length">
        <div class="fav-table">
          <DataTable :columns="columns" :rows="pageRows" :sort-key="sortKey" :sort-dir="sortDir"
            :row-key="(item) => item.stock.id" @sort="toggleSort" @select="viewKline">
            <template #cell-name="{ row }">
              <span class="name-cell"><b>{{ row.stock.name }}</b><span class="symbol-badge">{{ row.stock.symbol }}</span></span>
            </template>
            <template #cell-join_price="{ row }">{{ fmtMoney(row.join_price) }}</template>
            <template #cell-current_price="{ row }">{{ fmtMoney(row.current_price) }}</template>
            <template #cell-return_pct="{ row }">
              <span :class="row.return_pct >= 0 ? 'up' : 'down'">{{ fmtSigned(row.return_pct) }}%</span>
            </template>
            <template #cell-benchmark_return_pct="{ row }">
              <span :class="row.benchmark_return_pct >= 0 ? 'up' : 'down'">{{ fmtSigned(row.benchmark_return_pct) }}%</span>
            </template>
            <template #cell-excess_pct="{ row }">
              <span :class="row.excess_pct >= 0 ? 'up' : 'down'">{{ fmtSigned(row.excess_pct) }}%</span>
            </template>
            <template #cell-series="{ row }"><Sparkline :points="row.series" :width="92" :height="28" /></template>
            <template #cell-action="{ row }">
              <button class="btn btn-sm btn-danger" :disabled="market.pendingFavoriteIds.includes(row.stock.id)"
                :aria-label="`从自选移除 ${row.stock.name}`" @click.stop="removeStock(row)">
                <span v-if="market.pendingFavoriteIds.includes(row.stock.id)" class="spinner"></span>
                <AppIcon v-else name="trash" :size="13" />
                移除
              </button>
            </template>
          </DataTable>
        </div>

        <div class="fav-cards">
          <div v-for="item in pageRows" :key="item.stock.id" class="fav-card" tabindex="0"
            @click="viewKline(item)" @keydown.enter="viewKline(item)">
            <div class="fav-card-head">
              <span class="fav-name">{{ item.stock.name }}</span>
              <span class="symbol-badge">{{ item.stock.symbol }}</span>
              <b class="num fav-ret" :class="item.return_pct >= 0 ? 'up' : 'down'">{{ fmtSigned(item.return_pct) }}%</b>
            </div>
            <div class="fav-meta">
              加入 {{ item.joined_at }} · 加入价 {{ fmtMoney(item.join_price) }} → 现价 {{ fmtMoney(item.current_price) }}
            </div>
            <div class="fav-card-foot">
              <Sparkline :points="item.series" :width="84" :height="26" />
              <span class="num" :class="item.excess_pct >= 0 ? 'up' : 'down'">超额 {{ fmtSigned(item.excess_pct) }}%</span>
              <button class="btn btn-sm btn-danger" :disabled="market.pendingFavoriteIds.includes(item.stock.id)"
                :aria-label="`从自选移除 ${item.stock.name}`" @click.stop="removeStock(item)">
                <span v-if="market.pendingFavoriteIds.includes(item.stock.id)" class="spinner"></span>
                <AppIcon v-else name="trash" :size="13" />
                移除
              </button>
            </div>
          </div>
        </div>

        <DataPagination :page="page" :page-size="pageSize" :total="total" :total-pages="totalPages"
          @update:page="setPage" @update:page-size="setPageSize" />
      </template>

      <div v-else class="empty">
        <div class="title">还没有加入自选</div>
        <div class="sub">在上方输入代码或名称,加入后会记录当日价格,自动计算加入以来的收益、同期上证与超额收益,K 线也会标注加入日期。</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.kpi-value.best { display: flex; align-items: baseline; gap: 6px; font-size: var(--fs-xl); }
.kpi-value.best small { font-size: var(--fs-sm); font-weight: 700; }
.kpi-unit { font-size: var(--fs-sm); font-weight: 600; color: var(--text-3); margin-left: 4px; letter-spacing: 0; }
.panel-sub { color: var(--text-3); font-size: var(--fs-xs); margin-top: 3px; }
.name-cell { display: inline-flex; align-items: center; gap: 8px; }
.fav-cards { display: none; }
@media (max-width: 700px) {
  .fav-table { display: none; }
  .fav-cards { display: grid; gap: 8px; }
  .fav-card {
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--inset-bg-soft);
    cursor: pointer;
  }
  .fav-card:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .fav-card-head { display: flex; align-items: center; gap: 8px; }
  .fav-name { font-weight: 700; }
  .fav-ret { margin-left: auto; font-family: var(--font-display); font-size: var(--fs-lg); font-weight: 600; }
  .fav-meta { font-size: var(--fs-xs); color: var(--text-3); margin: 5px 0 8px; }
  .fav-card-foot { display: flex; align-items: center; gap: 10px; }
  .fav-card-foot > span { flex: 1; font-size: var(--fs-xs); }
  .page-head :deep(.symbol-search) { width: 100%; }
}
</style>