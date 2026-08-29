<script setup>
defineProps({
  glyph: { type: String, default: "◌" },
  title: { type: String, default: "暂无数据" },
  sub: { type: String, default: "" },
});
</script>

<template>
  <div class="empty">
    <div class="glyph">{{ glyph }}</div>
    <div class="title">{{ title }}</div>
    <div v-if="sub" class="sub">{{ sub }}</div>
    <div class="action" style="margin-top: 12px"><slot /></div>
  </div>
</template>

<style scoped>
.sub { font-size: 12.5px; }
</style>
