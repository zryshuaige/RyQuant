<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useMarketStore } from "../stores/market";
import { fetchMarketPulse } from "../api";
import { toast } from "../composables/useToast";
import IndexCard from "../components/IndexCard.vue";
import KlineChart from "../components/KlineChart.vue";
import StockTable from "../components/StockTable.vue";
import MarketStatus from "../components/MarketStatus.vue";
import WatchlistRail from "../components/WatchlistRail.vue";
import SymbolSearch from "../components/SymbolSearch.vue";
import AppIcon from "../components/AppIcon.vue";

const auth = useAuthStore();
const market = useMarketStore();
const route = useRoute();
const router = useRouter();

const selectedSymbol = ref("");
const klineTarget = ref({ symbol: String(route.query.symbol || "") || "sh000001", name: "" });
const pulse = ref(null);
const pulseLoading = ref(true);
let pulseTimer = null;
let summaryTimer = null;

const realIndices = computed(() => market.indices.filter((i) => i.symbol));
const klineStock = computed(() =>
  market.stocks.find((s) => s.symbol === klineTarget.value.symbol) || null
);
const isFavorite = computed(() => Boolean(klineStock.value && market.favoriteStockIds.has(klineStock.value.id)));
const favoritePending = computed(() =>
  Boolean(klineStock.value && market.pendingFavoriteIds.includes(klineStock.value.id))
);
const sourceText = computed(() => {
  if (market.error || market.stale) return "行情已过期";
  return pulse.value?.quote_source === "real" ? "腾讯实时" : "模拟行情";
});
const sourceClass = computed(() => {
  if (market.error || market.stale) return "stale";
  return pulse.value?.quote_source === "real" ? "" : "sim";
});
const updatedText = computed(() => {
  if (market.lastUpdated) {
    return new Date(market.lastUpdated).toLocaleTimeString("zh-CN", { hour12: false });
  }
  if (pulse.value?.generated_at) {
    return new Date(pulse.value.generated_at).toLocaleTimeString("zh-CN", { hour12: false });
  }
  return "--:--:--";
});

async function loadPulse() {
  if (document.hidden) return;
  try {
    pulse.value = await fetchMarketPulse();
  } catch { /* 顶部状态会提示行情过期 */ }
  finally { pulseLoading.value = false; }
}

async function loadWatchlist() {
  if (!auth.isLoggedIn) return;
  if (!market.favorites.length) await market.fetchFavorites();
  await market.fetchFavoritesSummary();
}

function resolveTargetName(symbol) {
  const stock = market.stocks.find((s) => s.symbol === symbol);
  const index = market.indices.find((i) => i.symbol === symbol);
  return { symbol, name: stock?.name || index?.name || "" };
}

