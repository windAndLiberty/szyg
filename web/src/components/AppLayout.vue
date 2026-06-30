<template>
  <div class="app-layout">
    <el-container>
      <!-- ═══ Top Header ═══ -->
      <el-header class="app-header">
        <div class="header-left">
          <span class="logo-text">{{ brand.name || 'szyg' }}</span>
        </div>
        <div class="header-nav">
          <el-menu
            :default-active="activeSection"
            mode="horizontal"
            :ellipsis="false"
            class="top-menu"
            @select="onNavSelect"
          >
            <el-menu-item index="ai-staff">
              <el-icon><User /></el-icon>
              <span>AI员工</span>
            </el-menu-item>
            <el-menu-item index="content">
              <el-icon><Box /></el-icon>
              <span>内容工厂</span>
            </el-menu-item>
            <el-menu-item index="marketing">
              <el-icon><Promotion /></el-icon>
              <span>营销拓客</span>
            </el-menu-item>
            <el-menu-item index="insights">
              <el-icon><TrendCharts /></el-icon>
              <span>数据洞察</span>
            </el-menu-item>
          </el-menu>
          <el-dropdown trigger="click" @command="onNavSelect" class="more-nav">
            <span class="more-trigger">
              更多<el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="workflow">
                  <el-icon><Connection /></el-icon> 工作流编排
                </el-dropdown-item>
                <el-dropdown-item command="knowledge">
                  <el-icon><Collection /></el-icon> 知识库
                </el-dropdown-item>
                <el-dropdown-item command="settings">
                  <el-icon><Setting /></el-icon> 系统设置
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div class="header-right">
          <el-tooltip v-if="activeStreams > 0" content="AI 员工正在工作中…" placement="bottom">
            <span class="streaming-dot">
              <span class="dot-pulse"></span>
              <span class="stream-label">{{ activeStreams }} 活跃</span>
            </span>
          </el-tooltip>
          <el-tooltip :content="isDark ? '浅色模式' : '深色模式'" placement="bottom">
            <span class="theme-toggle" @click="toggleTheme">{{ isDark ? '🌙' : '☀️' }}</span>
          </el-tooltip>
          <a v-if="brand.support_url" :href="brand.support_url" target="_blank" class="header-link">{{ brand.support_name }}</a>
          <span class="user-info">{{ user?.username || '未登录' }}</span>
          <el-dropdown @command="handleCommand">
            <el-avatar :size="32" icon="UserFilled" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="brand">品牌配置</el-dropdown-item>
                <el-dropdown-item command="team" v-if="isAdmin">团队管理</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- ═══ Body: Sidebar + Main ═══ -->
      <el-container class="body-container">
        <el-aside v-if="sidebarItems.length" class="app-sidebar" :style="{ width: sidebarWidth }">
          <el-menu
            :default-active="sidebarActiveIndex"
            :collapse="sidebarCollapsed"
            class="side-menu"
            @select="onSidebarSelect"
          >
            <div class="sidebar-section-title">{{ sidebarTitle }}</div>
            <template v-for="item in sidebarItems" :key="item.path">
              <el-menu-item v-if="!item.admin || isAdmin" :index="item.path">
                <el-icon><component :is="item.icon" /></el-icon>
                <template #title>
                  <span class="sidebar-item-label">{{ item.label }}</span>
                  <el-tag v-if="item.tag" size="small" :type="item.tagType || 'primary'" class="sidebar-tag">{{ item.tag }}</el-tag>
                </template>
              </el-menu-item>
            </template>
          </el-menu>
          <div class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
            {{ sidebarCollapsed ? '▶' : '◀' }}
          </div>
        </el-aside>

        <el-main class="app-main">
          <router-view v-slot="{ Component }">
            <keep-alive :include="keepAlivePages">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </el-main>
      </el-container>

      <el-footer class="app-footer">
        <span>{{ brand.copyright || '© 2024 szyg' }}</span>
        <span v-if="brand.disclaimer" class="disclaimer-link" @click="showDisclaimer"> | 免责声明</span>
      </el-footer>
    </el-container>

    <el-dialog v-model="disclaimerVisible" title="免责声明" width="600px">
      <div class="disclaimer-content">{{ brand.disclaimer }}</div>
    </el-dialog>

    <SuperStaffButton />
    <SuperStaffPanel />
    <OnboardingGuide v-if="showOnboarding" @complete="showOnboarding = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  TrendCharts, User, ChatLineSquare, Box, Setting,
  EditPen, ScaleToOriginal, Promotion, Calendar, Timer,
  Picture, VideoCamera, Collection, Connection,
  VideoPlay, Notebook, Search, ChatDotRound, ChatRound,
  Monitor, Message, DataAnalysis, Phone,
  Tickets, List, Histogram, Switch,
  UserFilled, Tools, Lock, Wallet, Coin,
  Position, OfficeBuilding, Reading, PieChart,
  ArrowDown,
} from '@element-plus/icons-vue'
import axios from 'axios'
import SuperStaffButton from './SuperStaffButton.vue'
import SuperStaffPanel from './SuperStaffPanel.vue'
import OnboardingGuide from './OnboardingGuide.vue'
import { useSuperStaffStore } from '../stores/superStaff'

