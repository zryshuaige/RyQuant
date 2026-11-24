import { createRouter, createWebHistory } from "vue-router";

const routes = [
  { path: "/", name: "home", component: () => import("../views/HomeView.vue"), meta: { title: "行情总览" } },
  { path: "/login", name: "login", component: () => import("../views/LoginView.vue"), meta: { title: "登录", guestOnly: true } },
  { path: "/register", name: "register", component: () => import("../views/RegisterView.vue"), meta: { title: "注册", guestOnly: true } },
  { path: "/favorites", name: "favorites", component: () => import("../views/FavoritesView.vue"), meta: { title: "自选股", requiresAuth: true } },
  { path: "/backtest", name: "backtest", component: () => import("../views/BacktestView.vue"), meta: { title: "量化回测", requiresAuth: true } },
  { path: "/ai", name: "ai", component: () => import("../views/AiAssistantView.vue"), meta: { title: "AI 助手", requiresAuth: true } },
  { path: "/:pathMatch(.*)*", name: "not-found", component: () => import("../views/NotFoundView.vue"), meta: { title: "页面不存在" } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach((to) => {
  const token = localStorage.getItem("fin_token");
  if (to.meta.requiresAuth && !token) {
    return { name: "login", query: { next: to.fullPath } };
  }
  if (to.meta.guestOnly && token) {
    return { name: "home" };
  }
  return true;
});

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · RyQuant` : "RyQuant";
});

export default router;
