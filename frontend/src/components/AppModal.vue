<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from "vue";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: "" },
  width: { type: Number, default: 480 },
});
const emit = defineEmits(["update:modelValue"]);

const cardEl = ref(null);
let lastActive = null;
const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function close() {
  emit("update:modelValue", false);
}

function onKeydown(e) {
  if (e.key === "Escape") return close();
  if (e.key !== "Tab" || !cardEl.value) return;
  // 焦点陷阱:Tab 循环限制在模态内
  const items = [...cardEl.value.querySelectorAll(FOCUSABLE)].filter((el) => !el.disabled);
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      lastActive = document.activeElement;
      document.addEventListener("keydown", onKeydown);
      nextTick(() => {
        const items = cardEl.value?.querySelectorAll(FOCUSABLE);
        (items?.[0] || cardEl.value)?.focus();
      });
    } else {
      document.removeEventListener("keydown", onKeydown);
      lastActive?.focus?.();  // 关闭后焦点归还原触发元素
      lastActive = null;
    }
  }
);
onBeforeUnmount(() => document.removeEventListener("keydown", onKeydown));
</script>

<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="modelValue" class="modal-overlay" @mousedown.self="close">
        <div ref="cardEl" class="modal-card" :style="{ maxWidth: `${width}px` }" role="dialog" aria-modal="true" tabindex="-1">
          <div class="modal-head">
            <h3 class="modal-title">{{ title }}</h3>
            <button class="modal-close" aria-label="关闭" @click="close">×</button>
          </div>
          <slot />
        </div>
      </div>
    </transition>
  </teleport>
</template>