const router = useRouter()
const route = useRoute()
const superStaffStore = useSuperStaffStore()

// ── State ──
const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
const isAdmin = computed(() => user.value?.role === 'admin')
const activeSection = ref('dashboard')
const brand = ref({ name: 'szyg', copyright: '© 2024' })
const disclaimerVisible = ref(false)
const isDark = ref(false)
const sidebarCollapsed = ref(false)
const sidebarWidth = computed(() => sidebarCollapsed.value ? '64px' : '200px')
const keepAlivePages = ['ChatPage']
const activeStreams = ref(0)
const showOnboarding = ref(false)
provide('activeStreams', activeStreams)

// ── Section → default route on header click ──
const sectionRoutes = {
  'ai-staff': '/ai-staff/super-agent',
  'content': '/content/production',
  'marketing': '/marketing/intercept',
  'workflow': '/workflow/pipeline',
  'insights': '/insights/dashboard',
  'knowledge': '/knowledge/base',
  'settings': '/settings/platforms',
}

// ── Route path → section mapping ──
const SECTION_PATTERNS = [
  ['ai-staff',   ['/ai-staff']],
  ['content',    ['/content']],
  ['marketing',  ['/marketing']],
  ['workflow',   ['/workflow']],
  ['insights',   ['/insights']],
  ['knowledge',  ['/knowledge']],
  ['settings',   ['/settings']],
]

const routeToSection = (fullPath) => {
  const path = fullPath.split('?')[0]
  for (const [section, patterns] of SECTION_PATTERNS) {
    if (patterns.some(p => path.startsWith(p))) return section
  }
  return 'ai-staff'
}

watch(() => route.fullPath, (fp) => { activeSection.value = routeToSection(fp) })

// ── Sidebar active index (highlight current route) ──
const sidebarActiveIndex = computed(() => {
  const fp = route.fullPath
  const pathOnly = fp.split('?')[0]
  const items = sidebarItems.value
  const exact = items.find(i => i.path === fp)
  if (exact) return exact.path
  const byPath = items.find(i => i.path === pathOnly)
  if (byPath) return byPath.path
  const prefix = items.filter(i => fp.startsWith(i.path)).sort((a, b) => b.path.length - a.path.length)
  if (prefix.length) return prefix[0].path
  return fp
})

