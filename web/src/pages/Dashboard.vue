<template>
  <div class="dashboard">
    <!-- Announcements -->
    <div v-if="announcements.length" class="announce-bar">
      <el-alert
        v-for="a in announcements" :key="a.id"
        :title="a.title" :description="a.content"
        :type="a.level" :closable="false" show-icon
        class="announce-item" />
    </div>

    <!-- 1. 快捷指令输入区 -->
    <section class="quick-command-section">
      <div class="command-input-wrapper">
        <el-input
          v-model="commandText"
          placeholder="输入指令，如：帮我发3条抖音视频并处理评论区私信"
          class="command-input"
          @keyup.enter="sendCommand"
        />
        <el-button type="primary" class="send-btn" @click="sendCommand">
          <span class="send-icon">⚡</span> 发送
        </el-button>
      </div>
      <div class="quick-tags">
        <el-tag
          v-for="tag in quickTags"
          :key="tag"
          class="quick-tag"
          effect="plain"
          round
          @click="fillCommand(tag)"
        >
          {{ tag }}
        </el-tag>
      </div>
    </section>

    <!-- 2. 员工状态卡片行 -->
    <section class="staff-cards-section">
      <el-row :gutter="20">
        <el-col :span="6" v-for="staff in staffList" :key="staff.name">
          <el-card class="staff-card" shadow="never" @click="goToStudio(staff.route)">
            <div class="staff-card-inner">
              <div class="staff-avatar">{{ staff.emoji }}</div>
              <div class="staff-info">
                <div class="staff-name-row">
                  <span class="staff-name">{{ staff.name }}</span>
                  <span class="status-dot" :class="staff.status"></span>
                </div>
                <div class="staff-status-text">{{ statusText(staff.status) }}</div>
              </div>
            </div>
            <div class="staff-progress">
              <el-progress
                :percentage="staff.progress"
                :color="statusColor"
                :stroke-width="6"
                :show-text="false"
              />
              <div class="staff-done">今日完成: {{ staff.completed }}</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </section>

    <!-- 3. Kanban + 今日数据 -->
    <el-row :gutter="20" class="main-content-row">
      <!-- 左侧 Kanban -->
      <el-col :span="16">
        <el-card class="kanban-card" shadow="never">
          <div class="kanban-header">
            <h3 class="section-title">任务看板</h3>
            <el-button text type="primary" size="small" @click="router.push('/ai-staff/tasks')">
              查看全部 →
            </el-button>
          </div>
          <div class="kanban-board">
            <div v-for="col in kanbanColumns" :key="col.key" class="kanban-column">
              <div class="kanban-column-header">
                <span class="column-title">{{ col.title }}</span>
                <span class="column-count">{{ col.tasks.length }}</span>
              </div>
              <div class="kanban-task-list">
                <div
                  v-for="task in col.tasks"
                  :key="task.id"
                  class="kanban-task-card"
                >
                  <div class="task-name">{{ task.name }}</div>
                  <div class="task-meta">
                    <span class="task-assignee">{{ task.assignee }}</span>
                    <el-progress
                      :percentage="task.progress"
                      :color="statusColor"
                      :stroke-width="4"
                      :show-text="false"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧今日数据 -->
      <el-col :span="8">
        <el-card class="metrics-card" shadow="never">
          <h3 class="section-title">今日数据</h3>
          <div class="metrics-list">
            <div v-for="m in metrics" :key="m.label" class="metric-item">
              <div class="metric-label">{{ m.label }}</div>
              <div class="metric-value-row">
                <span class="metric-value">{{ m.value }}</span>
                <span
                  class="metric-change"
                  :class="m.change >= 0 ? 'up' : 'down'"
                >
                  {{ m.change >= 0 ? '↗' : '↘' }} {{ Math.abs(m.change) }}%
                </span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useSuperStaffStore } from '../stores/superStaff'

