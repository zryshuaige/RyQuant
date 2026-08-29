<script setup>
import { watch } from "vue";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: "" },
  width: { type: Number, default: 480 },
});
const emit = defineEmits(["update:modelValue"]);

function close() {
  emit("update:modelValue", false);
}

function onKeydown(e) {
  if (e.key === "Escape") close();
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) document.addEventListener("keydown", onKeydown);
    else document.removeEventListener("keydown", onKeydown);
  }
);
</script>

<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="modelValue" class="modal-overlay" @mousedown.self="close">
        <div class="modal-card" :style="{ maxWidth: `${width}px` }" role="dialog" aria-modal="true">
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
