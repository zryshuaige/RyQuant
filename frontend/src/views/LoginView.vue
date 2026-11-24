<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import AppIcon from "../components/AppIcon.vue";
import { toast } from "../composables/useToast";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function submit() {
  error.value = "";
  if (!username.value.trim()) { error.value = "请输入用户名"; return; }
  if (!password.value) { error.value = "请输入密码"; return; }
  loading.value = true;
  try {
    const data = await auth.login(username.value.trim(), password.value);
    toast.success(`欢迎回来,${data.user.username}`);
    router.push(route.query.next || { name: "home" });
  } catch (e) {
    error.value = e.friendlyMessage || "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="page auth-page">
    <div class="panel-gradient auth-card">
      <form class="panel" style="border: none" @submit.prevent="submit">
        <h1 class="auth-title">登录 <em>RyQuant</em></h1>
        <p class="auth-sub">连接你的模拟交易账户</p>

        <div class="field">
          <label for="login-username">用户名</label>
          <input id="login-username" v-model="username" class="input" autocomplete="username" placeholder="用户名" />
        </div>
        <div class="field">
          <label for="login-password">密码</label>
          <input id="login-password" v-model="password" class="input" type="password" autocomplete="current-password" placeholder="密码" />
        </div>

        <div v-if="error" class="field-error" role="alert"><AppIcon name="warn" :size="13" /> {{ error }}</div>

        <button class="btn btn-primary btn-block" type="submit" :disabled="loading" style="margin-top: 10px">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? "登录中…" : "登录" }}
        </button>

        <p class="auth-foot">
          还没有账户?<router-link :to="{ name: 'register', query: route.query }">立即注册</router-link>
        </p>
        <div class="demo-box">
          <strong>演示账号</strong> demo / demo123456(VIP 已开通,含历史持仓)
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-page { display: flex; justify-content: center; padding-top: 7vh; }
.auth-card { width: 100%; max-width: 420px; }
.auth-title { font-size: 24px; text-align: center; }
.auth-title em {
  font-style: normal;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.auth-sub { text-align: center; color: var(--text-3); margin: 6px 0 20px; font-size: 13px; }
.auth-foot { text-align: center; color: var(--text-3); font-size: 13px; margin: 14px 0 0; }
.demo-box {
  margin-top: 16px;
  padding: 10px 12px;
  border: 1px dashed rgba(246, 196, 83, 0.45);
  border-radius: var(--radius);
  color: var(--text-2);
  font-size: 12px;
  text-align: center;
}
.demo-box strong { color: var(--gold); margin-right: 6px; }
</style>
