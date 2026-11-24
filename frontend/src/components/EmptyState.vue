<script setup>
import AppIcon from "./AppIcon.vue";

defineProps({
  glyph: { type: String, default: "◌" },
  icon: { type: String, default: "" },  // 优先内联 SVG 图标名
  title: { type: String, default: "暂无数据" },
  sub: { type: String, default: "" },
});
</script>

<template>
  <div class="empty">
    <div class="glyph">
      <AppIcon v-if="icon" :name="icon" :size="34" />
      <template v-else>{{ glyph }}</template>
    </div>
    <div class="title">{{ title }}</div>
    <div v-if="sub" class="sub">{{ sub }}</div>
    <div class="action" style="margin-top: 12px"><slot /></div>
  </div>
</template>

<style scoped>
.sub { font-size: 12px; }
.glyph { color: var(--text-3); }
</style>
