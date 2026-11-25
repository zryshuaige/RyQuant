<script setup>
/** 受控数据表:排序表头(aria-sort)/ 数字右对齐 / sticky 表头 / 行点击与键盘语义 */
import { computed } from "vue";

const props = defineProps({
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  sortKey: { type: String, default: "" },
  sortDir: { type: String, default: "desc" },
  rowKey: { type: [String, Function], default: "id" },
  selectedKey: { type: [String, Number], default: "" },
  clickable: { type: Boolean, default: true },
});
const emit = defineEmits(["sort", "select"]);

function keyOf(row) {
  return typeof props.rowKey === "function" ? props.rowKey(row) : row?.[props.rowKey];
}
function valueOf(row, col) {
  return typeof col.value === "function" ? col.value(row) : row?.[col.key];
}
function ariaSort(col) {
  if (!col.sortable || props.sortKey !== col.key) return col.sortable ? "none" : undefined;
  return props.sortDir === "asc" ? "ascending" : "descending";
}
const hasRows = computed(() => props.rows.length > 0);

function onRowKey(event, row) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    emit("select", row);
  }
}
</script>

<template>
  <div v-if="hasRows" class="table-wrap dt-wrap">
    <table class="data">
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" scope="col" :class="{ right: col.align === 'right', 'hide-mobile': col.hideMobile }"
            :style="col.width ? { width: col.width } : undefined" :aria-sort="ariaSort(col)">
            <button v-if="col.sortable" type="button" class="th-sort" :class="{ sorted: sortKey === col.key }"
              @click="emit('sort', col.key)">
              {{ col.label }}
              <span class="sort-arrow" aria-hidden="true">{{ sortKey === col.key ? (sortDir === "asc" ? "↑" : "↓") : "↕" }}</span>
            </button>
            <template v-else>{{ col.label }}</template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="keyOf(row)" :class="{ clickable, selected: selectedKey !== '' && keyOf(row) === selectedKey }"
          :tabindex="clickable ? 0 : undefined" :aria-current="selectedKey !== '' && keyOf(row) === selectedKey ? 'true' : undefined"
          @click="clickable && emit('select', row)" @keydown="clickable && onRowKey($event, row)">
          <td v-for="col in columns" :key="col.key" :class="[col.align === 'right' ? 'right num' : '', col.mono ? 'mono' : '', col.hideMobile ? 'hide-mobile' : '']">
            <slot :name="`cell-${col.key}`" :row="row" :value="valueOf(row, col)">{{ valueOf(row, col) }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <slot v-else name="empty">
    <div class="empty">
      <div class="title">没有数据</div>
      <div class="sub">换个条件试试。</div>
    </div>
  </slot>
</template>

<style scoped>
.dt-wrap table.data th { position: sticky; top: 0; z-index: 1; background: var(--panel); }
</style>