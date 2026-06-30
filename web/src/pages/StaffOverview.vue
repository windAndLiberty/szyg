<template>
  <div class="staff-overview">
    <h2 class="page-title">员工概览</h2>
    <el-row :gutter="20">
      <el-col
        v-for="staff in staffList"
        :key="staff.name"
        :xs="12"
        :sm="12"
        :md="6"
      >
        <el-card
          class="staff-card"
          shadow="never"
          @click="openDrawer(staff)"
        >
          <div class="card-header">
            <div class="staff-emoji">{{ staff.emoji }}</div>
            <div class="staff-info">
              <div class="staff-name">
                {{ staff.name }}
                <span
                  class="status-dot"
                  :style="{ backgroundColor: staff.status === 'running' ? '#22c55e' : '#9ca3af' }"
                />
              </div>
              <div class="staff-status-text">
                {{ staff.status === 'running' ? '运行中' : '空闲' }}
              </div>
            </div>
          </div>

          <div class="card-metrics">
            <div class="metric">
              <span class="metric-label">今日任务</span>
              <span class="metric-value">{{ staff.tasksToday }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">已完成</span>
              <span class="metric-value">{{ staff.completed }}</span>
            </div>
          </div>

          <div class="card-progress">
            <el-progress
              :percentage="staff.progress"
              :color="progressColor"
              :stroke-width="8"
              :show-text="true"
            />
          </div>

          <div class="card-recent">
            <span class="recent-label">{{ staff.recent }}</span>
          </div>

          <div class="card-footer">
            <el-button
              type="primary"
              size="small"
              @click.stop="goToStudio(staff.route)"
            >
              前往工作室
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 员工详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="selectedStaff?.name"
      size="400px"
      :with-header="true"
      direction="rtl"
    >
      <div v-if="selectedStaff" class="drawer-content">
        <div class="drawer-header">
          <div class="drawer-emoji">{{ selectedStaff.emoji }}</div>
          <div class="drawer-title-row">
            <span class="drawer-name">{{ selectedStaff.name }}</span>
            <span
              class="status-dot"
              :style="{ backgroundColor: selectedStaff.status === 'running' ? '#22c55e' : '#9ca3af' }"
            />
            <span class="drawer-status-text">
              {{ selectedStaff.status === 'running' ? '运行中' : '空闲' }}
            </span>
          </div>
        </div>

        <div class="drawer-section">
          <div class="section-title">能力列表</div>
          <div class="skill-tags">
            <el-tag
              v-for="skill in selectedStaff.skills"
              :key="skill"
              type="info"
              effect="plain"
              size="small"
              class="skill-tag"
            >
              {{ skill }}
            </el-tag>
          </div>
        </div>

        <div class="drawer-section">
          <div class="section-title">近期任务</div>
          <div class="recent-tasks">
            <div
              v-for="(task, idx) in recentTasks"
              :key="idx"
              class="recent-task-item"
            >
              <span class="task-name">{{ task.name }}</span>
              <el-tag :type="task.tagType" size="small" class="task-tag">
                {{ task.status }}
              </el-tag>
            </div>
          </div>
        </div>

        <div class="drawer-section">
          <div class="section-title">今日统计</div>
          <div class="stats-row">
            <div class="stat-item">
              <span class="stat-value">{{ selectedStaff.tasksToday }}</span>
              <span class="stat-label">今日任务</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ selectedStaff.completed }}</span>
              <span class="stat-label">已完成</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ selectedStaff.progress }}%</span>
              <span class="stat-label">总进度</span>
            </div>
          </div>
        </div>

        <div class="drawer-footer">
          <el-button
            type="primary"
            @click="goToStudio(selectedStaff.route)"
          >
            前往工作室
          </el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()

const staffList = ref([])
const loading = ref(false)
const progressColor = ref('var(--accent)')

const drawerVisible = ref(false)
const selectedStaff = ref(null)
const recentTasks = ref([])

async function loadStaff() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/staff/list')
    staffList.value = data.staff || []
  } catch (e) {
    ElMessage.error('加载员工数据失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function loadRecentTasks(assignee) {
  try {
    const { data } = await axios.get('/api/staff/tasks/list')
    const tasks = (data.tasks || []).filter(t => t.assignee === assignee).slice(0, 5)
    recentTasks.value = tasks.map(t => ({
      name: t.name,
      status: t.status === 'done' ? '已完成' : t.status === 'running' ? '进行中' : t.status === 'review' ? '审核中' : '待处理',
      tagType: t.status === 'done' ? 'success' : t.status === 'running' ? 'primary' : t.status === 'review' ? 'warning' : 'info',
    }))
  } catch {
    recentTasks.value = []
  }
}

const openDrawer = (staff) => {
  selectedStaff.value = staff
  loadRecentTasks(staff.name)
  drawerVisible.value = true
}

const goToStudio = (route) => {
  router.push(route)
  ElMessage.success('正在跳转...')
}

onMounted(() => {
  loadStaff()
})
</script>

<style scoped>
.staff-overview {
  padding: 24px;
}

.page-title {
  margin: 0 0 20px;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.staff-card {
  background: var(--bg-card);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: box-shadow var(--duration-fast) ease;
}

.staff-card:hover {
  box-shadow: var(--shadow-float);
}

:deep(.el-card__body) {
  padding: 24px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.staff-emoji {
  font-size: 36px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.staff-info {
  flex: 1;
  min-width: 0;
}

.staff-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.staff-status-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.card-metrics {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.card-progress {
  margin-bottom: 12px;
}

.card-progress :deep(.el-progress__text) {
  font-size: 12px;
  color: var(--text-secondary);
}

.card-recent {
  margin-bottom: 16px;
}

.recent-label {
  font-size: 12px;
  color: var(--text-tertiary);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
}

/* Drawer Styles */
.drawer-content {
  padding: 8px 0;
}

.drawer-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-light);
  margin-bottom: 20px;
}

.drawer-emoji {
  font-size: 56px;
  margin-bottom: 12px;
}

.drawer-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drawer-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.drawer-status-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.drawer-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.skill-tag {
  background: var(--bg-hover) !important;
  border-color: var(--border-light) !important;
  color: var(--text-secondary) !important;
}

.recent-tasks {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.recent-task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.task-name {
  font-size: 13px;
  color: var(--text-primary);
}

.task-tag {
  flex-shrink: 0;
  margin-left: 8px;
}

.stats-row {
  display: flex;
  gap: 12px;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.drawer-footer {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

.drawer-footer .el-button {
  width: 100%;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .staff-overview {
    padding: 16px;
  }

  .card-metrics {
    gap: 12px;
  }

  .stats-row {
    flex-wrap: wrap;
  }

  .stat-item {
    flex: 1 1 calc(50% - 6px);
  }
}
</style>
