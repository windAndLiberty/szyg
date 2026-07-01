<template>
  <div class="settings-tools-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-text">
        <h2 class="page-title">工具管理</h2>
        <p class="page-subtitle">AI 智能自动化插件管理</p>
      </div>
      <el-input
        v-model="searchQuery"
        placeholder="搜索工具..."
        prefix-icon="Search"
        class="search-input"
        clearable
      />
    </div>

    <!-- Stats Cards -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="8">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ installedCount }}</div>
          <div class="stat-label">已安装工具</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ runningCount }}</div>
          <div class="stat-label">运行中工具</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card" shadow="never">
          <div class="stat-value">{{ totalCalls.toLocaleString() }}</div>
          <div class="stat-label">总调用次数</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tool Cards Grid -->
    <el-row :gutter="16" class="tools-grid">
      <el-col
        :xs="24" :sm="12" :md="8" :lg="8"
        v-for="tool in filteredTools"
        :key="tool.id"
      >
        <el-card
          class="tool-card"
          shadow="hover"
          @click="openDetail(tool)"
        >
          <div class="tool-card-body">
            <div class="tool-icon">{{ tool.icon }}</div>
            <div class="tool-name">{{ tool.name }}</div>
            <div class="tool-desc">{{ tool.description }}</div>
            <div class="tool-meta">
              <el-tag
                :type="statusTagType(tool.status)"
                size="small"
                effect="light"
              >
                {{ statusLabel(tool.status) }}
              </el-tag>
              <span class="tool-calls">{{ tool.calls.toLocaleString() }} 次调用</span>
            </div>
            <div class="tool-actions" @click.stop>
              <el-button
                size="small"
                :type="tool.status === 'running' ? 'warning' : 'success'"
                @click="toggleStatus(tool)"
              >
                {{ tool.status === 'running' ? '停止' : '启动' }}
              </el-button>
              <el-button
                size="small"
                type="danger"
                plain
                @click="uninstallTool(tool)"
              >
                卸载
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Detail Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="selectedTool?.name"
      size="480px"
      :with-header="true"
      class="tool-drawer"
    >
      <div v-if="selectedTool" class="drawer-content">
        <div class="drawer-icon">{{ selectedTool.icon }}</div>
        <div class="drawer-desc">{{ selectedTool.description }}</div>

        <el-divider />

        <h4 class="drawer-section-title">参数配置</h4>
        <el-form label-width="120px" class="drawer-form">
          <el-form-item label="并发限制">
            <el-input-number v-model="detailConfig.concurrency" :min="1" :max="10" />
          </el-form-item>
          <el-form-item label="超时时间 (秒)">
            <el-input-number v-model="detailConfig.timeout" :min="5" :max="300" />
          </el-form-item>
          <el-form-item label="启用日志">
            <el-switch v-model="detailConfig.logging" />
          </el-form-item>
        </el-form>

        <el-divider />

        <h4 class="drawer-section-title">调用历史</h4>
        <el-timeline>
          <el-timeline-item
            v-for="(h, idx) in callHistory"
            :key="idx"
            :type="h.status === 'success' ? 'success' : 'danger'"
            :timestamp="h.time"
          >
            {{ h.action }}
          </el-timeline-item>
        </el-timeline>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { getErrorMessage } from '@/api'
import { useConfirmAction } from '@/composables/useConfirmAction'

// ── API Data ──
const tools = ref([])
const searchQuery = ref('')

async function loadTools() {
  try {
    const [{ data: catalog }, { data: installedList }] = await Promise.all([
      axios.get('/api/tools/catalog'),
      axios.get('/api/tools/installed'),
    ])
    const catalogArr = Array.isArray(catalog) ? catalog : (catalog.data || [])
    const installedArr = Array.isArray(installedList) ? installedList : (installedList.data || [])
    const installedIds = new Set(installedArr.map(i => i.soft_id))
    tools.value = catalogArr.map(t => ({
      ...t,
      name: t.title || t.name || t.id,
      description: t.desc || t.description || '',
      status: installedIds.has(t.id) ? 'stopped' : 'not_installed',
      calls: 0,
    }))
  } catch (e) {
    ElMessage.error('加载工具失败: ' + getErrorMessage(e))
  }
}

