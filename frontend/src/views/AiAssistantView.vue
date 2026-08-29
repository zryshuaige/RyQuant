<script setup>
/** AI 投研助手:VIP 门槛 + 会话延续 + 打字动效 */
import { ref, nextTick, onMounted } from "vue";
import { useAuthStore } from "../stores/auth";
import { aiQuery } from "../api";
import { fmtDateTime } from "../utils/format";
import VipBadge from "../components/VipBadge.vue";
import { toast } from "../composables/useToast";

const auth = useAuthStore();

const messages = ref([]); // {sender: 'user'|'bot', content, time}
const input = ref("");
const sending = ref(false);
const conversationId = ref(null);
const error = ref("");
const listEl = ref(null);

const suggestions = ["分析我的持仓", "现在行情怎么样?", "怎么用双均线策略?", "如何撤单?"];

async function activate() {
  try {
    await auth.activateVip();
    toast.success("VIP 已开通,AI 助手已解锁!");
  } catch (e) {
    toast.error(e.friendlyMessage || "开通失败");
  }
}

async function scrollToBottom() {
  await nextTick();
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight;
}

async function send(text) {
  const question = (text ?? input.value).trim();
  if (!question || sending.value) return;
  error.value = "";
  input.value = "";
  messages.value.push({ sender: "user", content: question, time: new Date().toISOString() });
  sending.value = true;
  scrollToBottom();
  try {
    const data = await aiQuery(question, conversationId.value);
    conversationId.value = data.conversation.id;
    messages.value.push({ sender: "bot", content: data.answer, time: data.conversation.created_at });
  } catch (e) {
    error.value = e.friendlyMessage || "提问失败";
  } finally {
    sending.value = false;
    scrollToBottom();
  }
}

onMounted(() => {
  if (auth.isVip) {
    messages.value.push({
      sender: "bot",
      content: "你好!我是 FinQuant 投研助手(模拟环境)。可以直接问我持仓分析、行情观点,或让我解释某个量化策略。提示:回答不构成投资建议。",
      time: new Date().toISOString(),
    });
  }
});
</script>

<template>
  <div class="page ai-page">
    <!-- 未开通 VIP -->
    <div v-if="!auth.isVip" class="panel-gradient vip-gate">
      <div class="panel vip-inner" style="border: none">
        <div class="lock">🤖</div>
        <h1 class="vip-title">AI 投研助手</h1>
        <p class="vip-sub">
          接入大模型的对话式投研助理:解读你的持仓与盈亏、分析模拟行情、讲解量化策略。
          <br />VIP 开通后即可使用;未配置 AI Key 时将使用内置离线分析引擎。
        </p>
        <button class="btn btn-primary btn-lg" @click="activate">开通 VIP · 解锁 AI 助手</button>
      </div>
    </div>

    <template v-else>
      <div class="ai-head">
        <h1 class="page-title">AI 投研助手 <VipBadge active /></h1>
        <p class="page-sub">回答为模拟环境生成,不构成任何投资建议</p>
      </div>

      <section class="panel chat-panel">
        <div ref="listEl" class="chat-list">
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.sender">
            <div class="bubble" :class="m.sender">
              <div class="msg-content">{{ m.content }}</div>
              <div class="msg-time">{{ fmtDateTime(m.time) }}</div>
            </div>
          </div>
          <div v-if="sending" class="msg-row bot">
            <div class="bubble bot typing">
              <span class="tdot"></span><span class="tdot"></span><span class="tdot"></span>
            </div>
          </div>
        </div>

        <div v-if="error" class="field-error" role="alert">⚠ {{ error }}</div>

        <div class="suggestion-row">
          <button v-for="s in suggestions" :key="s" class="btn btn-sm" :disabled="sending" @click="send(s)">
            {{ s }}
          </button>
        </div>

        <form class="composer" @submit.prevent="send()">
          <textarea
            v-model="input" class="input" rows="2" placeholder="输入你的问题,Enter 发送…"
            @keydown.enter.exact.prevent="send()"
          ></textarea>
          <button class="btn btn-primary" type="submit" :disabled="sending || !input.trim()">
            <span v-if="sending" class="spinner"></span>
            {{ sending ? "思考中" : "发送" }}
          </button>
        </form>
      </section>
    </template>
  </div>
</template>

<style scoped>
.vip-gate { max-width: 640px; margin: 6vh auto 0; }
.vip-inner { text-align: center; padding: 44px 36px; }
.lock { font-size: 44px; margin-bottom: 10px; filter: drop-shadow(0 0 18px rgba(34, 211, 238, 0.4)); }
.vip-title {
  font-size: 30px;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.vip-sub { color: var(--text-2); margin: 14px 0 22px; line-height: 1.8; }
.btn-lg { padding: 12px 26px; font-size: 15px; }

.page-title { font-size: 24px; display: flex; align-items: center; gap: 10px; }
.page-sub { color: var(--text-3); font-size: 13px; margin: 6px 0 18px; }
.chat-panel { display: flex; flex-direction: column; height: calc(100vh - 260px); min-height: 480px; }
.chat-list { flex: 1; overflow-y: auto; padding: 6px 4px; }
.msg-row { display: flex; margin-bottom: 14px; }
.msg-row.user { justify-content: flex-end; }
.bubble {
  max-width: 76%;
  padding: 11px 15px;
  border-radius: 16px;
  font-size: 13.5px;
  line-height: 1.7;
}
.msg-content { white-space: pre-wrap; word-break: break-word; }
.msg-time { font-size: 10.5px; margin-top: 6px; opacity: 0.55; }
.bubble.bot {
  background: var(--panel);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}
.bubble.user {
  background: var(--brand-grad);
  color: #07101c;
  font-weight: 600;
  border-bottom-right-radius: 4px;
}
.msg-time { color: inherit; }
.typing { display: inline-flex; gap: 5px; align-items: center; padding: 14px 18px; }
.tdot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--text-3);
  animation: bounce 1.2s infinite ease-in-out;
}
.tdot:nth-child(2) { animation-delay: 0.15s; }
.tdot:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-6px); } }
.suggestion-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.composer { display: flex; gap: 10px; align-items: flex-end; }
.composer textarea { resize: none; flex: 1; }
@media (max-width: 700px) {
  .bubble { max-width: 92%; }
}
</style>
