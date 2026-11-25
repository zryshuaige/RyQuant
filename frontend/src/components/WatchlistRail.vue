<script setup>
/** 首页自选侧栏:加入以来收益 + 同期上证超额。 */
import { computed } from "vue";
import { useAuthStore } from "../stores/auth";
import { fmtSigned } from "../utils/format";
import Sparkline from "./Sparkline.vue";
import AppIcon from "./AppIcon.vue";

const props = defineProps({
  summary: { type: Object, default: null },
  loading: { type: Boolean, default: false },
});
const emit = defineEmits(["select"]);
const auth = useAuthStore();
const items = computed(() => (props.summary?.items || []).slice(0, 6));
</script>

<template>
  <aside class="panel watch-rail">
    <div class="panel-head">
      <div>
        <h3 class="rail-title">我的自选</h3>
        <p v-if="summary?.count" class="rail-sub">加入以来 · 对比上证</p>
      </div>
      <router-link v-if="auth.isLoggedIn && summary?.count" class="manage" :to="{ name: 'favorites' }">
        管理 <AppIcon name="arrow-right" :size="13" />
      </router-link>
    </div>

    <template v-if="!auth.isLoggedIn">
      <p class="rail-empty-text">登录后可记录加入自选的时间,并跟踪加入以来的收益与上证对比。</p>
      <router-link class="btn btn-sm" :to="{ name: 'login' }">登录后使用</router-link>
    </template>

    <template v-else-if="loading && !summary">
      <div class="stack">
        <div v-for="i in 4" :key="i" class="skeleton" style="height: 44px"></div>
      </div>
    </template>

    <template v-else-if="items.length">
      <div class="watch-list">
        <button v-for="item in items" :key="item.stock.symbol" class="watch-row" @click="emit('select', item.stock)">
          <span class="watch-id">
            <b>{{ item.stock.name }}</b>
            <span class="watch-code">{{ item.stock.symbol }} · {{ item.joined_at.slice(5) }}</span>
          </span>
          <Sparkline :points="item.series" :width="76" :height="26" />
          <span class="watch-ret">
            <b class="num" :class="item.return_pct >= 0 ? 'up' : 'down'">{{ fmtSigned(item.return_pct) }}%</b>
            <span class="num" :class="item.excess_pct >= 0 ? 'up' : 'down'">
              超额 {{ fmtSigned(item.excess_pct) }}%
            </span>
          </span>
        </button>
      </div>
      <div class="rail-foot">
        <span>平均 <b class="num" :class="summary.avg_return_pct >= 0 ? 'up' : 'down'">{{ fmtSigned(summary.avg_return_pct) }}%</b></span>
        <span>跑赢上证 <b class="num">{{ summary.beat_count }}/{{ summary.count }}</b></span>
      </div>
    </template>

    <template v-else>
      <p class="rail-empty-text">还没有自选。加入后 K 线会标注加入日期,并自动计算相对上证的收益。</p>
      <router-link class="btn btn-sm" :to="{ name: 'favorites' }">添加第一只</router-link>
    </template>
  </aside>
</template>

<style scoped>
.watch-rail { display: flex; flex-direction: column; min-height: 100%; }
.rail-title { font-size: var(--fs-lg); font-weight: 700; }
.rail-sub { color: var(--text-3); font-size: var(--fs-xs); margin-top: 2px; }
.manage { display: inline-flex; align-items: center; gap: 2px; font-size: var(--fs-xs); font-weight: 600; }
.watch-list { display: grid; gap: 0; margin: 0 -6px; }
.watch-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 76px auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 6px;
  border: none;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--text-1);
  text-align: left;
  cursor: pointer;
}
.watch-row { border-bottom: 1px solid var(--hover-bg); }
.watch-row:last-child { border-bottom: none; }
.watch-row:hover { background: var(--hover-bg); }
.watch-id { display: grid; min-width: 0; }
.watch-id b { font-size: var(--fs-md); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.watch-code { font-family: var(--font-mono); font-size: var(--fs-xs); letter-spacing: 0.04em; color: var(--text-3); }
.watch-ret { display: grid; justify-items: end; gap: 1px; }
.watch-ret b { font-family: var(--font-display); font-size: var(--fs-lg); font-weight: 600; letter-spacing: -0.02em; }
.watch-ret span { font-size: var(--fs-xs); }
.rail-foot {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--accent-bg);
  color: var(--text-2);
  font-size: var(--fs-xs);
}
.rail-foot b { color: var(--text-1); }
.rail-empty-text { color: var(--text-2); font-size: var(--fs-sm); line-height: 1.6; margin: 0 0 12px; }
</style>