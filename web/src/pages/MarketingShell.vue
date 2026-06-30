<template>
  <div class="section-shell">
    <div v-if="isRoot" class="shell-center">
      <h2>营销拓客</h2>
      <p>请从左侧导航选择具体功能模块</p>
    </div>
    <router-view />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isRoot = computed(() => route.path === '/marketing')
</script>

<style scoped>
.section-shell { min-height: 100%; display: flex; flex-direction: column; }
.shell-center { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; color: var(--text-secondary); }
.shell-center h2 { margin: 0 0 8px; font-size: 20px; color: var(--text-primary); }
.shell-center p { margin: 0; font-size: 13px; }
</style>
