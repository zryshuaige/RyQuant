<script setup>
/** 标的检索:输入代码/名称 → 本地优先 + 全网识别 → 落库补历史 → 选中。 */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useMarketStore } from "../stores/market";
import { toast } from "../composables/useToast";
import AppIcon from "./AppIcon.vue";

const props = defineProps({
  placeholder: { type: String, default: "输入代码或名称" },
  ariaLabel: { type: String, default: "检索股票或指数" },
});
const emit = defineEmits(["select"]);

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const market = useMarketStore();

const query = ref("");
const results = ref([]);
const open = ref(false);
const loading = ref(false);
const resolving = ref("");
const remoteAvailable = ref(true);
const activeIndex = ref(-1);
let timer = null;
let requestSeq = 0;

const showEmpty = computed(() =>
  open.value && !loading.value && query.value.trim() && !results.value.length
);

function close() {
  open.value = false;
  activeIndex.value = -1;
}

function localStock(item) {
  return market.stocks.find((s) => s.symbol === item.symbol || s.symbol === item.code)
    || market.indices.find((s) => s.symbol === item.symbol)
    || { symbol: item.symbol, name: item.name, kind: item.kind, quote_source: "sim" };
}

async function pick(item) {
  if (!item || resolving.value) return;
  if (!item.in_db) {
    if (!auth.isLoggedIn) {
      toast.info("登录后可添加任意股票");
      router.push({ name: "login", query: { next: route.fullPath } });
      return;
    }
    resolving.value = item.code;
    try {
      const stock = await market.resolveStock(item.symbol);
      toast.success(`已添加 ${stock.name}(${stock.symbol})`);
      query.value = "";
      results.value = [];
      close();
      emit("select", stock);
    } catch (e) {
      toast.error(e.friendlyMessage || "添加失败");
    } finally {
      resolving.value = "";
    }
    return;
  }
  const stock = localStock(item);
  query.value = "";
  results.value = [];
  close();
  emit("select", stock);
}

function onInput() {
  open.value = true;
  activeIndex.value = -1;
  if (timer) clearTimeout(timer);
  const q = query.value.trim();
  if (!q) {
    results.value = [];
    loading.value = false;
    return;
  }
  loading.value = true;
  const seq = ++requestSeq;
  timer = setTimeout(async () => {
    try {
      const data = await market.searchSymbols(q);
      if (seq !== requestSeq) return;
      results.value = data.results || [];
      remoteAvailable.value = data.remote_available !== false;
    } catch {
      if (seq === requestSeq) results.value = [];
    } finally {
      if (seq === requestSeq) loading.value = false;
    }
  }, 250);
}

function onKeydown(event) {
  if (event.key === "Escape") { close(); return; }
  if (!open.value && (event.key === "ArrowDown" || event.key === "Enter")) {
    open.value = true;
    if (!results.value.length) onInput();
    return;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    activeIndex.value = Math.min(activeIndex.value + 1, results.value.length - 1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    activeIndex.value = Math.max(activeIndex.value - 1, 0);
  } else if (event.key === "Enter") {
    event.preventDefault();
    if (activeIndex.value >= 0) pick(results.value[activeIndex.value]);
    else if (results.value.length === 1) pick(results.value[0]);
  }
}

watch(query, (value) => { if (!value.trim()) results.value = []; });
onBeforeUnmount(() => { if (timer) clearTimeout(timer); });
</script>

<template>
  <div class="symbol-search">
    <div class="search-box">
      <AppIcon name="search" :size="15" class="search-icon" />
      <input
        v-model="query"
        class="input search-input"
        type="search"
        role="combobox"
        aria-autocomplete="list"
        aria-controls="symbol-search-list"
        :aria-expanded="open"
        :aria-label="ariaLabel"
        :placeholder="placeholder"
        autocomplete="off"
        @input="onInput"
        @focus="open = true"
        @keydown="onKeydown"
      />
      <span v-if="loading" class="spinner search-spin"></span>
    </div>
    <div v-if="open && (results.length || showEmpty)" id="symbol-search-list" class="search-menu" role="listbox">
      <button
        v-for="(item, i) in results"
        :key="`${item.source}-${item.code}`"
        class="search-item"
        :class="{ active: i === activeIndex }"
        role="option"
        :aria-selected="i === activeIndex"
        type="button"
        @mousedown.prevent="pick(item)"
        @mouseenter="activeIndex = i"
      >
        <span class="item-name">{{ item.name }}</span>
        <span class="symbol-badge">{{ item.code }}</span>
        <span v-if="item.kind === 'index'" class="item-kind">指数</span>
        <span v-if="resolving === item.code" class="spinner"></span>
        <span v-else-if="item.in_db" class="tag tag-muted">本库</span>
        <span v-else class="tag tag-info">{{ auth.isLoggedIn ? "添加" : "需登录" }}</span>
      </button>
      <div v-if="showEmpty" class="search-empty">
        没有找到匹配的股票<span v-if="!remoteAvailable">,名称检索暂不可用,可直接输入 6 位代码</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.symbol-search { position: relative; min-width: 260px; }
.search-box { position: relative; }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-3); pointer-events: none; }
.search-input { padding-left: 32px; padding-right: 30px; border-radius: var(--radius-pill); }
.search-spin { position: absolute; right: 10px; top: 50%; margin-top: -7px; }
.search-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: auto;
  right: 0;
  width: max(100%, 340px);
  z-index: 60;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--panel-chrome);
  backdrop-filter: blur(var(--blur-chrome));
  -webkit-backdrop-filter: blur(var(--blur-chrome));
  box-shadow: var(--shadow-2);
}
.search-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 38px;
  padding: 6px 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--text-1);
  font-size: var(--fs-sm);
  text-align: left;
  cursor: pointer;
}
.search-item:hover, .search-item.active { background: var(--hover-bg); }
.item-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-kind { color: var(--text-3); font-size: var(--fs-xs); }
.search-empty { padding: 10px; color: var(--text-3); font-size: var(--fs-xs); line-height: 1.6; }
@media (max-width: 700px) {
  .search-menu { left: 0; right: 0; width: 100%; }
}
</style>