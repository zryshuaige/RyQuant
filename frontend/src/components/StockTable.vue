<script setup>
import { computed } from "vue";
import AnimatedNumber from "./AnimatedNumber.vue";
import AppIcon from "./AppIcon.vue";
import { fmtPct, fmtDate } from "../utils/format";

const props = defineProps({
  stocks: { type: Array, required: true },
  favoriteIds: { type: Set, default: () => new Set() },
  selectedSymbol: { type: String, default: "" },
  showFavorite: { type: Boolean, default: true },
  joinedDates: { type: Object, default: null }, // symbol → 加入自选 ISO 日期(自选页展示)
});
const emit = defineEmits(["toggle-fav", "select"]);

const rows = computed(() => props.stocks);
</script>

<template>
  <div class="table-wrap">
    <table class="data">
      <thead>
        <tr>
          <th>代码</th>
          <th>名称</th>
          <th>现价</th>
          <th>涨跌幅</th>
          <th v-if="joinedDates">加入自选</th>
          <th v-if="showFavorite" style="width: 110px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in rows" :key="s.id" class="clickable" :class="{ selected: s.symbol === selectedSymbol }"
          @click="emit('select', s)">
          <td><span class="symbol-badge">{{ s.symbol }}</span></td>
          <td class="stock-name">
            {{ s.name }}
            <span class="tag src-tag" :class="s.quote_source === 'real' ? 'tag-ok' : 'tag-muted'">
              {{ s.quote_source === "real" ? "真实" : "模拟" }}
            </span>
            <AppIcon v-if="favoriteIds.has(s.id)" name="star-filled" :size="12" class="fav-star" title="已自选" />
          </td>
          <td><AnimatedNumber :value="s.price" :class="s.change >= 0 ? 'up' : 'down'" /></td>
          <td><span class="pct-pill" :class="s.change >= 0 ? 'up' : 'down'">{{ fmtPct(s.change_pct) }}</span></td>
          <td v-if="joinedDates" class="num joined-date">{{ fmtDate(joinedDates[s.symbol]) }}</td>
          <td v-if="showFavorite">
            <button class="btn btn-sm" :title="favoriteIds.has(s.id) ? '移除自选' : '加入自选'"
              @click.stop="emit('toggle-fav', s)">
              <AppIcon :name="favoriteIds.has(s.id) ? 'star-filled' : 'star'" :size="13" />
              {{ favoriteIds.has(s.id) ? "自选" : "加自选" }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.stock-name { font-weight: 600; }
.fav-star { color: var(--gold); margin-left: 5px; }
.src-tag { font-size: 10px; padding: 1px 6px; margin-left: 6px; vertical-align: 1px; }
.joined-date { color: var(--gold); font-weight: 600; }
</style>