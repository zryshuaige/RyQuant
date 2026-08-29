<script setup>
import { toastState } from "../composables/useToast";
</script>

<template>
  <div class="toast-host" role="status" aria-live="polite">
    <transition-group name="toast-slide">
      <div v-for="t in toastState.toasts" :key="t.id" class="toast" :class="t.type">
        <span class="dot"></span>
        <span>{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>
