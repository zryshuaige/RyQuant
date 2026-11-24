<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { theme, toggleTheme } from "../composables/useTheme";
import AppIcon from "./AppIcon.vue";
import { toast } from "../composables/useToast";

const router = useRouter();
const auth = useAuthStore();
const menuOpen = ref(false);

const navItems = [
  { to: "/", label: "行情总览", exact: true },
  { to: "/favorites", label: "自选股" },
  { to: "/backtest", label: "量化回测" },
  { to: "/ai", label: "AI 助手" },
];

function logout() {
  auth.logout();
  toast.info("已退出登录");
  router.push({ name: "home" });
}
</script>

<template>
  <header class="header">
    <div class="header-inner">
      <router-link to="/" class="brand" aria-label="RyQuant 首页">
        <svg class="brand-mark" viewBox="0 0 32 32" width="26" height="26" aria-hidden="true">
          <defs>
            <linearGradient id="brand-g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#22d3ee" />
              <stop offset="1" stop-color="#8b5cf6" />
            </linearGradient>
          </defs>
          <path d="M5 23 L11 14 L17 18 L27 6" stroke="url(#brand-g)" stroke-width="3.4" fill="none"
            stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="27" cy="6" r="3.4" fill="url(#brand-g)" />
        </svg>
        <span class="brand-name">Ry<em>Quant</em></span>
      </router-link>

      <button class="btn btn-sm btn-ghost nav-burger" :aria-expanded="menuOpen" aria-label="打开导航"
        @click="menuOpen = !menuOpen">
        <AppIcon name="menu" :size="18" />
      </button>

      <nav class="nav" :class="{ open: menuOpen }" aria-label="主导航">
        <router-link v-for="item in navItems" :key="item.to" :to="item.to"
          class="nav-link" :class="{ exact: item.exact }" @click="menuOpen = false">
          {{ item.label }}
        </router-link>
      </nav>

      <div class="auth-area">
        <button class="btn btn-sm btn-ghost theme-toggle" :title="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          :aria-label="theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'" @click="toggleTheme">
          <AppIcon :name="theme === 'dark' ? 'sun' : 'moon'" :size="15" />
        </button>
        <template v-if="auth.isLoggedIn">
          <span class="user-chip" :title="auth.user?.email">
            <span class="avatar">{{ auth.username.slice(0, 1).toUpperCase() }}</span>
            {{ auth.username }}
          </span>
          <button class="btn btn-sm btn-ghost" @click="logout">退出</button>
        </template>
        <template v-else>
          <router-link class="btn btn-sm btn-ghost" :to="{ name: 'login' }">登录</router-link>
          <router-link class="btn btn-sm btn-primary" :to="{ name: 'register' }">注册</router-link>
        </template>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  background: var(--header-bg);
  border-bottom: 1px solid var(--border);
}
.header-inner {
  max-width: 1240px;
  margin: 0 auto;
  padding: 0 20px;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 22px;
}
.brand { display: flex; align-items: center; gap: 9px; }
.brand-name {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: 0.02em;
  background: linear-gradient(120deg, #e9eef8 30%, #22d3ee 55%, #8b5cf6 80%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.brand-name em { font-style: normal; }
.nav { display: flex; gap: 4px; flex: 1; flex-wrap: nowrap; overflow-x: auto; }
.nav-link {
  position: relative;
  padding: 7px 13px;
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  transition: color 0.2s, background 0.2s;
}
.nav-link:hover { color: var(--text-1); background: var(--hover-bg); }
.nav-link.router-link-active:not(.exact) { color: var(--text-1); }
.nav-link.router-link-exact-active,
.nav-link.exact.router-link-active { color: var(--text-1); }
.nav-link.router-link-active::after {
  content: "";
  position: absolute;
  left: 12px; right: 12px; bottom: 1px;
  height: 2px;
  border-radius: 2px;
  background: var(--brand-grad);
  box-shadow: var(--glow-brand);
}
.vip-dot { color: var(--gold); font-size: 8px; vertical-align: 2px; margin-left: 2px; }
.auth-area { display: flex; align-items: center; gap: 9px; }
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.avatar {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #07101c;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.gold-text { color: var(--gold); font-weight: 800; }
.nav-burger { display: none; margin-left: auto; }
@media (max-width: 860px) {
  .header-inner { gap: 10px; padding: 9px 14px; }
  .nav-burger { display: inline-flex; }
  /* 抽屉式导航:覆盖在内容上方,不再挤压换行 */
  .nav {
    display: none;
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    flex-direction: column;
    gap: 2px;
    padding: var(--space-2);
    background: var(--panel-solid);
    border-bottom: 1px solid var(--border);
    box-shadow: var(--shadow-1);
  }
  .nav.open { display: flex; }
  .nav-link { padding: 10px 14px; }
  .nav-link.router-link-active::after { display: none; }
}
</style>