function scrollToKline() {
  nextTick(() => {
    const el = document.getElementById("kline-panel");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function openTarget(target, { scroll = true } = {}) {
  klineTarget.value = {
    symbol: target.symbol,
    name: target.name || resolveTargetName(target.symbol).name,
  };
  const isIndex = target.kind === "index" || market.indices.some((i) => i.symbol === target.symbol);
  selectedSymbol.value = isIndex ? "" : target.symbol;
  if (route.query.symbol !== target.symbol) {
    router.replace({ name: "home", query: { symbol: target.symbol } });
  }
  if (scroll) scrollToKline();
}

function selectStock(stock) { openTarget(stock); }
function selectIndex(index) {
  if (!index.symbol) return;
  openTarget({ ...index, kind: "index" });
}

async function toggleFavorite(stock) {
  if (!auth.isLoggedIn) {
    toast.info("登录后可添加自选");
    router.push({ name: "login", query: { next: route.fullPath } });
    return;
  }
  await market.toggleFavorite(stock);
}

async function toggleKlineFavorite() {
  if (!klineStock.value) return;
  if (!auth.isLoggedIn) {
    toast.info("登录后可添加自选");
    router.push({ name: "login", query: { next: route.fullPath } });
    return;
  }
  await market.toggleFavorite(klineStock.value);
}

function goBacktest(strategyId) {
  const anchor = pulse.value?.anchor?.symbol || "sh000001";
  router.push({ name: "backtest", query: { symbol: anchor, strategy: strategyId, autorun: "1" } });
}
function goCompare() {
  const anchor = pulse.value?.anchor?.symbol || "sh000001";
  router.push({ name: "backtest", query: { tab: "compare", symbol: anchor, autorun: "1" } });
}
async function refreshAll() {
  await Promise.allSettled([market.refreshAll(), loadPulse()]);
}

onMounted(async () => {
  await market.ensureLoaded();
  const qs = String(route.query.symbol || "");
  if (qs) {
    const target = resolveTargetName(qs);
    if (target.name) klineTarget.value = target;
    if (market.stocks.some((s) => s.symbol === qs)) selectedSymbol.value = qs;
  } else {
    klineTarget.value = { symbol: "sh000001", name: resolveTargetName("sh000001").name || "上证指数" };
  }
  loadPulse();
  loadWatchlist();
  pulseTimer = setInterval(loadPulse, 60000);
  summaryTimer = setInterval(() => {
    if (!document.hidden && auth.isLoggedIn) market.fetchFavoritesSummary();
  }, 60000);
  if (qs) scrollToKline();
});
onUnmounted(() => {
  clearInterval(pulseTimer);
  clearInterval(summaryTimer);
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">行情总览</h1>
        <p class="page-sub">看大盘状态,选当前更合适的策略,再回到 K 线与自选验证。</p>
      </div>
      <div class="market-state">
        <span class="status-dot" :class="sourceClass"></span>
        <span>{{ sourceText }}</span>
        <span class="state-time num">{{ updatedText }}</span>
        <button class="icon-btn" aria-label="刷新行情" title="刷新行情" @click="refreshAll">
          <AppIcon name="refresh" :size="15" />
        </button>
      </div>
    </div>

    <MarketStatus :pulse="pulse" :loading="pulseLoading" @backtest="goBacktest" @compare="goCompare" />

    <section class="grid-3 section-gap indices">
      <IndexCard v-for="idx in market.indices" :key="idx.name" :index="idx" @select="selectIndex" />
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 96px"></div>
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 96px"></div>
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 96px"></div>
    </section>

    <section class="home-grid section-gap">
      <div id="kline-panel" class="panel chart-panel">
        <div class="chart-tabs">
          <button v-if="klineStock" class="btn btn-sm chip chip-on" aria-pressed="true"
            :aria-label="`当前标的 ${klineStock.name}`" @click="selectStock(klineStock)">
            {{ klineStock.name }}
          </button>
          <button v-for="idx in realIndices" :key="idx.symbol" class="btn btn-sm chip"
            :class="{ 'chip-on': klineTarget.symbol === idx.symbol }"
            :aria-pressed="klineTarget.symbol === idx.symbol" @click="selectIndex(idx)">
            {{ idx.name }}
          </button>
        </div>
        <KlineChart v-if="klineTarget.symbol" :symbol="klineTarget.symbol" :name="klineTarget.name"
          :height="360" :favorite="isFavorite" :favorite-pending="favoritePending"
          :favorite-enabled="Boolean(klineStock)" @toggle-favorite="toggleKlineFavorite" />
      </div>
      <WatchlistRail :summary="market.favoritesSummary" :loading="market.summaryLoading" @select="selectStock" />
    </section>

    <section class="panel section-gap">
      <div class="panel-head table-head">
        <div>
          <h2 class="panel-title" style="margin: 0">股票列表</h2>
          <p class="panel-sub">{{ market.activeStocks.length }} 只股票 · 输入名称或代码可添加任意 A 股</p>
        </div>
        <SymbolSearch placeholder="搜索代码 / 名称,添加任意股票" @select="selectStock" />
      </div>
      <div v-if="market.error && !market.stocks.length" class="empty">
        <div class="title">行情加载失败</div>
        <div class="sub">{{ market.error }}</div>
        <button class="btn btn-sm section-gap" @click="refreshAll">重试</button>
      </div>
      <StockTable v-else :stocks="market.activeStocks" :favorite-ids="market.favoriteStockIds"
        :pending-ids="market.pendingFavoriteIds" :selected-symbol="selectedSymbol"
        @select="selectStock" @toggle-fav="toggleFavorite" />
    </section>
  </div>
</template>

<style scoped>
.market-state { display: flex; align-items: center; gap: 6px; color: var(--text-2); font-size: var(--fs-xs); }
.state-time { color: var(--text-3); }
.indices { margin-top: var(--space-4); }
.home-grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--space-4); align-items: stretch; }
.chart-panel { scroll-margin-top: 72px; padding: 16px; }
.chart-tabs { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
.chip { background: transparent; }
.chip-on { border-color: var(--accent); color: var(--accent); background: var(--accent-bg); }
.table-head { align-items: center; }
.panel-sub { color: var(--text-3); font-size: var(--fs-xs); margin-top: 3px; }
@media (max-width: 1000px) {
  .home-grid { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .indices { display: flex; overflow-x: auto; gap: 8px; scrollbar-width: none; }
  .indices::-webkit-scrollbar { display: none; }
  .indices :deep(.index-card) { flex: 0 0 176px; }
}
@media (max-width: 700px) {
  .market-state { width: 100%; }
  .table-head { align-items: flex-start; flex-direction: column; }
  .table-head :deep(.symbol-search) { width: 100%; }
}
</style>