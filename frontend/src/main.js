import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import { onUnauthorized } from "./api/client";
import { useAuthStore } from "./stores/auth";
import { toast } from "./composables/useToast";

import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

// 401 统一处理:清除会话并跳转登录
onUnauthorized(() => {
  const auth = useAuthStore(pinia);
  if (auth.isLoggedIn) {
    auth.logout();
    toast.error("登录已过期,请重新登录");
    router.push({ name: "login" });
  }
});

app.mount("#app");
