<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { theme, toggleTheme } from "../composables/useTheme";
import AppIcon from "./AppIcon.vue";
import { toast } from "../composables/useToast";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const navEl = ref(null);

const navItems = [
  { to: "/", label: "行情总览", icon: "chart", exact: true },
  { to: "/favorites", label: "自选跟踪", icon: "star" },
  { to: "/backtest", label: "量化回测", icon: "scale" },
  { to: "/ai", label: "研究助手", icon: "robot" },
];

/* 胶囊导航滑动指示器(桌面) */
const linkEls = ref({});
const indicator = ref({ width: 0, transform: "translateX(0)", ready: false });
function setLinkEl(to, el) {
  const node = el && el.$el ? el.$el : el;
  if (node) linkEls.value[to] = node;
  else delete linkEls.value[to];
}
function syncIndicator() {
  const item = navItems.find((n) => (n.exact ? route.path === n.to : route.path.startsWith(n.to)));
  const el = item && linkEls.value[item.to];
  if (!el || !navEl.value || window.innerWidth <= 860) {
    indicator.value.ready = false;
    return;
  }
  indicator.value = { width: el.offsetWidth, transform: `translateX(${el.offsetLeft}px)`, ready: true };
}

function logout() {
  auth.logout();
  toast.info("已退出登录");
  router.push({ name: "home" });
}
watch(() => route.fullPath, () => nextTick(syncIndicator));
onMounted(() => {
  window.addEventListener("resize", syncIndicator);
  nextTick(syncIndicator);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(syncIndicator);
});
onUnmounted(() => {
  window.removeEventListener("resize", syncIndicator);
});
</script>

<template>
  <header class="header">
    <div class="header-inner">
      <router-link to="/" class="brand" aria-label="RyQuant 首页">
        <svg class="brand-mark" viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
          <path d="M5 23 L11 14 L17 18 L27 6" stroke="currentColor" stroke-width="3.2" fill="none"
            stroke-linecap="round" stroke-linejoin="round" />
          <circle cx="27" cy="6" r="3" fill="currentColor" />
        </svg>
        <span class="brand-name">Ry<em>Quant</em></span>
      </router-link>

      <nav id="main-nav" ref="navEl" class="nav" aria-label="主导航">
        <span class="nav-indicator" :class="{ ready: indicator.ready }" aria-hidden="true"
          :style="{ width: indicator.width + 'px', transform: indicator.transform }"></span>
        <router-link v-for="item in navItems" :key="item.to" :to="item.to"
          :ref="(el) => setLinkEl(item.to, el)" class="nav-link" :class="{ exact: item.exact }">
          {{ item.label }}
        </router-link>
      </nav>

      <div class="auth-area">
        <button class="theme-toggle" :title="theme === 'yonder' ? '切换到 Reverie(浅)' : '切换到 Yonder(深)'"
          :aria-label="theme === 'yonder' ? '切换到 Reverie 浅色主题' : '切换到 Yonder 深色主题'" @click="toggleTheme">
          <AppIcon :name="theme === 'yonder' ? 'moon' : 'sun'" :size="14" />
          <span class="theme-name" :class="{ 'is-active': theme === 'reverie' }">Reverie</span>
          <span class="theme-name" :class="{ 'is-active': theme === 'yonder' }">Yonder</span>
        </button>
        <template v-if="auth.isLoggedIn">
          <span class="user-chip">
            <span class="avatar">{{ auth.username.slice(0, 1).toUpperCase() }}</span>
            <span class="user-name">{{ auth.username }}</span>
          </span>
          <button class="btn btn-sm btn-ghost logout-btn" @click="logout">退出</button>
        </template>
        <template v-else>
          <router-link class="btn btn-sm btn-ghost" :to="{ name: 'login' }">登录</router-link>
          <router-link class="btn btn-sm btn-primary" :to="{ name: 'register' }">注册</router-link>
        </template>
      </div>
    </div>
  </header>

  <!-- 移动端常驻底部标签栏:四个页面始终可见。
       必须置于 <header> 之外:header 的 backdrop-filter 会成为 fixed 后代的包含块 -->
  <nav class="tabbar" aria-label="主导航">
    <router-link v-for="item in navItems" :key="item.to" :to="item.to" class="tabbar-item">
      <AppIcon :name="item.icon" :size="18" />
      <span>{{ item.label }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--header-bg);
  backdrop-filter: blur(var(--blur-chrome));
  -webkit-backdrop-filter: blur(var(--blur-chrome));
  border-bottom: 1px solid var(--border);
}
.header-inner {
  max-width: 1240px;
  margin: 0 auto;
  padding: 0 20px;
  height: 64px;
  display: flex;
  align-items: center;
  gap: 20px;
}
.brand { display: flex; align-items: center; gap: 8px; color: var(--text-1); }
.brand:hover { color: var(--text-1); }
.brand-mark { color: var(--accent); flex: none; }
.brand-name {
  font-family: var(--font-display);
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.04em;
}
.brand-name em { color: var(--accent-text); font-style: normal; font-weight: 400; }