onMounted(() => {
  loadTools()
})

const filteredTools = computed(() => {
  if (!searchQuery.value) return tools.value
  const q = searchQuery.value.toLowerCase()
  return tools.value.filter(
    t => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
  )
})

const installedCount = computed(() => tools.value.filter(t => t.status !== 'not_installed').length)
const runningCount = computed(() => tools.value.filter(t => t.status === 'running').length)
const totalCalls = computed(() => tools.value.reduce((sum, t) => sum + t.calls, 0))

function statusTagType(status) {
  switch (status) {
    case 'running': return 'success'
    case 'stopped': return 'info'
    case 'not_installed': return 'info'
    default: return 'info'
  }
}

function statusLabel(status) {
  switch (status) {
    case 'running': return '运行中'
    case 'stopped': return '已停止'
    case 'not_installed': return '未安装'
    default: return status
  }
}

async function toggleStatus(tool) {
  try {
    if (tool.status === 'running') {
      await axios.post(`/api/tools/stop/${tool.id}`)
      tool.status = 'stopped'
      ElMessage.info(`${tool.name} 已停止`)
    } else {
      await axios.post(`/api/tools/launch/${tool.id}`)
      tool.status = 'running'
      ElMessage.success(`${tool.name} 已启动`)
    }
  } catch (e) {
    ElMessage.error('操作失败: ' + getErrorMessage(e))
  }
}

const { run: uninstallTool } = useConfirmAction({
  confirm: (t) => `确定要卸载 ${t.name} 吗？此操作不可撤销。`,
  confirmTitle: '卸载确认',
  confirmButton: '卸载',
  action: (t) => axios.delete(`/api/tools/uninstall/${t.id}`),
  onSuccess: (t) => { t.status = 'not_installed'; t.calls = 0 },
  successMsg: (t) => `${t.name} 已卸载`,
  errorPrefix: '卸载',
})

// ── Drawer ──
const drawerVisible = ref(false)
const selectedTool = ref(null)
const detailConfig = reactive({ concurrency: 4, timeout: 60, logging: true })

const callHistory = [
  { action: '生成月度报告.docx', status: 'success', time: '2026-06-28 10:23' },
  { action: '批量处理 Excel 数据', status: 'success', time: '2026-06-28 09:45' },
  { action: '转换 PPT 模板失败', status: 'error', time: '2026-06-27 18:12' },
  { action: 'PDF 合并任务', status: 'success', time: '2026-06-27 16:30' },
  { action: '视频切片导出', status: 'success', time: '2026-06-27 14:05' },
]

function openDetail(tool) {
  selectedTool.value = tool
  drawerVisible.value = true
}
</script>

<style scoped>
.settings-tools-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

/* Header */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.search-input {
  width: 280px;
}

/* Stats */
.stats-row {
  margin-bottom: 24px;
}
.stat-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  text-align: center;
  padding: 20px 0;
  border-radius: var(--radius-md);
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--accent-primary);
  font-variant-numeric: tabular-nums;
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 6px;
}

/* Tool Cards */
.tools-grid {
  margin-top: 8px;
}
.tool-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  margin-bottom: 16px;
}
.tool-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--border-active);
}
.tool-card-body {
  text-align: center;
  padding: 8px 4px;
}
.tool-icon {
  font-size: 48px;
  line-height: 1;
  margin-bottom: 12px;
}
.tool-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.tool-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 36px;
  margin-bottom: 12px;
  padding: 0 8px;
}
.tool-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 14px;
}
.tool-calls {
  font-size: 12px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.tool-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
}

/* Drawer */
.drawer-content {
  padding: 8px 4px;
}
.drawer-icon {
  font-size: 64px;
  text-align: center;
  margin-bottom: 16px;
}
.drawer-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  text-align: center;
}
.drawer-section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 16px 0 12px;
}
.drawer-form :deep(.el-form-item__label) {
  color: var(--text-secondary);
}

/* Responsive */
@media (max-width: 1280px) {
  .search-input { width: 220px; }
}
</style>
