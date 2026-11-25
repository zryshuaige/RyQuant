<script setup>
import { onMounted, onUnmounted } from "vue";
import AppHeader from "./components/AppHeader.vue";
import ToastHost from "./components/ToastHost.vue";
import { useMarketStore } from "./stores/market";

const market = useMarketStore();
onMounted(() => market.startPolling());
onUnmounted(() => market.stopPolling());
</script>

<template>
  <a class="skip-link" href="#main">跳到主要内容</a>
  <AppHeader />
  <main id="main" class="app-main" tabindex="-1">
    <router-view v-slot="{ Component }">
      <transition name="page" mode="out-in">
        <component :is="Component" :key="$route.name" />
      </transition>
    </router-view>
  </main>
  <footer class="app-footer">
    RyQuant · 量化研究工具 · 行情数据来自腾讯财经 · 仅供研究学习,不构成投资建议
  </footer>
  <ToastHost />
</template>

<style scoped>
.app-main { min-height: calc(100vh - 140px); outline: none; }
@media (max-width: 860px) {
  .app-main { padding-bottom: 70px; }
  .app-footer { padding-bottom: 84px; }
}
.app-footer {
  max-width: 1240px;
  margin: 0 auto;
  padding: 16px 20px 24px;
  border-top: 1px solid var(--border);
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.06em;
  text-align: center;
}
</style>