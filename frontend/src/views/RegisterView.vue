<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { toast } from "../composables/useToast";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref("");
const email = ref("");
const password = ref("");
const confirm = ref("");
const error = ref("");
const loading = ref(false);

function clientValidate() {
  if (!username.value.trim()) return "请输入用户名";
  if (username.value.trim().length < 3) return "用户名至少 3 个字符";
  if (!password.value) return "请输入密码";
  if (password.value.length < 6) return "密码至少 6 位,且不能为纯数字";
  if (/^\d+$/.test(password.value)) return "密码不能为纯数字";
  if (password.value !== confirm.value) return "两次输入的密码不一致";
  return null;
}

async function submit() {
  error.value = clientValidate();
  if (error.value) return;
  loading.value = true;
  try {
    const data = await auth.register({
      username: username.value.trim(),
      email: email.value.trim(),
      password: password.value,
    });
    toast.success(`注册成功,欢迎加入,${data.user.username}!`);
    router.push(route.query.next || { name: "home" });
  } catch (e) {
    error.value = e.friendlyMessage || "注册失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="page auth-page">
    <div class="panel-gradient auth-card">
      <form class="panel" style="border: none" @submit.prevent="submit">
        <h1 class="auth-title">创建账户</h1>
        <p class="auth-sub">加入 FinQuant · 体验完整模拟交易闭环</p>

        <div class="field">
          <label for="reg-username">用户名</label>
          <input id="reg-username" v-model="username" class="input" autocomplete="username" placeholder="3 个字符以上" />
        </div>
        <div class="field">
          <label for="reg-email">邮箱(可选)</label>
          <input id="reg-email" v-model="email" class="input" type="email" autocomplete="email" placeholder="you@example.com" />
        </div>
        <div class="field">
          <label for="reg-password">密码</label>
          <input id="reg-password" v-model="password" class="input" type="password" autocomplete="new-password" placeholder="至少 6 位,不能纯数字" />
        </div>
        <div class="field">
          <label for="reg-confirm">确认密码</label>
          <input id="reg-confirm" v-model="confirm" class="input" type="password" autocomplete="new-password" placeholder="再次输入密码" />
        </div>

        <div v-if="error" class="field-error" role="alert">⚠ {{ error }}</div>

        <button class="btn btn-primary btn-block" type="submit" :disabled="loading" style="margin-top: 10px">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? "注册中…" : "注册" }}
        </button>

        <p class="auth-foot">
          已有账户?<router-link :to="{ name: 'login', query: route.query }">直接登录</router-link>
        </p>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-page { display: flex; justify-content: center; padding-top: 6vh; }
.auth-card { width: 100%; max-width: 420px; }
.auth-title { font-size: 24px; text-align: center; }
.auth-sub { text-align: center; color: var(--text-3); margin: 6px 0 20px; font-size: 13px; }
.auth-foot { text-align: center; color: var(--text-3); font-size: 13px; margin: 14px 0 0; }
</style>
