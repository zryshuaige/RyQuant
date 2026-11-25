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

function fillDemo() {
  username.value = "demo";
  password.value = "demo123456";
  error.value = "";
}

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
    <div class="panel auth-card">
      <h1 class="auth-title">登录 RyQuant</h1>
      <p class="auth-sub">登录后建立自选、保存回测记录并使用研究助手。</p>

      <form @submit.prevent="submit">
        <div class="field">
          <label for="login-username">用户名</label>
          <input id="login-username" v-model="username" class="input" autocomplete="username" />
        </div>
        <div class="field">
          <label for="login-password">密码</label>
          <input id="login-password" v-model="password" class="input" type="password" autocomplete="current-password" />
        </div>

        <div v-if="error" class="field-error" role="alert"><AppIcon name="warn" :size="13" /> {{ error }}</div>

        <button class="btn btn-primary btn-block" type="submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? "登录中…" : "登录" }}
        </button>
      </form>

      <p class="auth-foot">
        还没有账户?<router-link :to="{ name: 'register', query: route.query }">立即注册</router-link>
      </p>
      <div class="demo-box">
        <span>演示账号 <b>demo / demo123456</b></span>
        <button class="btn btn-sm" type="button" @click="fillDemo">填入</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page { display: flex; justify-content: center; padding-top: 7vh; }
.auth-card { width: 100%; max-width: 420px; padding: 28px; }
.auth-title { font-family: var(--font-display); font-size: var(--fs-2xl); font-weight: 600; letter-spacing: -0.02em; text-align: center; }
.auth-sub { color: var(--text-2); margin: 8px 0 22px; font-size: var(--fs-sm); text-align: center; }
.auth-foot { color: var(--text-2); font-size: var(--fs-sm); margin: 14px 0 0; }
.demo-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 16px;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--accent-bg);
  color: var(--text-2);
  font-size: var(--fs-xs);
}
.demo-box b { color: var(--text-1); font-family: var(--font-mono); letter-spacing: 0.04em; }
</style>