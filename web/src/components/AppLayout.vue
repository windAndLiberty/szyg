<template>
  <div class="app-layout">
    <!-- ═══ Sidebar ═══ -->
    <aside class="app-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <!-- Logo -->
      <div class="sidebar-logo" @click="router.push('/super-agent').catch(() => {})">
        <span class="logo-text" v-show="!sidebarCollapsed">{{ brand.name || 'szyg' }}</span>
        <span class="logo-icon" v-show="sidebarCollapsed">S</span>
      </div>

      <!-- Nav groups -->
      <nav class="sidebar-nav">
        <div v-for="group in navGroups" :key="group.label" class="nav-group">
          <div class="nav-group-header" @click="toggleGroup(group.label)">
            <span class="nav-group-label" v-show="!sidebarCollapsed">{{ group.label }}</span>
            <el-icon class="nav-group-arrow" v-show="!sidebarCollapsed">
              <ArrowDown v-if="expandedGroups.has(group.label)" />
              <ArrowRight v-else />
            </el-icon>
          </div>
          <transition name="expand">
            <div v-show="expandedGroups.has(group.label) && !sidebarCollapsed" class="nav-items">
              <div
                v-for="item in group.items"
                :key="item.path"
                class="nav-item"
                :class="{ active: isRouteActive(item.path) }"
                @click="router.push(item.path).catch(() => {})"
              >
                <el-icon class="nav-item-icon"><component :is="item.icon" /></el-icon>
                <span class="nav-item-label">{{ item.label }}</span>
              </div>
            </div>
          </transition>
        </div>
      </nav>

      <!-- Collapse toggle -->
      <div class="sidebar-footer">
        <div class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <el-icon><Fold v-if="!sidebarCollapsed" /><Expand v-else /></el-icon>
        </div>
      </div>
    </aside>

    <!-- ═══ Main Area ═══ -->
    <div class="app-main-area">
      <!-- Top bar -->
      <header class="app-topbar">
        <div class="topbar-left">
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="topbar-right">
          <!-- Theme switcher -->
          <el-dropdown trigger="click" @command="setTheme">
            <span class="theme-switcher">
              <el-icon><Brush /></el-icon>
              <span class="theme-name">{{ themeLabel }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="light" :class="{ 'is-current': currentTheme === 'light' }">Effie Light</el-dropdown-item>
                <el-dropdown-item command="dark" :class="{ 'is-current': currentTheme === 'dark' }">Effie Dark</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <span class="user-name">{{ user?.username || '未登录' }}</span>
          <el-avatar :size="28" icon="UserFilled" />
        </div>
      </header>

      <!-- Content -->
      <main class="app-content" :class="{ 'full-bleed': route.meta.fullBleed }">
        <router-view v-slot="{ Component }">
          <component :is="Component" />
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  ChatDotRound, Setting,
  ArrowDown, ArrowRight, Fold, Expand, Brush, UserFilled,
} from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

let userValue = null
try {
  userValue = JSON.parse(localStorage.getItem('user') || 'null')
} catch {
  userValue = null
}
const user = ref(userValue)
const brand = ref({ name: 'szyg' })
const sidebarCollapsed = ref(false)
const currentTheme = ref('light')
const expandedGroups = ref(new Set(['AI 员工', '系统设置']))

const themeLabels = { light: 'Effie Light', dark: 'Effie Dark' }
const themeLabel = computed(() => themeLabels[currentTheme.value] || 'Light')

const navGroups = [
  {
    label: 'AI 员工',
    items: [
      { path: '/super-agent', label: '超级员工', icon: ChatDotRound },
    ],
  },
]

const currentTitle = computed(() => {
  for (const group of navGroups) {
    const item = group.items.find(i => route.path.startsWith(i.path))
    if (item) return item.label
  }
  return 'szyg'
})

function isRouteActive(path) {
  return route.path === path || route.path.startsWith(path + '/')
}

function toggleGroup(label) {
  if (expandedGroups.value.has(label)) {
    expandedGroups.value.delete(label)
  } else {
    expandedGroups.value.add(label)
  }
  expandedGroups.value = new Set(expandedGroups.value)
}

function setTheme(theme) {
  currentTheme.value = theme
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('szyg_theme', theme)
}

onMounted(async () => {
  const saved = localStorage.getItem('szyg_theme') || 'light'
  setTheme(saved)

  try {
    const { data } = await axios.get('/api/oem/config/default')
    if (data.name) brand.value = data
  } catch (_) {}
})
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg-body);
}

/* ═══ Sidebar ═══ */
.app-sidebar {
  width: 200px;
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--duration-normal) var(--ease-smooth);
  overflow: hidden;
}
.app-sidebar.collapsed { width: 64px; }

.sidebar-logo {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  cursor: pointer;
  flex-shrink: 0;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}
.logo-icon {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
}

.nav-group { margin-bottom: 4px; }

.nav-group-header {
  display: flex;
  align-items: center;
  padding: 0 12px;
  cursor: pointer;
  user-select: none;
  margin-bottom: 8px;
}
.nav-group-label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.2px;
  color: var(--text-tertiary);
}
.nav-group-arrow {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-tertiary);
}

.nav-items { padding: 2px 0; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all var(--duration-fast) var(--ease-smooth);
  border-radius: var(--radius-sm);
}
.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 500;
}
.nav-item-icon {
  font-size: 16px;
  flex-shrink: 0;
}
.nav-item-label { white-space: nowrap; }

.sidebar-footer {
  flex-shrink: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-top: 1px solid var(--border-light);
}
.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  transition: all var(--duration-fast) var(--ease-smooth);
}
.collapse-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* ═══ Main Area ═══ */
.app-main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.app-topbar {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 24px;
  background: var(--bg-page);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}
.topbar-left { flex: 1; }
.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.theme-switcher {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) ease;
}
.theme-switcher:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.user-name {
  font-size: 13px;
  color: var(--text-secondary);
}

.app-content {
  flex: 1;
  padding: 32px;
  overflow-y: auto;
  background: var(--bg-body);
}

.app-content.full-bleed {
  padding: 0;
}

/* Responsive padding */
@media (max-width: 1279px) {
  .app-content { padding: 24px; }
}
@media (max-width: 767px) {
  .app-content { padding: 16px; }
}

/* ═══ Expand transition ═══ */
.expand-enter-active, .expand-leave-active {
  transition: all var(--duration-normal) var(--ease-smooth);
  overflow: hidden;
}
.expand-enter-from, .expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to, .expand-leave-from {
  opacity: 1;
  max-height: 300px;
}
</style>
