<template>
  <button class="super-staff-fab" @click="togglePanel">
    <svg class="fab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  </button>
</template>

<script setup>
import { useSuperStaffStore } from '../stores/superStaff'
const store = useSuperStaffStore()
function togglePanel() { store.toggle() }
</script>

<style scoped>
.super-staff-fab {
  position: fixed; bottom: 24px; right: 24px; z-index: 2000;
  width: 56px; height: 56px; border-radius: 50%; border: none; cursor: pointer;
  background: var(--accent);
  color: #fff; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 16px rgba(79, 70, 229, 0.3);
  animation: fabPulse 2s ease-in-out infinite;
  transition: transform 0.2s;
}
.super-staff-fab:hover { transform: scale(1.08); }
.fab-icon { width: 24px; height: 24px; }
@keyframes fabPulse {
  0% { box-shadow: 0 0 0 0 rgba(79,70,229,0.3); }
  70% { box-shadow: 0 0 0 15px rgba(79,70,229,0); }
  100% { box-shadow: 0 0 0 0 rgba(79,70,229,0); }
}
</style>
