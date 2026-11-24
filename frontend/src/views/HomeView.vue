<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useMarketStore } from "../stores/market";
import { fetchMarketPulse } from "../api";
import IndexCard from "../components/IndexCard.vue";
import KlineChart from "../components/KlineChart.vue";
import StockTable from "../components/StockTable.vue";
import MarketPulse from "../components/MarketPulse.vue";

const auth = useAuthStore();
const market = useMarketStore();
const route = useRoute();

const selected = ref(null);
const search = ref("");
// 深链 ?symbol= 同步初始化,避免默认指数与目标标的两次请求竞态
const klineTarget = ref({ symbol: String(route.query.symbol || "") || "sh000001", name: "" });

const pulse = ref(null); // 市场脉冲(60s 刷新,服务端亦有 TTL 缓存)
let pulseTimer = null;

const realIndices = computed(() => market.indices.filter((i) => i.symbol));

const filteredStocks = computed(() => {
  const kw = search.value.trim().toLowerCase();
  if (!kw) return market.activeStocks;
  return market.activeStocks.filter((s) => s.symbol.toLowerCase().includes(kw) || s.name.includes(kw));
});

async function loadPulse() {
  if (document.hidden) return;
  try {
    pulse.value = await fetchMarketPulse();
  } catch { /* 脉冲失败不阻塞首页 */ }
}

function selectStock(stock) {
  selected.value = stock;
  klineTarget.value = { symbol: stock.symbol, name: stock.name };
}
function selectIndex(idx) {
  klineTarget.value = { symbol: idx.symbol, name: idx.name };
}

onMounted(async () => {
  if (!market.stocks.length) await market.refreshAll();
  if (auth.isLoggedIn && !market.favorites.length) {
    market.fetchFavorites().catch(() => {});  // K 线自选日期标注依赖
  }
  // 补全深链标的名称;无深链时默认上证指数
  const qs = String(route.query.symbol || "");
  const target = market.activeStocks.find((s) => s.symbol === qs)
    || market.indices.find((i) => i.symbol === qs);
  if (target) {
    klineTarget.value = { symbol: target.symbol, name: target.name };
    if (target.kind !== "index") selected.value = target;
  } else if (klineTarget.value.symbol === "sh000001") {
    klineTarget.value = { symbol: "sh000001", name: "上证指数" };
  }
  if (!selected.value && market.activeStocks.length) selected.value = market.activeStocks[0];
  loadPulse();
  pulseTimer = setInterval(loadPulse, 60000);
});
onUnmounted(() => clearInterval(pulseTimer));
</script>

<template>
  <div class="page">
    <!-- Hero -->
    <section class="hero panel-gradient">
      <div class="hero-inner panel" style="border: none">
        <div class="hero-text">
          <h1 class="hero-title">
            量化研究<em>终端</em><br />先看大盘状态再选策略
          </h1>
          <p class="hero-sub">
            真实行情 · 市场脉冲推断 · 策略有效性对比 · AI 投研助手
          </p>
          <div v-if="!auth.isLoggedIn" class="hero-actions">
            <router-link class="btn btn-primary" :to="{ name: 'register' }">注册开始研究</router-link>
            <router-link class="btn" :to="{ name: 'login' }">登录</router-link>
          </div>
          <div v-else class="hero-actions">
            <router-link class="btn btn-primary" :to="{ name: 'backtest' }">量化回测</router-link>
            <router-link class="btn" :to="{ name: 'favorites' }">我的自选</router-link>
          </div>
        </div>
        <MarketPulse :pulse="pulse" compact />
      </div>
    </section>

    <!-- 市场脉冲 -->
    <section class="section-gap">
      <MarketPulse :pulse="pulse" />
    </section>

    <!-- 指数 -->
    <section class="grid-3 section-gap">
      <IndexCard v-for="idx in market.indices" :key="idx.name" :index="idx" />
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 118px"></div>
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 118px"></div>
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 118px"></div>
    </section>

    <!-- K 线 -->
    <section class="panel section-gap">
      <div class="kline-tabs">
        <button v-for="idx in realIndices" :key="idx.symbol" class="btn btn-sm kline-chip"
          :class="{ 'chip-on': klineTarget.symbol === idx.symbol }" @click="selectIndex(idx)">
          {{ idx.name }}
        </button>
        <button v-if="selected" class="btn btn-sm kline-chip"
          :class="{ 'chip-on': klineTarget.symbol === selected.symbol }"
          @click="klineTarget = { symbol: selected.symbol, name: selected.name }">
          {{ selected.name }}
        </button>
      </div>
      <KlineChart v-if="klineTarget?.symbol" :symbol="klineTarget.symbol" :name="klineTarget.name" :height="380" />
      <div v-else class="panel skeleton" style="height: 400px"></div>
    </section>

    <!-- 标的列表 -->
    <section class="panel section-gap">
      <h3 class="panel-title">
        市场标的
        <input v-model="search" class="input search" type="search" placeholder="搜索代码 / 名称…" aria-label="搜索标的" />
      </h3>
      <StockTable
        :stocks="filteredStocks"
        :favorite-ids="market.favoriteStockIds"
        :selected-symbol="selected?.symbol"
        @select="selectStock"
        @toggle-fav="market.toggleFavorite"
      />
    </section>
  </div>
</template>

<style scoped>
.hero-inner { display: flex; gap: 28px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
.hero-title {
  font-size: clamp(26px, 4vw, 40px);
  line-height: 1.25;
  letter-spacing: 0.01em;
}
.hero-title em {
  font-style: normal;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 0 14px rgba(34, 211, 238, 0.35));
}
.hero-sub { color: var(--text-2); margin: 10px 0 18px; }
.hero-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.search { max-width: 230px; font-size: 13px; padding: 7px 12px; }
.kline-tabs { display: flex; gap: 7px; margin-bottom: 10px; flex-wrap: wrap; }
.kline-chip.chip-on { border-color: var(--brand-a); color: var(--brand-a); box-shadow: var(--glow-brand); }
@media (max-width: 900px) {
  .hero-inner { gap: 16px; }
}
</style>