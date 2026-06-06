<template>
  <div class="app-layout">
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <span class="logo-text">{{ brand.name || 'szyg' }}</span>
        </div>
        <div class="header-nav">
          <el-menu :default-active="activeMenu" mode="horizontal" router :ellipsis="false" class="top-menu">
            <el-menu-item index="/dashboard"><el-icon><HomeFilled /></el-icon>首页</el-menu-item>
            <el-menu-item index="/tools"><el-icon><Box /></el-icon>工具市场</el-menu-item>
            <el-menu-item index="/agents"><el-icon><MagicStick /></el-icon>AI智能体</el-menu-item>
            <el-menu-item index="/publisher"><el-icon><EditPen /></el-icon>内容发布</el-menu-item>
            <el-menu-item index="/scheduler"><el-icon><Timer /></el-icon>调度引擎</el-menu-item>
            <el-menu-item index="/platforms"><el-icon><Monitor /></el-icon>平台管理</el-menu-item>
            <el-menu-item index="/hub"><el-icon><Connection /></el-icon>AI导航</el-menu-item>
            <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon>对话</el-menu-item>
            <el-menu-item index="/image"><el-icon><Picture /></el-icon>绘图</el-menu-item>
            <el-menu-item v-if="isAdmin" index="/admin"><el-icon><Setting /></el-icon>管理</el-menu-item>
          </el-menu>
        </div>
        <div class="header-right">
          <!-- Theme toggle — 💡 lightbulb -->
          <el-tooltip :content="isDark ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
            <span class="theme-toggle" @click="toggleTheme" :title="isDark ? '浅色' : '深色'">
              {{ isDark ? '💡' : '💡' }}
            </span>
          </el-tooltip>

          <!-- Support/Website links -->
          <a v-if="brand.support_url" :href="brand.support_url" target="_blank" class="header-link">{{ brand.support_name }}</a>
          <a v-if="brand.website_url" :href="brand.website_url" target="_blank" class="header-link">{{ brand.website_name }}</a>

          <span class="user-info">{{ user?.username || '未登录' }}</span>
          <el-dropdown @command="handleCommand">
            <el-avatar :size="32" icon="UserFilled" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="oem">品牌设置</el-dropdown-item>
                <el-dropdown-item command="admin" v-if="isAdmin">系统管理</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
      <el-footer class="app-footer">
        <span>{{ brand.copyright || '© 2024 szyg' }}</span>
        <span v-if="brand.disclaimer" class="disclaimer-link" @click="showDisclaimer"> | 免责声明</span>
      </el-footer>
    </el-container>

    <!-- Disclaimer Dialog -->
    <el-dialog v-model="disclaimerVisible" title="免责声明" width="600px">
      <div class="disclaimer-content">{{ brand.disclaimer }}</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Monitor } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
const isAdmin = computed(() => user.value?.role === 'admin')
const activeMenu = ref('/dashboard')
const brand = ref({ name: 'szyg', copyright: '© 2024' })
const disclaimerVisible = ref(false)
const isDark = ref(false)

watch(() => route.path, (path) => { activeMenu.value = path })

onMounted(async () => {
  // Load saved theme preference
  const saved = localStorage.getItem('szyg_theme')
  if (saved === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else if (saved === 'light') {
    isDark.value = false
    document.documentElement.classList.remove('dark')
  }
  // Default: respect system preference
  else if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }

  // Load brand
  try {
    const { data } = await axios.get('/api/oem/config/default')
    brand.value = data
  } catch (_) {}
})

function toggleTheme() {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('szyg_theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('szyg_theme', 'light')
  }
}

function showDisclaimer() { disclaimerVisible.value = true }

function handleCommand(cmd) {
  if (cmd === 'logout') {
    localStorage.removeItem('token'); localStorage.removeItem('user')
    router.push('/login')
  } else if (cmd === 'oem') {
    router.push('/oem')
  } else if (cmd === 'admin') {
    router.push('/admin')
  }
}
</script>

<style scoped>
.app-layout { min-height: 100vh; }

/* ── Header ── */
.app-header {
  display: flex;
  align-items: center;
  padding: 0 20px;
  height: 56px;
  background: var(--header-bg);
  color: var(--header-text);
  border-bottom: 1px solid var(--header-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
html.dark .app-header {
  box-shadow: 0 1px 3px rgba(0,0,0,0.5);
}

.header-left { font-size: 18px; font-weight: 700; margin-right: 24px; letter-spacing: -0.3px; }
.logo-text {
  white-space: nowrap;
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 50%, #0ea5e9 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
html.dark .logo-text {
  background: linear-gradient(135deg, #3b82f6, #818cf8, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.top-menu {
  background: transparent !important;
  border-bottom: none !important;
}

/* ── Header Right ── */
.header-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 💡 Theme Toggle */
.theme-toggle {
  cursor: pointer;
  font-size: 18px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.2s ease;
  user-select: none;
  background: var(--hover-bg);
}
.theme-toggle:hover {
  transform: scale(1.1);
  background: var(--accent-light);
}
html.dark .theme-toggle {
  background: rgba(255,255,255,0.06);
}

.header-link {
  text-decoration: none;
  font-size: 13px;
  color: var(--text-secondary);
  transition: color 0.15s;
}
.header-link:hover { color: var(--accent); }

.user-info {
  font-size: 13px;
  color: var(--header-text);
  font-weight: 500;
}

.disclaimer-link { cursor: pointer; color: var(--text-secondary); }
.disclaimer-link:hover { color: var(--accent); }

/* ── Main ── */
.app-main {
  padding: 24px;
  min-height: calc(100vh - 104px);
  background: var(--bg-main);
}

/* ── Footer ── */
.app-footer {
  text-align: center;
  padding: 10px;
  font-size: 12px;
  background: var(--footer-bg);
  color: var(--footer-text);
  border-top: 1px solid var(--border-color);
}

.disclaimer-content {
  white-space: pre-wrap;
  line-height: 2;
  font-size: 13px;
  max-height: 50vh;
  overflow-y: auto;
}
</style>
