<script setup>
import { onMounted, onUnmounted } from "vue";
import AppHeader from "./components/AppHeader.vue";
import TickerTape from "./components/TickerTape.vue";
import ToastHost from "./components/ToastHost.vue";
import { useMarketStore } from "./stores/market";

const market = useMarketStore();
onMounted(() => market.startPolling());
onUnmounted(() => market.stopPolling());
</script>

<template>
  <div class="aurora-bg" aria-hidden="true"></div>
  <AppHeader />
  <TickerTape />
  <main class="app-main">
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" :key="$route.fullPath" />
      </transition>
    </router-view>
  </main>
  <footer class="app-footer">
    FinQuant 模拟交易终端 · 所有行情与资金均为模拟数据,仅供学习 ·
    <a href="/admin/" target="_blank" rel="noopener">后台管理</a>
  </footer>
  <ToastHost />
</template>

<style scoped>
.app-main { min-height: calc(100vh - 170px); }
.app-footer {
  max-width: 1240px;
  margin: 0 auto;
  padding: 18px 20px 26px;
  color: var(--text-3);
  font-size: 12px;
  text-align: center;
}
</style>
