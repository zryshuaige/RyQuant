<script setup>
import { orderStatus } from "../utils/format";

defineProps({ status: { type: String, required: true } });
</script>

<template>
  <span class="tag" :class="`tag-${orderStatus(status).tone}`">{{ orderStatus(status).label }}</span>
</template>
