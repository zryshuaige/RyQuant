<script setup>
/** 术语解释:可点击/聚焦的小问号,避免把解释塞成小字。 */
import { ref } from "vue";
import AppIcon from "./AppIcon.vue";

defineProps({
  text: { type: String, required: true },
  label: { type: String, default: "查看说明" },
});
const open = ref(false);
</script>

<template>
  <span class="info-tip">
    <button type="button" class="tip-btn" :aria-label="label" :aria-expanded="open"
      @mouseenter="open = true" @mouseleave="open = false"
      @focus="open = true" @blur="open = false" @click.stop="open = !open"
      @keydown.esc="open = false">
      <AppIcon name="info" :size="14" />
    </button>
    <span v-if="open" class="tip-pop" role="tooltip">{{ text }}</span>
  </span>
</template>

<style scoped>
.info-tip { position: relative; display: inline-flex; vertical-align: -2px; }
.tip-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px; height: 20px;
  padding: 0;
  border: none;
  background: none;
  color: var(--text-3);
  cursor: help;
}
.tip-btn:hover { color: var(--text-2); }
.tip-pop {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 40;
  width: max-content;
  max-width: 260px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--toast-bg);
  backdrop-filter: blur(var(--blur-chrome));
  -webkit-backdrop-filter: blur(var(--blur-chrome));
  color: var(--text-2);
  font-size: var(--fs-xs);
  font-weight: 400;
  line-height: 1.5;
  box-shadow: var(--shadow-2);
  white-space: normal;
}
</style>