<template>
  <div class="page nf">
    <div class="code num">404</div>
    <h1 class="msg">页面不存在</h1>
    <p class="sub">链接可能已失效,回到行情总览继续。</p>
    <router-link class="btn btn-primary" :to="{ name: 'home' }">返回行情总览</router-link>
  </div>
</template>

<style scoped>
.nf { text-align: center; padding-top: 12vh; }
.code { font-family: var(--font-display); font-size: 72px; font-weight: 600; letter-spacing: -0.04em; color: var(--text-3); line-height: 1; }
.msg { font-size: var(--fs-xl); margin: 14px 0 6px; }
.sub { color: var(--text-2); margin: 0 0 22px; font-size: var(--fs-sm); }
</style>