// ── Sidebar definitions (7 sections) ──
const sidebarDefs = {
  'ai-staff': {
    title: 'AI 员工',
    items: [
      { path: '/ai-staff/super-agent',  label: '超级员工',    icon: 'ChatDotRound' },
      { path: '/ai-staff/overview',     label: '员工概览',    icon: 'User' },
      { path: '/ai-staff/tasks',        label: '任务看板',    icon: 'List' },
      { path: '/ai-staff/profiles',     label: '员工配置',    icon: 'Setting' },
    ],
  },
  'content': {
    title: '内容工厂',
    items: [
      { path: '/content/production',    label: '内容生产',    icon: 'EditPen' },
      { path: '/content/video-editor',  label: '视频剪辑',    icon: 'VideoPlay' },
      { path: '/content/digital-human', label: '数字人',      icon: 'VideoCamera' },
      { path: '/content/assets',        label: '内容资产',    icon: 'Box' },
      { path: '/content/publish',       label: '多平台发布',  icon: 'Promotion' },
    ],
  },
  'marketing': {
    title: '营销拓客',
    items: [
      { path: '/marketing/intercept',   label: '智能截流',    icon: 'Search' },
      { path: '/marketing/listen',      label: '舆情监听',    icon: 'Monitor' },
      { path: '/marketing/conversion',  label: '客户转化',    icon: 'ChatLineSquare' },
      { path: '/marketing/ab-test',     label: 'A/B测试',     icon: 'ScaleToOriginal' },
      { path: '/marketing/customers',   label: '客户资产',    icon: 'UserFilled' },
      { path: '/marketing/enterprise',  label: '企业获客',    icon: 'OfficeBuilding' },
      { path: '/marketing/nfc',         label: '到店引流',    icon: 'Position' },
    ],
  },
  'workflow': {
    title: '工作流编排',
    items: [
      { path: '/workflow/pipeline',   label: '流水线编排',  icon: 'Connection' },
      { path: '/workflow/scheduler',  label: '调度引擎',    icon: 'Timer' },
      { path: '/workflow/sop',        label: 'SOP管理',     icon: 'Notebook' },
    ],
  },
  'insights': {
    title: '数据洞察',
    items: [
      { path: '/insights/dashboard',             label: '运营仪表盘',  icon: 'TrendCharts' },
      { path: '/insights/content-analytics',     label: '内容分析',    icon: 'Histogram' },
      { path: '/insights/acquisition-analytics', label: '截流效果',    icon: 'DataAnalysis' },
      { path: '/insights/conversion-analytics',  label: '转化分析',    icon: 'PieChart' },
    ],
  },
  'knowledge': {
    title: '知识库',
    items: [
      { path: '/knowledge/base',    label: '知识管理',    icon: 'Collection' },
      { path: '/knowledge/memory',  label: '长期记忆',    icon: 'Coin' },
      { path: '/knowledge/skills',  label: '技能市场',    icon: 'Tickets' },
      { path: '/knowledge/academy', label: '商学院',      icon: 'Reading' },
    ],
  },
  'settings': {
    title: '系统设置',
    items: [
      { path: '/settings/platforms',    label: '平台账号', icon: 'Switch',     admin: false },
      { path: '/settings/risk-control', label: '风控策略', icon: 'Lock' },
      { path: '/settings/tools',        label: '工具管理', icon: 'Tools' },
      { path: '/settings/system',       label: '系统配置', icon: 'Setting' },
      { path: '/settings/brand',        label: '品牌配置', icon: 'EditPen',    admin: true },
      { path: '/settings/team',         label: '团队管理', icon: 'UserFilled', admin: true },
      { path: '/settings/billing',      label: '计费管理', icon: 'Wallet',     admin: true },
    ],
  },
}

const sidebarTitle = computed(() => sidebarDefs[activeSection.value]?.title || '')
const sidebarItems = computed(() => sidebarDefs[activeSection.value]?.items || [])

// ── Navigation handlers ──
function onNavSelect(index) {
  activeSection.value = index
  const target = sectionRoutes[index]
  if (target) router.push(target).catch(() => {})
}

function onSidebarSelect(index) {
  router.push(index).catch(() => {})
}

// ── Auto-open SuperStaff panel from query ──
watch(() => route.query.panel, (panel) => {
  if (panel === 'open') {
    superStaffStore.open()
  }
})

// ── Theme & init ──
onMounted(async () => {
  const saved = localStorage.getItem('szyg_theme')
  if (saved === 'dark') {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    isDark.value = false
    document.documentElement.classList.remove('dark')
    if (!saved) localStorage.setItem('szyg_theme', 'light')
  }

  try {
    const { data } = await axios.get('/api/oem/config/default')
    brand.value = data
  } catch (_) {}

  activeSection.value = routeToSection(route.fullPath)

  // Check initial panel query
  if (route.query.panel === 'open') {
    superStaffStore.open()
  }

  // Onboarding check
  const onboardingCompleted = localStorage.getItem('szyg_onboarding_completed')
  if (!onboardingCompleted && route.path !== '/login') {
    showOnboarding.value = true
  }
})

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('szyg_theme', isDark.value ? 'dark' : 'light')
}

function showDisclaimer() { disclaimerVisible.value = true }

function handleCommand(cmd) {
  if (cmd === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
  } else if (cmd === 'brand') {
    router.push('/settings/brand')
  } else if (cmd === 'team') {
    router.push('/settings/team')
  }
}
</script>

