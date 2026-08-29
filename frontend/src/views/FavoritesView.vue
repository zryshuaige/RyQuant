<script setup>
import { ref, computed, onMounted } from "vue";
import { useMarketStore } from "../stores/market";
import StockTable from "../components/StockTable.vue";
import OrderModal from "../components/OrderModal.vue";
import EmptyState from "../components/EmptyState.vue";
import { fetchFavorites } from "../api";
import { toast } from "../composables/useToast";

const market = useMarketStore();
const orderStock = ref(null);
const orderVisible = ref(false);
const search = ref("");

const favStocks = computed(() => market.favorites.map((f) => f.stock));
const favIds = computed(() => new Set(favStocks.value.map((s) => s.id)));
const others = computed(() => {
  const kw = search.value.trim().toLowerCase();
  return market.activeStocks.filter(
    (s) => !favIds.value.has(s.id) && (!kw || s.symbol.toLowerCase().includes(kw) || s.name.includes(kw))
  );
});

function openOrder(stock) {
  orderStock.value = stock;
  orderVisible.value = true;
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
        <span class="hint">{{ favStocks.length }} 只 · 点击行查看走势</span>
      </h3>
      <StockTable
        v-if="favStocks.length"
        :stocks="favStocks"
        :favorite-ids="favIds"
        @order="openOrder"
        @toggle-fav="market.toggleFavorite"
        @select="openOrder"
      />
      <EmptyState v-else glyph="⭐" title="还没有自选股" sub="在下方市场中点击「加自选」,价格异动一目了然" />
    </section>

    <section class="panel section-gap">
      <h3 class="panel-title">
        全部标的
        <input v-model="search" class="input search" type="search" placeholder="搜索代码 / 名称…" aria-label="搜索标的" />
      </h3>
      <StockTable
        :stocks="others"
        :favorite-ids="favIds"
        @order="openOrder"
        @toggle-fav="market.toggleFavorite"
      />
    </section>

    <OrderModal v-model="orderVisible" :stock="orderStock" />
  </div>
</template>

<style scoped>
.search { max-width: 230px; font-size: 13px; padding: 7px 12px; }
</style>