const router = useRouter()
const superStaffStore = useSuperStaffStore()
const announcements = ref([])
const commandText = ref('')

const quickTags = ['一键上班', '生成今日内容', '检查平台状态', '处理昨日私信']

const staffList = ref([])
const kanbanColumns = ref([])
const metrics = ref([])

const statusColor = 'var(--accent-primary)'

function fillCommand(tag) {
  commandText.value = tag
}

function sendCommand() {
  if (!commandText.value.trim()) {
    ElMessage.warning('请输入指令内容')
    return
  }
  const prompt = commandText.value.trim()
  commandText.value = ''
  // Open SuperStaff panel and inject the prompt
  superStaffStore.submitPrompt(prompt)
}

function statusText(status) {
  return status === 'running' ? '运行中' : '空闲'
}

function goToStudio(route) {
  router.push(route)
}

onMounted(async () => {
  // 公告（独立加载，不影响其他模块）
  try {
    const announceRes = await axios.get('/api/announce/list')
    announcements.value = announceRes.data?.slice(0, 3) || []
  } catch (_) {
    announcements.value = []
  }

  // 并行获取 Dashboard 数据
  const results = await Promise.allSettled([
    axios.get('/api/publisher/stats'),
    axios.get('/api/acquisition/leads/stats'),
    axios.get('/api/acquisition/leads/funnel'),
    axios.get('/api/acquisition/customers'),
    axios.get('/api/staff/list'),
    axios.get('/api/staff/tasks/list'),
  ])

  const [pubR, leadStatsR, funnelR, customersR, staffR, tasksR] = results

  // ── 指标卡片 ──
  const pubStats = pubR.status === 'fulfilled' ? pubR.value.data : {}
  const leadStats = leadStatsR.status === 'fulfilled' ? leadStatsR.value.data : {}
  const funnel = funnelR.status === 'fulfilled' ? funnelR.value.data : {}
  const customers = customersR.status === 'fulfilled' ? customersR.value.data : {}
  metrics.value = [
    { label: '当前发布', value: String(pubStats.published ?? 0), change: 0 },
    { label: '线索总数', value: String(leadStats.total ?? 0), change: 0 },
    { label: '客户总数', value: String(customers.total ?? 0), change: 0 },
    { label: '转化率',   value: (funnel.conversion_rate ?? 0).toFixed(1) + '%', change: 0 },
  ]

  // ── 员工卡片 ──
  if (staffR.status === 'fulfilled') {
    staffList.value = staffR.value.data?.staff || []
  }

  // ── 看板（按 status 分组） ──
  if (tasksR.status === 'fulfilled') {
    const tasks = tasksR.value.data?.tasks || []
    const cols = [
      { key: 'ready', title: 'Ready' },
      { key: 'running', title: 'Running' },
      { key: 'blocked', title: 'Blocked' },
      { key: 'done', title: 'Done' },
    ]
    kanbanColumns.value = cols.map(col => ({
      ...col,
      tasks: tasks.filter(t => t.status === col.key),
    }))
  }
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

/* ── Announcements ── */
.announce-bar {
  margin-bottom: 16px;
}
.announce-item {
  margin-bottom: 8px;
}

/* ── 1. 快捷指令输入区 ── */
.quick-command-section {
  margin-bottom: 20px;
}

.command-input-wrapper {
  display: flex;
  width: 100%;
  height: 48px;
}

.command-input {
  flex: 1;
}

.command-input :deep(.el-input__wrapper) {
  height: 48px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-right: none;
  box-shadow: none;
  border-radius: var(--radius-md) 0 0 var(--radius-md);
  padding-left: 16px;
}

.command-input :deep(.el-input__inner) {
  color: var(--text-primary);
  height: 48px;
  font-size: 14px;
}

.command-input :deep(.el-input__inner::placeholder) {
  color: var(--placeholder-color);
}

.send-btn {
  height: 48px;
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  padding: 0 24px;
  font-weight: 600;
  font-size: 14px;
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: var(--text-inverse);
  transition: all 0.2s ease;
}

.send-btn:hover {
  filter: brightness(1.15);
  box-shadow: var(--btn-shadow);
}

.send-icon {
  margin-right: 4px;
}

.quick-tags {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.quick-tag {
  cursor: pointer;
  background: var(--card-bg);
  border-color: var(--border-color);
  color: var(--text-secondary);
  transition: all 0.2s ease;
  user-select: none;
}

.quick-tag:hover {
  border-color: var(--accent-primary);
  color: var(--accent-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* ── 2. 员工状态卡片 ── */
.staff-cards-section {
  margin-bottom: 20px;
}

.staff-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.3s var(--ease-out-expo);
}

.staff-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--border-active);
}

.staff-card :deep(.el-card__body) {
  padding: 16px;
}

.staff-card-inner {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.staff-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--accent-light);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}

.staff-info {
  flex: 1;
  min-width: 0;
}

.staff-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.staff-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.status-dot.running {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.status-dot.idle {
  background: var(--text-muted);
}

.staff-status-text {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.staff-progress {
  margin-top: 8px;
}

.staff-progress :deep(.el-progress-bar__outer) {
  background: var(--hover-bg);
  border-radius: 3px;
}

.staff-progress :deep(.el-progress-bar__inner) {
  border-radius: 3px;
  background-color: var(--accent-primary) !important;
}

.staff-done {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
}

/* ── 3. Kanban + 今日数据 ── */
.main-content-row {
  margin-bottom: 20px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* Kanban */
.kanban-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  height: 100%;
}

.kanban-card :deep(.el-card__body) {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.kanban-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.kanban-board {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.kanban-column {
  flex: 1;
  min-width: 0;
  background: var(--bg-main);
  border-radius: var(--radius-md);
  padding: 12px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.kanban-column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.column-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.column-count {
  font-size: 12px;
  color: var(--text-tertiary);
  background: var(--hover-bg);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.kanban-task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.kanban-task-card {
  background: var(--card-bg);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  transition: all 0.2s ease;
  cursor: default;
}

.kanban-task-card:hover {
  border-color: var(--border-active);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.task-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
  line-height: 1.4;
}

.task-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-assignee {
  font-size: 11px;
  color: var(--text-tertiary);
  background: var(--accent-light);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  align-self: flex-start;
}

.task-meta :deep(.el-progress-bar__outer) {
  background: var(--hover-bg);
  border-radius: 2px;
}

.task-meta :deep(.el-progress-bar__inner) {
  border-radius: 2px;
  background-color: var(--accent-primary) !important;
}

/* 今日数据 */
.metrics-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  height: 100%;
}

.metrics-card :deep(.el-card__body) {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.metrics-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
  flex: 1;
}

.metric-item {
  background: var(--bg-main);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 16px;
  transition: all 0.2s ease;
}

.metric-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--border-active);
}

.metric-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.metric-value-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.metric-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.metric-change {
  font-size: 12px;
  font-weight: 600;
}

.metric-change.up {
  color: var(--green-500);
}

.metric-change.down {
  color: var(--rose-500);
}

/* ── 响应式适配 ── */
@media (max-width: 1279px) {
  .staff-cards-section .el-col,
  .main-content-row .el-col {
    min-width: 50%;
    max-width: 50%;
  }
}

@media (max-width: 991px) {
  .staff-cards-section .el-col,
  .main-content-row .el-col {
    min-width: 100%;
    max-width: 100%;
  }

  .kanban-board {
    flex-wrap: wrap;
  }

  .kanban-column {
    min-width: calc(50% - 6px);
    flex: 1 1 calc(50% - 6px);
  }
}

@media (max-width: 767px) {
  .kanban-column {
    min-width: 100%;
    flex: 1 1 100%;
  }
}
</style>
