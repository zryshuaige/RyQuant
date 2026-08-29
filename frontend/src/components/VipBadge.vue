<script setup>
defineProps({ active: { type: Boolean, default: false } });
</script>

<template>
  <span v-if="active" class="tag tag-gold shimmer">VIP</span>
  <span v-else class="tag tag-muted">未开通</span>
</template>