<style scoped>
.app-layout { min-height: 100vh; }

/* ═══ Header ═══ */
.app-header {
  display: flex; align-items: center; padding: 0 16px; height: 56px;
  background: var(--header-bg); color: var(--header-text);
  border-bottom: 1px solid var(--header-border);
  z-index: 100;
}

.header-left { font-size: 18px; font-weight: 700; margin-right: 12px; flex-shrink: 0; }
.logo-text {
  white-space: nowrap;
  background: var(--logo-gradient);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}

.header-nav { flex: 1; overflow: hidden; display: flex; align-items: center; gap: 8px; }
.top-menu { background: transparent !important; border-bottom: none !important; }
.top-menu .el-menu-item {
  font-size: 13px; font-weight: 500; padding: 0 10px; gap: 6px;
}

.more-nav { flex-shrink: 0; }
.more-trigger {
  display: flex; align-items: center; gap: 4px;
  font-size: 13px; font-weight: 500; color: var(--text-secondary);
  cursor: pointer; padding: 0 8px; height: 56px;
  transition: color var(--duration-fast) ease;
}
.more-trigger:hover { color: var(--accent); }

.header-right { margin-left: auto; display: flex; align-items: center; gap: 14px; }

.theme-toggle {
  cursor: pointer; font-size: 18px; width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; transition: all 0.2s; user-select: none;
}
.theme-toggle:hover { transform: scale(1.1); }

/* SSE stream indicator */
.streaming-dot { display: inline-flex; align-items: center; gap: 6px; margin-right: 4px; }
.dot-pulse {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--accent);
  display: inline-block;
  animation: dotPulse 1.2s ease-in-out infinite;
}
.stream-label { font-size: 11px; color: var(--accent); font-weight: 500; white-space: nowrap; }

@keyframes dotPulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.header-link { text-decoration: none; font-size: 13px; color: var(--text-secondary); white-space: nowrap; }
.header-link:hover { color: var(--accent); }
.user-info { font-size: 13px; color: var(--header-text); font-weight: 500; white-space: nowrap; }

/* ═══ Body ═══ */
.body-container { min-height: calc(100vh - 106px); }

/* ═══ Sidebar ═══ */
.app-sidebar {
  background: var(--sidebar-bg, var(--bg-page));
  border-right: 1px solid var(--border-light);
  position: relative;
  transition: width 0.2s ease;
  overflow: hidden;
  flex-shrink: 0;
}
.side-menu { border-right: none !important; background: transparent; }
.sidebar-section-title {
  padding: 16px 20px 8px;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  color: var(--text-tertiary); letter-spacing: 1px;
}
.sidebar-item-label { font-size: 13px; }
.sidebar-tag { margin-left: auto; font-size: 10px; transform: scale(0.85); flex-shrink: 0; }
.sidebar-toggle {
  position: absolute; bottom: 20px; left: 0; right: 0;
  text-align: center; cursor: pointer; font-size: 12px;
  color: var(--text-secondary); padding: 8px; user-select: none;
}
.sidebar-toggle:hover { color: var(--accent); background: var(--hover-bg); }

/* ═══ Main ═══ */
.app-main {
  padding: 24px; flex: 1;
  min-height: calc(100vh - 160px);
  background: var(--bg-main);
}

/* ═══ Footer ═══ */
.app-footer {
  text-align: center; padding: 10px; font-size: 12px;
  background: var(--footer-bg); color: var(--footer-text);
  border-top: 1px solid var(--border-light);
}
.disclaimer-link { cursor: pointer; color: var(--text-secondary); }
.disclaimer-link:hover { color: var(--accent); }
.disclaimer-content {
  white-space: pre-wrap; line-height: 2; font-size: 13px; max-height: 50vh; overflow-y: auto;
}

/* ═══ Dark mode ═══ */
html.dark .app-header {
  border-bottom-color: var(--border-color);
}

html.dark .top-menu .el-menu-item.is-active {
  border-bottom: 2px solid var(--accent) !important;
  color: var(--accent) !important;
}

html.dark .side-menu .el-menu-item.is-active {
  background: var(--accent-soft) !important;
  color: var(--accent) !important;
}

html.dark .logo-text {
  background: var(--logo-gradient);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
</style>
