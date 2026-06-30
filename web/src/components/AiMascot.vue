<template>
  <div class="core-wrapper" :class="{ 'core-visible': visible }">
    <svg viewBox="0 0 100 100" class="core-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <!-- Soft glow -->
        <filter id="coreGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur"/>
          <feMerge>
            <feMergeNode in="blur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
        <!-- Radial gradient for center -->
        <radialGradient id="centerGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#67e8f9" stop-opacity="0.9"/>
          <stop offset="50%" stop-color="#22d3ee" stop-opacity="0.4"/>
          <stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/>
        </radialGradient>
        <!-- Ring gradient -->
        <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#22d3ee" stop-opacity="0.6"/>
          <stop offset="50%" stop-color="#3b82f6" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="#8b5cf6" stop-opacity="0.15"/>
        </linearGradient>
      </defs>

      <!-- Outer soft halo -->
      <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(34,211,238,0.06)" stroke-width="12" filter="url(#coreGlow)"/>

      <!-- Outer ring -->
      <circle cx="50" cy="50" r="38" fill="none" stroke="url(#ringGrad)" stroke-width="1" opacity="0.7"/>

      <!-- Inner ring -->
      <circle cx="50" cy="50" r="28" fill="none" stroke="rgba(34,211,238,0.12)" stroke-width="0.5"/>

      <!-- Cross lines -->
      <line x1="50" y1="12" x2="50" y2="88" stroke="rgba(34,211,238,0.08)" stroke-width="0.5"/>
      <line x1="12" y1="50" x2="88" y2="50" stroke="rgba(34,211,238,0.08)" stroke-width="0.5"/>

      <!-- Center orb -->
      <circle cx="50" cy="50" r="6" fill="url(#centerGrad)" filter="url(#coreGlow)" class="center-orb"/>

      <!-- Center dot -->
      <circle cx="50" cy="50" r="2" fill="#a5f3fc" opacity="0.9"/>
    </svg>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const visible = ref(false)
onMounted(() => {
  setTimeout(() => { visible.value = true }, 100)
})
</script>

<style scoped>
.core-wrapper {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
  position: relative;
  opacity: 0;
  transform: scale(0.85);
  transition: opacity 0.8s var(--ease-out-expo), transform 0.8s var(--ease-out-expo);
}

.core-wrapper.core-visible {
  opacity: 1;
  transform: scale(1);
}

.core-svg {
  width: 100%;
  height: 100%;
  animation: coreFloat 6s ease-in-out infinite;
}

.center-orb {
  animation: coreBreathe 4s ease-in-out infinite;
  transform-origin: center;
}

@keyframes coreFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

@keyframes coreBreathe {
  0%, 100% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.3); opacity: 1; }
}
</style>
