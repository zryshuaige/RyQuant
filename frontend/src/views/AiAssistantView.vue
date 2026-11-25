<script setup>
/** 研究助手:结合大盘状态与自选回答,右侧上下文卡让回答有据可查。 */
import { computed, nextTick, onMounted, ref } from "vue";
import { useAuthStore } from "../stores/auth";
import { useMarketStore } from "../stores/market";
import { aiQuery, fetchMarketPulse } from "../api";
import { fmtDateTime, fmtSigned } from "../utils/format";
import AppIcon from "../components/AppIcon.vue";
import InfoTip from "../components/InfoTip.vue";
import { toast } from "../composables/useToast";

const auth = useAuthStore();
const market = useMarketStore();

const messages = ref([]);
const input = ref("");
const sending = ref(false);
const conversationId = ref(null);
const error = ref("");
const retryQuestion = ref("");
const listEl = ref(null);
const pulse = ref(null);
const pulseLoading = ref(true);

const suggestions = [
  "当前行情适合什么策略?",
  "解释一下样本外收益",
  "我的自选最近表现如何?",
];

const contextAdvice = computed(() => pulse.value?.advice?.[0] || null);
const summary = computed(() => market.favoritesSummary);

function greeting() {
  return {
    sender: "bot",
    content: "可以问我当前大盘状态、适合的策略,或某只自选加入以来的表现。回答仅供研究参考,不构成投资建议。",
    time: new Date().toISOString(),
  };
}

async function scrollToBottom() {
  await nextTick();
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight;
}

async function send(text, isRetry = false) {
  const question = (text ?? input.value).trim();
  if (!question || sending.value) return;
  error.value = "";
  retryQuestion.value = "";
  if (!isRetry) {
    input.value = "";
    messages.value.push({ sender: "user", content: question, time: new Date().toISOString() });
  }
  sending.value = true;
  scrollToBottom();
  try {
    const data = await aiQuery(question, conversationId.value);
    conversationId.value = data.conversation.id;
    messages.value.push({ sender: "bot", content: data.answer, time: new Date().toISOString() });
  } catch (e) {
    error.value = e.friendlyMessage || "提问失败";
    retryQuestion.value = question;
  } finally {
    sending.value = false;
    scrollToBottom();
  }
}

function retry() {
  if (retryQuestion.value) send(retryQuestion.value, true);
}

function onEnter(event) {
  if (event.isComposing) return;
  send();
}

function newChat() {
  conversationId.value = null;
  messages.value = [greeting()];
  error.value = "";
  retryQuestion.value = "";
  input.value = "";
  toast.info("已开始新对话");
}

async function loadContext() {
  try {
    pulse.value = await fetchMarketPulse();
  } catch { /* 上下文卡失败不影响聊天 */ }
  finally { pulseLoading.value = false; }
  if (auth.isLoggedIn) {
    if (!market.favorites.length) await market.fetchFavorites();
    await market.fetchFavoritesSummary();
  }
}

