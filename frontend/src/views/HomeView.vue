<script setup>
import { ref, computed, onMounted } from "vue";
import { useAuthStore } from "../stores/auth";
import { useMarketStore } from "../stores/market";
import { fetchNews, fetchPositions } from "../api";
import IndexCard from "../components/IndexCard.vue";
import KlineChart from "../components/KlineChart.vue";
import StockTable from "../components/StockTable.vue";
import OrderModal from "../components/OrderModal.vue";
import AnimatedNumber from "../components/AnimatedNumber.vue";
import { fmtMoney, fmtSigned, trendClass, fmtDateTime } from "../utils/format";

const auth = useAuthStore();
const market = useMarketStore();

const selected = ref(null);
const orderStock = ref(null);
const orderVisible = ref(false);
const search = ref("");
const klineTarget = ref({ symbol: "sh000001", name: "上证指数" }); // 默认看上证指数

const news = ref([]);
const account = ref(null); // 持仓汇总(已登录时展示)

const realIndices = computed(() => market.indices.filter((i) => i.symbol));

const filteredStocks = computed(() => {
  const kw = search.value.trim().toLowerCase();
  if (!kw) return market.activeStocks;
  return market.activeStocks.filter((s) => s.symbol.toLowerCase().includes(kw) || s.name.includes(kw));
});

const trend = computed(() => trendClass(account.value?.total_unrealized_pl ?? 0));

function openOrder(stock) {
  orderStock.value = stock;
  orderVisible.value = true;
}
function selectStock(stock) {
  selected.value = stock;
  klineTarget.value = { symbol: stock.symbol, name: stock.name };
}
function selectIndex(idx) {
  klineTarget.value = { symbol: idx.symbol, name: idx.name };
}
async function onPlaced() {
  if (auth.isLoggedIn) {
    try {
      account.value = await fetchPositions();
    } catch { /* 忽略 */ }
  }
}

onMounted(async () => {
  if (!market.stocks.length) await market.refreshAll();
  if (!selected.value && market.activeStocks.length) selected.value = market.activeStocks[0];
  fetchNews().then((list) => (news.value = list)).catch(() => {});
  if (auth.isLoggedIn) {
    fetchPositions().then((d) => (account.value = d)).catch(() => {});
  }
});
</script>

<template>
  <div class="page">
    <!-- Hero -->
    <section class="hero panel-gradient">
      <div class="hero-inner panel" style="border: none">
        <div class="hero-text">
          <h1 class="hero-title">
            模拟交易<em>实战场</em><br />策略先跑一遍再进场
          </h1>
          <p class="hero-sub">
            实时模拟行情 · 真实撮合与费用 · VIP 量化回测 · AI 投研助手
          </p>
          <div class="hero-actions" v-if="!auth.isLoggedIn">
            <router-link class="btn btn-primary" :to="{ name: 'register' }">开启 VIP</router-link>
            <router-link class="btn" :to="{ name: 'login' }">登录</router-link>
          </div>
          <div v-else-if="!auth.isVip" class="hero-actions">
            <router-link class="btn btn-primary" :to="{ name: 'backtest' }">开启 VIP</router-link>
            <router-link class="btn" :to="{ name: 'positions' }">查看持仓</router-link>
          </div>
          <div v-else class="hero-actions">
            <button class="btn btn-primary" @click="selected && openOrder(selected)">快速下单</button>
            <router-link class="btn" :to="{ name: 'positions' }">查看持仓</router-link>
          </div>
        </div>

        <div v-if="auth.isLoggedIn && account" class="hero-stats">
          <div class="stat">
            <span class="stat-label">总资产</span>
            <AnimatedNumber class="stat-value" :value="account.total_asset ?? 0" />
          </div>
          <div class="stat">
            <span class="stat-label">可用资金</span>
            <AnimatedNumber class="stat-value" :value="Number(account.cash?.balance ?? 0)" />
          </div>
          <div class="stat">
            <span class="stat-label">持仓市值</span>
            <AnimatedNumber class="stat-value" :value="account.total_market_value ?? 0" />
          </div>
          <div class="stat">
            <span class="stat-label">浮动盈亏</span>
            <AnimatedNumber class="stat-value" :class="trend" :value="account.total_unrealized_pl ?? 0" />
          </div>
        </div>
      </div>
    </section>

    <!-- 指数 -->
    <section class="grid-3 section-gap">
      <IndexCard v-for="idx in market.indices" :key="idx.name" :index="idx" />
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 118px"></div>
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 118px"></div>
      <div v-if="!market.indices.length" class="panel skeleton" style="height: 118px"></div>
    </section>

    <!-- K 线 + 资讯 -->
    <section class="grid-2 section-gap media-grid">
      <div class="panel">
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
        <KlineChart v-if="klineTarget?.symbol" :symbol="klineTarget.symbol" :name="klineTarget.name" :height="360" />
        <div v-else class="panel skeleton" style="height: 400px"></div>
      </div>
      <div class="panel">
        <h3 class="panel-title">
          财经快讯
          <span class="hint">模拟数据</span>
        </h3>
        <ul class="news-list">
          <li v-for="n in news" :key="n.id" class="news-item">
            <span class="news-dot"></span>
            <div>
              <div class="news-title">{{ n.title }}</div>
              <div class="news-meta">{{ n.source }} · {{ fmtDateTime(n.ts) }}</div>
            </div>
          </li>
          <li v-if="!news.length" class="news-item"><div class="news-meta">加载中…</div></li>
        </ul>
      </div>
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
        @order="openOrder"
        @select="selectStock"
        @toggle-fav="market.toggleFavorite"
      />
    </section>

    <OrderModal v-model="orderVisible" :stock="orderStock" @placed="onPlaced" />
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
.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(140px, 1fr));
  gap: 12px;
}
.stat {
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--inset-bg);
  min-width: 150px;
}
.stat-label { display: block; font-size: 12px; color: var(--text-3); margin-bottom: 4px; }
.stat-value { font-size: 21px; font-weight: 800; }
.media-grid { grid-template-columns: 1.5fr 1fr; }
.news-list { list-style: none; margin: 0; padding: 0; }
.news-item { display: flex; gap: 10px; padding: 11px 2px; border-bottom: 1px dashed var(--border); }
.news-item:last-child { border-bottom: none; }
.news-dot { width: 7px; height: 7px; margin-top: 8px; border-radius: 50%; background: var(--brand-a); flex: none; box-shadow: var(--glow-brand); }
.news-title { font-size: 13.5px; font-weight: 600; }
.news-meta { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.search { max-width: 230px; font-size: 13px; padding: 7px 12px; }
.kline-tabs { display: flex; gap: 7px; margin-bottom: 10px; flex-wrap: wrap; }
.kline-chip.chip-on { border-color: var(--brand-a); color: var(--brand-a); box-shadow: var(--glow-brand); }
@media (max-width: 900px) {
  .media-grid { grid-template-columns: 1fr; }
  .hero-stats { width: 100%; grid-template-columns: repeat(2, 1fr); }
}
</style>