/* 胶囊导航 + 滑动指示器 */
.nav {
  position: relative;
  display: flex;
  flex: 1;
  justify-content: center;
  gap: 0;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--panel-chrome);
  backdrop-filter: blur(var(--blur-chrome));
  -webkit-backdrop-filter: blur(var(--blur-chrome));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 8px 28px var(--shadow-color);
  max-width: 460px;
  margin: 0 auto;
}
.nav-indicator {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 0;
  z-index: 1;
  border-radius: var(--radius-pill);
  background: var(--panel-solid);
  border: 1px solid var(--border);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.38), 0 4px 12px var(--shadow-color);
  opacity: 0;
  transition: transform 0.26s var(--ease-out), width 0.26s var(--ease-out), opacity 0.2s;
}
.nav-indicator.ready { opacity: 1; }
.nav-link {
  position: relative;
  z-index: 2;
  display: grid;
  place-items: center;
  min-height: 36px;
  padding: 0 16px;
  border-radius: var(--radius-pill);
  color: var(--text-2);
  font-size: var(--fs-sm);
  font-weight: 600;
  letter-spacing: -0.01em;
  white-space: nowrap;
  transition: color 0.18s;
}
.nav-link:hover { color: var(--text-1); }
.nav-link.router-link-active { color: var(--text-1); }

.auth-area { display: flex; align-items: center; gap: 8px; }
.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--panel-chrome);
  color: var(--text-3);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.18s, color 0.18s;
}
.theme-toggle:hover { background: var(--hover-bg); color: var(--text-1); }
.theme-name { position: relative; padding: 4px 0; opacity: 0.55; transition: opacity 0.22s, color 0.22s; }
.theme-name::after {
  content: "";
  position: absolute;
  left: 25%; right: 25%; bottom: 0;
  height: 1px;
  background: var(--accent);
  transform: scaleX(0);
  transition: transform 0.3s var(--ease-out);
}
.theme-name.is-active { opacity: 1; color: var(--text-1); }
.theme-name.is-active::after { transform: scaleX(1); }
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--text-2);
  max-width: 140px;
}
.user-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.avatar {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: var(--accent-bg);
  color: var(--accent-text);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

/* 移动端底部标签栏 */
.tabbar { display: none; }
@media (max-width: 860px) {
  .header-inner { gap: 8px; padding: 0 12px; height: 56px; }
  .brand-name { font-size: 19px; }
  .nav { display: none; }
  .auth-area { gap: 4px; margin-left: auto; }
  .user-name { display: none; }
  .logout-btn { padding: 4px 8px; }
  .tabbar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    position: fixed;
    left: 0; right: 0; bottom: 0;
    z-index: 50;
    padding: 6px 8px calc(6px + env(safe-area-inset-bottom));
    background: var(--header-bg);
    backdrop-filter: blur(var(--blur-chrome));
    -webkit-backdrop-filter: blur(var(--blur-chrome));
    border-top: 1px solid var(--border);
  }
  .tabbar-item {
    display: grid;
    justify-items: center;
    align-content: center;
    gap: 2px;
    min-height: 46px;
    border-radius: var(--radius-sm);
    color: var(--text-3);
    font-size: var(--fs-xs);
    font-weight: 600;
    transition: color 0.15s, background 0.15s;
  }
  .tabbar-item.router-link-active { color: var(--accent-text); background: var(--accent-bg); }
}
@media (max-width: 480px) {
  .theme-name { display: none; }
  .theme-toggle { padding: 0 10px; }
}
@media (max-width: 380px) {
  .brand-name { display: none; }
}
</style>