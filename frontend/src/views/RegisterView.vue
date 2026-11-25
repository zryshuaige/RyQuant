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
    toast.success(`注册成功,欢迎 ${data.user.username}`);
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
    <div class="panel auth-card">
      <h1 class="auth-title">创建账户</h1>
      <p class="auth-sub">建立自选、保存回测记录并使用研究助手。</p>

      <form @submit.prevent="submit">
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
          <input id="reg-confirm" v-model="confirm" class="input" type="password" autocomplete="new-password" />
        </div>

        <div v-if="error" class="field-error" role="alert"><AppIcon name="warn" :size="13" /> {{ error }}</div>

        <button class="btn btn-primary btn-block" type="submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? "注册中…" : "注册" }}
        </button>
      </form>

      <p class="auth-foot">
        已有账户?<router-link :to="{ name: 'login', query: route.query }">直接登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page { display: flex; justify-content: center; padding-top: 6vh; }
.auth-card { width: 100%; max-width: 420px; }
.auth-title { font-family: var(--font-display); font-size: var(--fs-2xl); font-weight: 600; letter-spacing: -0.02em; }
.auth-sub { color: var(--text-2); margin: 6px 0 20px; font-size: var(--fs-sm); }
.auth-foot { color: var(--text-2); font-size: var(--fs-sm); margin: 14px 0 0; }
</style>