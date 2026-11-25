<script setup>
/** 分页脚:左「共 N 条 · 第 x/y 页」,右 页大小 + 页码(>7 页省略) */
import { computed } from "vue";
import { pageList } from "../composables/usePagedSort";

const props = defineProps({
  page: { type: Number, required: true },
  pageSize: { type: Number, default: 10 },
  total: { type: Number, default: 0 },
  totalPages: { type: Number, default: 1 },
  sizes: { type: Array, default: () => [10, 20, 50] },
});
const emit = defineEmits(["update:page", "update:pageSize"]);

const pages = computed(() => pageList(props.page, props.totalPages));
</script>

<template>
  <div v-if="total > 0" class="pager">
    <span class="pager-info">共 {{ total }} 条 · 第 {{ page }}/{{ totalPages }} 页</span>
    <div class="pager-right">
      <select class="select pager-size" :value="pageSize" aria-label="每页条数"
        @change="emit('update:pageSize', Number($event.target.value))">
        <option v-for="s in sizes" :key="s" :value="s">{{ s }} 条/页</option>
      </select>
      <nav class="pager-pages" aria-label="分页">
        <button class="page-btn" :disabled="page <= 1" aria-label="上一页" @click="emit('update:page', page - 1)">‹</button>
        <template v-for="(p, i) in pages" :key="i">
          <span v-if="typeof p === 'string'" class="page-gap">…</span>
          <button v-else class="page-btn" :class="{ on: p === page }" :aria-current="p === page ? 'page' : undefined"
            :aria-label="`第 ${p} 页`" @click="emit('update:page', p)">{{ p }}</button>
        </template>
        <button class="page-btn" :disabled="page >= totalPages" aria-label="下一页" @click="emit('update:page', page + 1)">›</button>
      </nav>
    </div>
  </div>
</template>