onMounted(async () => {
  messages.value = [greeting()];
  if (auth.isLoggedIn) await market.ensureLoaded();
  loadContext();
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">研究助手</h1>
        <p class="page-sub">结合大盘状态、策略与自选回答问题;内容仅供研究参考。</p>
      </div>
      <button class="btn btn-sm" @click="newChat">
        <AppIcon name="plus" :size="14" /> 新对话
      </button>
    </div>

    <div class="ai-grid">
      <section class="panel chat-panel">
        <div ref="listEl" class="chat-list" aria-live="polite">
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.sender">
            <div class="bubble" :class="m.sender">
              <div class="msg-content">{{ m.content }}</div>
              <div class="msg-time">{{ fmtDateTime(m.time) }}</div>
            </div>
          </div>
          <div v-if="sending" class="msg-row bot">
            <div class="bubble bot typing">
              <span class="spinner"></span>
              <span>正在回答…</span>
            </div>
          </div>
        </div>

        <div v-if="error" class="field-error" role="alert">
          <AppIcon name="warn" :size="13" /> {{ error }}
          <button v-if="retryQuestion" class="btn btn-sm" @click="retry">重试</button>
        </div>

        <div v-if="messages.length <= 1" class="suggestion-row">
          <button v-for="s in suggestions" :key="s" class="btn btn-sm" :disabled="sending" @click="send(s)">
            {{ s }}
          </button>
        </div>

        <form class="composer" @submit.prevent="send()">
          <textarea
            v-model="input" class="input" rows="2" aria-label="输入研究问题"
            placeholder="输入研究问题…"
            @keydown.enter.exact.prevent="onEnter"
          ></textarea>
          <button class="btn btn-primary" type="submit" :disabled="sending || !input.trim()">
            <span v-if="sending" class="spinner"></span>
            {{ sending ? "回答中…" : "发送" }}
          </button>
        </form>
      </section>

      <aside class="context-rail">
        <section class="panel context-card">
          <h2 class="panel-title">当前大盘</h2>
          <template v-if="pulse">
            <div class="context-regime">
              <span class="regime-label">{{ pulse.label }}</span>
              <span class="num" :class="pulse.score >= 0 ? 'up' : 'down'">{{ fmtSigned(Math.round(pulse.score), 0) }}</span>
            </div>
            <p class="context-text">
              涨 {{ pulse.breadth.advance }} / 跌 {{ pulse.breadth.decline }},
              {{ pulse.breadth.pct_above_ma20 ?? "--" }}% 个股站上 20 日均线。
            </p>
            <div v-if="contextAdvice" class="context-advice">
              <span>当前更适合</span>
              <b>{{ contextAdvice.name }}</b>
              <span class="context-meta">
                类似行情下相对最好,区间收益 {{ fmtSigned(contextAdvice.regime_return_pct ?? contextAdvice.oos_return_pct) }}%
                <InfoTip text="统计的是当前行情状态下、过去 120 个交易日里该策略的表现,不代表未来收益。" />
              </span>
            </div>
            <router-link class="context-link" :to="{ name: 'home' }">查看大盘状态 <AppIcon name="arrow-right" :size="13" /></router-link>
          </template>
          <div v-else-if="pulseLoading" class="skeleton" style="height: 90px"></div>
          <p v-else class="context-text">大盘状态暂时不可用。</p>
        </section>

        <section class="panel context-card">
          <h2 class="panel-title">我的自选</h2>
          <template v-if="summary?.count">
            <div class="context-stats">
              <div><b class="num" :class="summary.avg_return_pct >= 0 ? 'up' : 'down'">{{ fmtSigned(summary.avg_return_pct) }}%</b><span>平均加入以来</span></div>
              <div><b class="num">{{ summary.beat_count }}/{{ summary.count }}</b><span>跑赢上证</span></div>
            </div>
            <router-link class="context-link" :to="{ name: 'favorites' }">查看自选跟踪 <AppIcon name="arrow-right" :size="13" /></router-link>
          </template>
          <p v-else class="context-text">还没有自选。加入后可跟踪加入以来的收益与上证对比。</p>
        </section>

        <section class="panel context-card tips-card">
          <h2 class="panel-title">可以这样问</h2>
          <ul class="tips-list">
            <li>当前大盘是什么状态?</li>
            <li>为什么当前更适合某个策略?</li>
            <li>我的自选有没有跑赢上证?</li>
          </ul>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.ai-grid { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: var(--space-4); align-items: start; }
.chat-panel { display: flex; flex-direction: column; height: calc(100vh - 190px); min-height: 520px; }
.chat-list { flex: 1; overflow-y: auto; padding: 4px; }
.msg-row { display: flex; margin-bottom: 12px; }
.msg-row.user { justify-content: flex-end; }
.bubble { max-width: 78%; padding: 10px 14px; border-radius: var(--radius); font-size: var(--fs-sm); line-height: 1.7; }
.bubble.bot { background: var(--inset-bg-soft); border: 1px solid var(--border); border-bottom-left-radius: 2px; }
.bubble.user { background: var(--btn-primary-bg); color: var(--btn-primary-fg); border-bottom-right-radius: 2px; }
.msg-content { white-space: pre-wrap; word-break: break-word; }
.msg-time { font-family: var(--font-mono); font-size: var(--fs-xs); letter-spacing: 0.04em; margin-top: 5px; color: var(--text-3); }
.bubble.user .msg-time { color: color-mix(in srgb, var(--btn-primary-fg) 72%, transparent); }
.typing { display: inline-flex; align-items: center; gap: 8px; color: var(--text-2); }
.suggestion-row { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.composer { display: flex; gap: 8px; align-items: flex-end; border-top: 1px solid var(--border); padding-top: 10px; }
.composer textarea { resize: none; flex: 1; }
.context-rail { display: grid; gap: var(--space-4); }
.context-card { padding: var(--space-4); }
.context-card .panel-title { font-size: var(--fs-sm); margin-bottom: 10px; }
.context-regime { display: flex; align-items: baseline; gap: 8px; }
.regime-label { font-family: var(--font-display); font-size: var(--fs-xl); font-weight: 600; letter-spacing: -0.02em; }
.context-regime .num { font-family: var(--font-display); font-size: var(--fs-lg); font-weight: 600; }
.context-text { font-size: var(--fs-xs); color: var(--text-2); line-height: 1.6; margin: 6px 0 10px; }
.context-advice { display: grid; gap: 2px; padding: 8px 10px; border: 1px solid var(--border); border-left: 2px solid var(--accent); border-radius: var(--radius-sm); background: var(--accent-bg); margin-bottom: 10px; }
.context-advice > span:first-child { font-size: var(--fs-xs); color: var(--text-3); }
.context-advice b { font-size: var(--fs-sm); }
.context-meta { font-size: var(--fs-xs); color: var(--text-2); display: inline-flex; align-items: center; gap: 2px; }
.context-link { display: inline-flex; align-items: center; gap: 3px; font-size: var(--fs-xs); font-weight: 600; }
.context-stats { display: flex; gap: var(--space-4); }
.context-stats div { display: grid; }
.context-stats b { font-family: var(--font-display); font-size: var(--fs-xl); font-weight: 600; letter-spacing: -0.02em; }
.context-stats span { font-size: var(--fs-xs); color: var(--text-3); }
.tips-list { margin: 0; padding-left: 16px; color: var(--text-2); font-size: var(--fs-xs); line-height: 1.8; }
@media (max-width: 1000px) {
  .ai-grid { grid-template-columns: 1fr; }
  .context-rail { grid-template-columns: 1fr 1fr; }
  .tips-card { display: none; }
}
@media (max-width: 700px) {
  .chat-panel { height: calc(100vh - 300px); min-height: 420px; }
  .bubble { max-width: 90%; }
  .context-rail { grid-template-columns: 1fr; }
}
</style>