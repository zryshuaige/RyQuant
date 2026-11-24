<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useMarketStore } from "../stores/market";
import StockTable from "../components/StockTable.vue";
import EmptyState from "../components/EmptyState.vue";
import { fetchFavorites } from "../api";
import { toast } from "../composables/useToast";

const market = useMarketStore();
const router = useRouter();
const search = ref("");

const favStocks = computed(() => market.favorites.map((f) => f.stock));
const favIds = computed(() => new Set(favStocks.value.map((s) => s.id)));
const joinedDates = computed(() =>
  Object.fromEntries(market.favorites.map((f) => [f.stock.symbol, f.created_at]))
);
const others = computed(() => {
  const kw = search.value.trim().toLowerCase();
  return market.activeStocks.filter(
    (s) => !favIds.value.has(s.id) && (!kw || s.symbol.toLowerCase().includes(kw) || s.name.includes(kw))
  );
});

function viewKline(stock) {
  router.push({ name: "home", query: { symbol: stock.symbol } });
}

onMounted(async () => {
  if (!market.stocks.length) await market.refreshAll();
  try {
    market.favorites = await fetchFavorites();
  } catch (e) {
    toast.error(e.friendlyMessage || "自选加载失败");
  }
});
</script>

<template>
  <div class="page">
    <section class="panel">
      <h3 class="panel-title">
        我的自选
        <span class="hint">{{ favStocks.length }} 只 · 点击行跳转 K 线(标注加入日期)</span>
      </h3>
      <StockTable
        v-if="favStocks.length"
        :stocks="favStocks"
        :favorite-ids="favIds"
        :joined-dates="joinedDates"
        @toggle-fav="market.toggleFavorite"
        @select="viewKline"
      />
      <EmptyState v-else icon="star" title="还没有自选股" sub="在下方市场中点击「加自选」,K 线会醒目标注加入日期" />
    </section>

    <section class="panel section-gap">
      <h3 class="panel-title">
        全部标的
        <input v-model="search" class="input search" type="search" placeholder="搜索代码 / 名称…" aria-label="搜索标的" />
      </h3>
      <StockTable
        :stocks="others"
        :favorite-ids="favIds"
        @toggle-fav="market.toggleFavorite"
        @select="viewKline"
      />
    </section>
  </div>
</template>

<style scoped>
.search { max-width: 230px; font-size: 13px; padding: 7px 12px; }
</style>