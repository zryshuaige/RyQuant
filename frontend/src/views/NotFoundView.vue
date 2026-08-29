<template>
  <div class="page nf">
    <div class="code num">404</div>
    <p class="msg">这个页面被市场蒸发了。</p>
    <router-link class="btn btn-primary" :to="{ name: 'home' }">返回行情总览</router-link>
  </div>
</template>

<style scoped>
.nf { text-align: center; padding-top: 12vh; }
.code {
  font-size: 110px;
  font-weight: 800;
  background: var(--brand-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 0 24px rgba(34, 211, 238, 0.35));
  line-height: 1;
}
.msg { color: var(--text-2); margin: 12px 0 22px; }
</style>
