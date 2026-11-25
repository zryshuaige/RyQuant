import { createRouter, createWebHistory } from "vue-router";

/** 懒加载自愈:开发服务器重启/部署更新后旧 chunk 失效时,整页重载一次 */
const lazy = (loader) => () =>
  loader().catch((err) => {
    if (!sessionStorage.getItem("fin_chunk_reload")) {
      sessionStorage.setItem("fin_chunk_reload", "1");
      location.reload();
      return new Promise(() => {});
    }
    throw err;
  });

const routes = [
  { path: "/", name: "home", component: lazy(() => import("../views/HomeView.vue")), meta: { title: "行情总览" } },
  { path: "/login", name: "login", component: lazy(() => import("../views/LoginView.vue")), meta: { title: "登录", guestOnly: true } },
  { path: "/register", name: "register", component: lazy(() => import("../views/RegisterView.vue")), meta: { title: "注册", guestOnly: true } },
  { path: "/favorites", name: "favorites", component: lazy(() => import("../views/FavoritesView.vue")), meta: { title: "自选跟踪", requiresAuth: true } },
  { path: "/backtest", name: "backtest", component: lazy(() => import("../views/BacktestView.vue")), meta: { title: "量化回测", requiresAuth: true } },
  { path: "/ai", name: "ai", component: lazy(() => import("../views/AiAssistantView.vue")), meta: { title: "研究助手", requiresAuth: true } },
  { path: "/:pathMatch(.*)*", name: "not-found", component: lazy(() => import("../views/NotFoundView.vue")), meta: { title: "页面不存在" } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, from, savedPosition) => savedPosition || { top: 0 },
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
  const main = document.getElementById("main");
  if (main) main.focus({ preventScroll: true });
});

export default router;