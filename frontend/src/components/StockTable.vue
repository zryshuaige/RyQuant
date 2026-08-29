<script setup>
import { computed } from "vue";
import AnimatedNumber from "./AnimatedNumber.vue";
import { fmtPct } from "../utils/format";

const props = defineProps({
  stocks: { type: Array, required: true },
  favoriteIds: { type: Set, default: () => new Set() },
  selectedSymbol: { type: String, default: "" },
  showFavorite: { type: Boolean, default: true },
});
const emit = defineEmits(["order", "toggle-fav", "select"]);

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
          <th style="width: 160px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in rows" :key="s.id" class="clickable" :class="{ selected: s.symbol === selectedSymbol }"
          @click="emit('select', s)">
          <td><span class="symbol-badge">{{ s.symbol }}</span></td>
          <td class="stock-name">{{ s.name }}<span v-if="favoriteIds.has(s.id)" class="fav-star" title="已自选">★</span></td>
          <td><AnimatedNumber :value="s.price" :class="s.change >= 0 ? 'up' : 'down'" /></td>
          <td><span class="pct-pill" :class="s.change >= 0 ? 'up' : 'down'">{{ fmtPct(s.change_pct) }}</span></td>
          <td>
            <div class="actions">
              <button v-if="showFavorite" class="btn btn-sm" :title="favoriteIds.has(s.id) ? '移除自选' : '加入自选'"
                @click.stop="emit('toggle-fav', s)">
                {{ favoriteIds.has(s.id) ? "★ 自选" : "☆ 加自选" }}
              </button>
              <button class="btn btn-sm" :class="s.change >= 0 ? 'btn-up' : 'btn-down'" @click.stop="emit('order', s)">
                下单
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.stock-name { font-weight: 600; }
.fav-star { color: var(--gold); margin-left: 5px; font-size: 12px; }
.actions { display: flex; gap: 7px; }
</style>
