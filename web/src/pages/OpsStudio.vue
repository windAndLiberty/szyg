<template>
  <div class="ops-studio">
    <h2 class="page-title">运营工作室</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <!-- ════════════════════════════════════════════════════════════ Tab 1: 调度引擎 ═══════ -->
      <el-tab-pane label="调度引擎" name="scheduler">
        <div class="tab-content">
          <!-- 触发器列表 -->
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="section-header">
                <span>触发器列表</span>
                <el-button type="primary" size="small" @click="createTask"><el-icon><Plus /></el-icon>新建任务</el-button>
              </div>
            </template>
            <el-table :data="scheduledTasks" stripe>
              <el-table-column prop="name" label="任务名称" min-width="160" />
              <el-table-column label="触发类型" width="100">
                <template #default="{row}">
                  <el-tag :type="triggerTagType(row.trigger)" size="small" effect="plain">{{ triggerLabel(row.trigger) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="触发配置" width="140">
                <template #default="{row}">
                  <span v-if="row.trigger === 'cron'" class="config-text">{{ row.cron }}</span>
                  <span v-else-if="row.trigger === 'interval'" class="config-text">每 {{ row.interval }} 分钟</span>
                  <span v-else class="config-text">{{ row.event }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="nextRun" label="下次执行" width="150" />
              <el-table-column label="状态" width="90">
                <template #default="{row}">
                  <el-switch v-model="row.status" active-value="active" inactive-value="paused" inline-prompt active-text="运行" inactive-text="暂停" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="220">
                <template #default="{row}">
                  <el-button size="small" @click="editTask(row)">编辑</el-button>
                  <el-button size="small" type="warning" plain @click="toggleTask(row)">{{ row.status === 'active' ? '暂停' : '恢复' }}</el-button>
                  <el-button size="small" type="primary" plain @click="runTaskNow(row)">立即执行</el-button>
                  <el-button size="small" type="danger" text @click="deleteTask(row)"><el-icon><Delete /></el-icon></el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 日历视图 -->
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="section-header">
                <span>日历视图</span>
                <div class="calendar-controls">
                  <el-radio-group v-model="calendarView" size="small">
                    <el-radio-button label="month">月视图</el-radio-button>
                    <el-radio-button label="week">周视图</el-radio-button>
                  </el-radio-group>
                  <el-button size="small" text @click="prevPeriod"><el-icon><ArrowLeft /></el-icon></el-button>
                  <span class="calendar-title">{{ calendarTitle }}</span>
                  <el-button size="small" text @click="nextPeriod"><el-icon><ArrowRight /></el-icon></el-button>
                  <el-button size="small" @click="goToday">今天</el-button>
                </div>
              </div>
            </template>

            <!-- 月视图 -->
            <div v-if="calendarView === 'month'" class="calendar-month">
              <div class="cal-weekdays">
                <div v-for="d in ['周一','周二','周三','周四','周五','周六','周日']" :key="d" class="cal-weekday">{{ d }}</div>
              </div>
              <div class="cal-grid">
                <div v-for="day in calendarDays" :key="day.date" :class="['cal-day', { 'other-month': !day.isCurrentMonth, 'today': day.isToday, 'selected': selectedDate === day.date }]" @click="selectDate(day.date)">
                  <div class="day-num">{{ day.day }}</div>
                  <div class="day-dots">
                    <span v-for="(task, i) in day.tasks" :key="i" class="day-dot" :style="{ background: taskColor(task.type) }" :title="task.name"></span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 周视图 -->
            <div v-else class="calendar-week">
              <div class="week-header">
                <div v-for="d in weekDays" :key="d.date" :class="['week-day-header', { 'today': d.isToday }]">
                  <div class="week-day-name">{{ d.weekName }}</div>
                  <div class="week-day-num">{{ d.dayNum }}</div>
                </div>
              </div>
              <div class="week-body">
                <div v-for="d in weekDays" :key="d.date" class="week-day-col">
                  <div v-for="task in d.tasks" :key="task.id" class="week-task" :style="{ background: taskColor(task.type), top: task.top + '%', height: task.height + '%' }">
                    <span class="week-task-name">{{ task.name }}</span>
                    <span class="week-task-time">{{ task.time }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 当天任务列表 -->
            <div v-if="selectedDateTasks.length > 0" class="day-tasks">
              <div class="day-tasks-title">{{ selectedDate }} 任务安排（{{ selectedDateTasks.length }} 项）</div>
              <div class="day-task-list">
                <div v-for="task in selectedDateTasks" :key="task.id" class="day-task-item">
                  <span class="task-dot" :style="{ background: taskColor(task.type) }"></span>
                  <span class="task-name">{{ task.name }}</span>
                  <span class="task-time">{{ task.time }}</span>
                  <el-tag size="small" :type="task.status === 'active' ? 'success' : 'info'" effect="plain">{{ task.status === 'active' ? '运行中' : '已暂停' }}</el-tag>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 执行历史 -->
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="section-header">
                <span>执行历史</span>
                <el-button size="small" text @click="historyExpanded = !historyExpanded">
                  {{ historyExpanded ? '收起' : '展开' }}<el-icon><ArrowDown v-if="!historyExpanded" /><ArrowUp v-else /></el-icon>
                </el-button>
              </div>
            </template>
            <el-collapse-transition>
              <div v-show="historyExpanded">
                <el-table :data="executionHistory" stripe size="small">
                  <el-table-column prop="taskName" label="任务名称" min-width="140" />
                  <el-table-column prop="execTime" label="执行时间" width="150" />
                  <el-table-column label="结果" width="90">
                    <template #default="{row}">
                      <el-tag :type="row.result === 'success' ? 'success' : 'danger'" size="small">{{ row.result === 'success' ? '成功' : '失败' }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="log" label="日志摘要" min-width="200" show-overflow-tooltip />
                </el-table>
              </div>
            </el-collapse-transition>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════════════════════ Tab 2: 数据报告 ═══════ -->
      <el-tab-pane label="数据报告" name="report">
        <div class="tab-content">
          <!-- A/B 实验管理 -->
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="section-header">
                <span>A/B 实验管理</span>
                <el-button type="primary" size="small" @click="createExperiment"><el-icon><Plus /></el-icon>新建实验</el-button>
              </div>
            </template>
            <el-table :data="abExperiments" stripe>
              <el-table-column prop="name" label="实验名称" min-width="160" />
              <el-table-column prop="variantA" label="变量 A" width="120" />
              <el-table-column prop="variantB" label="变量 B" width="120" />
              <el-table-column label="状态" width="100">
                <template #default="{row}">
                  <el-tag :type="row.status === 'running' ? 'primary' : 'success'" size="small" effect="dark">{{ row.status === 'running' ? '进行中' : '已完成' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="startTime" label="开始时间" width="150" />
              <el-table-column label="操作" width="180">
                <template #default="{row}">
                  <el-button size="small" type="primary" plain @click="viewResults(row)">查看结果</el-button>
                  <el-button v-if="row.status === 'running'" size="small" type="danger" text @click="stopExperiment(row)">停止</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 策略配置 -->
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="section-header"><span>策略配置</span></div>
            </template>
            <el-row :gutter="16">
              <el-col :span="8" v-for="s in strategies" :key="s.key">
                <div :class="['strategy-card', { active: s.enabled }]" @click="toggleStrategy(s)">
                  <div class="strategy-header">
                    <span class="strategy-name">{{ s.name }}</span>
                    <el-switch v-model="s.enabled" @click.stop />
                  </div>
                  <p class="strategy-desc">{{ s.description }}</p>
                  <div class="strategy-params">
                    <div class="param-row"><span class="param-label">频率限制</span><span class="param-value">{{ s.freq }} 次/小时</span></div>
                    <div class="param-row"><span class="param-label">评论长度</span><span class="param-value">{{ s.commentLen }} 字</span></div>
                    <div class="param-row"><span class="param-label">间隔时间</span><span class="param-value">{{ s.interval }} 秒</span></div>
                  </div>
                </div>
              </el-col>
            </el-row>
          </el-card>

          <!-- 效果对比图表 -->
          <el-card shadow="never" class="section-card">
            <template #header>
              <div class="section-header"><span>策略效果对比</span></div>
            </template>
            <div class="chart-grid">
              <div class="chart-box">
                <div class="chart-title">点击率 (%)</div>
                <div class="bar-chart">
                  <div class="bar-row" v-for="item in chartData" :key="item.label">
                    <span class="bar-label">{{ item.label }}</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: item.ctr + '%', background: item.color }"></div>
                    </div>
                    <span class="bar-value">{{ item.ctr }}%</span>
                  </div>
                </div>
              </div>
              <div class="chart-box">
                <div class="chart-title">回复率 (%)</div>
                <div class="bar-chart">
                  <div class="bar-row" v-for="item in chartData" :key="item.label">
                    <span class="bar-label">{{ item.label }}</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: item.reply + '%', background: item.color }"></div>
                    </div>
                    <span class="bar-value">{{ item.reply }}%</span>
                  </div>
                </div>
              </div>
              <div class="chart-box">
                <div class="chart-title">转化率 (%)</div>
                <div class="bar-chart">
                  <div class="bar-row" v-for="item in chartData" :key="item.label">
                    <span class="bar-label">{{ item.label }}</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: item.conv + '%', background: item.color }"></div>
                    </div>
                    <span class="bar-value">{{ item.conv }}%</span>
                  </div>
                </div>
              </div>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════════════════════ Tab 3: 审计日志 ═══════ -->
      <el-tab-pane label="审计日志" name="audit">
        <div class="tab-content">
          <!-- 筛选区 -->
          <el-card shadow="never" class="section-card">
            <div class="filter-bar">
              <el-select v-model="auditFilters.operator" placeholder="操作者" clearable style="width:140px">
                <el-option label="全部" value="" />
                <el-option label="内容专员" value="内容专员" />
                <el-option label="获客专员" value="获客专员" />
                <el-option label="运营主管" value="运营主管" />
                <el-option label="系统" value="系统" />
              </el-select>
              <el-select v-model="auditFilters.action" placeholder="操作类型" clearable style="width:130px">
                <el-option label="全部" value="" />
                <el-option label="创建" value="create" />
                <el-option label="修改" value="update" />
                <el-option label="删除" value="delete" />
                <el-option label="查询" value="query" />
                <el-option label="发送" value="send" />
              </el-select>
              <el-select v-model="auditFilters.target" placeholder="目标类型" clearable style="width:130px">
                <el-option label="全部" value="" />
                <el-option label="内容" value="content" />
                <el-option label="评论" value="comment" />
                <el-option label="任务" value="task" />
                <el-option label="配置" value="config" />
                <el-option label="用户" value="user" />
              </el-select>
              <el-date-picker v-model="auditFilters.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" style="width:240px" />
              <el-input v-model="auditFilters.search" placeholder="搜索关键词..." clearable style="width:200px">
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
              <el-button type="primary" @click="refreshLogs"><el-icon><Refresh /></el-icon>查询</el-button>
            </div>
          </el-card>

          <!-- 日志列表 -->
          <el-card shadow="never" class="section-card">
            <el-table :data="filteredLogs" stripe @expand-change="onExpandLog" row-key="id">
              <el-table-column type="expand" width="40">
                <template #default="{ row }">
                  <div class="log-expand">
                    <div class="expand-title">全链路回溯</div>
                    <el-timeline>
                      <el-timeline-item v-for="(link, i) in row.chain" :key="i" :type="link.type" :timestamp="link.time">
                        <div class="chain-node">
                          <div class="chain-title">{{ link.title }}</div>
                          <div class="chain-desc">{{ link.description }}</div>
                        </div>
                      </el-timeline-item>
                    </el-timeline>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="time" label="时间" width="160" sortable />
              <el-table-column prop="operator" label="操作者" width="100" />
              <el-table-column label="操作类型" width="90">
                <template #default="{row}">
                  <el-tag :type="actionTagType(row.action)" size="small" effect="dark">{{ actionLabel(row.action) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="target" label="目标" width="100">
                <template #default="{row}">
                  <span>{{ row.target }} <span class="target-id">{{ row.targetId }}</span></span>
                </template>
              </el-table-column>
              <el-table-column label="结果" width="80">
                <template #default="{row}">
                  <el-tag :type="row.result === 'success' ? 'success' : 'danger'" size="small">{{ row.result === 'success' ? '成功' : '失败' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
            </el-table>
            <el-pagination class="log-pagination" background layout="prev, pager, next, total" :total="filteredLogs.length" :page-size="10" />
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

// ==================== 通用 ====================
const activeTab = ref('scheduler')

// ==================== Tab 1: 调度引擎 ====================
const scheduledTasks = ref([])
const executionHistory = ref([])
const abExperiments = ref([])
const strategies = ref([])
const logs = ref([])

async function loadOpsData() {
  try {
    const [{ data: tasks }, { data: history }, { data: experiments }, { data: strategiesData }, { data: logsData }, { data: chart }] = await Promise.all([
      axios.get('/api/scheduler/jobs'),
      axios.get('/api/scheduler/history'),
      axios.get('/api/acquisition/ab-test'),
      axios.get('/api/acquisition/strategy'),
      axios.get('/api/scheduler/audit-logs'),
      axios.get('/api/scheduler/chart-data'),
    ])
    scheduledTasks.value = Array.isArray(tasks) ? tasks : []
    executionHistory.value = Array.isArray(history) ? history : []
    abExperiments.value = experiments.tests || []
    strategies.value = strategiesData.strategies || []
    logs.value = logsData.logs || []
    chartData.value = chart.data || []
  } catch (e) {
    ElMessage.error('加载运营数据失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadOpsData()
  loadCalendarData()
})

const triggerLabel = (t) => ({ cron: 'Cron', interval: 'Interval', event: 'Event' }[t] || t)
const triggerTagType = (t) => ({ cron: 'primary', interval: 'success', event: 'warning' }[t] || 'info')

const createTask = () => ElMessage.info('新建任务弹窗：请填写任务信息')
const editTask = (row) => ElMessage.info(`编辑任务：${row.name}`)
async function toggleTask(row) {
  try {
    if (row.status === 'active') {
      await axios.post(`/api/scheduler/jobs/${row.id}/pause`)
      row.status = 'paused'
    } else {
      await axios.post(`/api/scheduler/jobs/${row.id}/resume`)
      row.status = 'active'
    }
    ElMessage.success(`${row.name} 已${row.status === 'active' ? '恢复' : '暂停'}`)
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function runTaskNow(row) {
  try {
    await axios.post(`/api/scheduler/jobs/${row.id}/execute`)
    await loadOpsData()
    ElMessage.success(`任务 ${row.name} 已开始执行`)
  } catch (e) {
    ElMessage.error('执行失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function deleteTask(row) {
  try {
    await ElMessageBox.confirm('确定删除此任务吗？')
    await axios.delete(`/api/scheduler/jobs/${row.id}`)
    scheduledTasks.value = scheduledTasks.value.filter(t => t.id !== row.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

// 日历
const calendarView = ref('month')
const currentDate = ref(new Date())
const selectedDate = ref(new Date().toISOString().slice(0, 10))
const historyExpanded = ref(false)

const calendarTitle = computed(() => {
  const y = currentDate.value.getFullYear()
  const m = currentDate.value.getMonth() + 1
  if (calendarView.value === 'month') return `${y}年 ${m}月`
  const start = new Date(currentDate.value)
  start.setDate(start.getDate() - start.getDay() + 1)
  const end = new Date(start); end.setDate(end.getDate() + 6)
  return `${start.getMonth() + 1}/${start.getDate()} - ${end.getMonth() + 1}/${end.getDate()}`
})

const taskColor = (type) => ({ data: '#4f46e5', publish: '#67c23a', monitor: '#e6a23c', backup: '#909399' }[type] || '#6366f1')

const calendarTaskData = ref([])

async function loadCalendarData() {
  try {
    const { data } = await axios.get('/api/scheduler/jobs')
    const jobs = data || []
    calendarTaskData.value = jobs.map(j => {
      const nextRun = j.next_run_at ? new Date(j.next_run_at) : null
      const date = nextRun ? nextRun.toISOString().slice(0, 10) : ''
      const time = nextRun ? nextRun.toTimeString().slice(0, 5) : ''
      return {
        id: j.id,
        name: j.name,
        date,
        time,
        type: j.tags?.includes('publish') ? 'publish' : j.tags?.includes('monitor') ? 'monitor' : j.tags?.includes('backup') ? 'backup' : 'data',
        status: j.status || 'active',
      }
    })
  } catch (_) {
    calendarTaskData.value = []
  }
}

const calendarDays = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const start = new Date(firstDay); start.setDate(start.getDate() - ((firstDay.getDay() + 6) % 7))
  const days = []
  const today = new Date().toISOString().slice(0, 10)
  for (let i = 0; i < 42; i++) {
    const d = new Date(start); d.setDate(start.getDate() + i)
    const dateStr = d.toISOString().slice(0, 10)
    const isCurrentMonth = d.getMonth() === month
    days.push({
      date: dateStr,
      day: d.getDate(),
      isCurrentMonth,
      isToday: dateStr === today,
      tasks: calendarTaskData.value.filter(t => t.date === dateStr),
    })
  }
  return days
})

const weekDays = computed(() => {
  const start = new Date(currentDate.value)
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7))
  const today = new Date().toISOString().slice(0, 10)
  const names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start); d.setDate(start.getDate() + i)
    const dateStr = d.toISOString().slice(0, 10)
    const tasks = calendarTaskData.value.filter(t => t.date === dateStr).map(t => {
      const [h, m] = t.time.split(':').map(Number)
      const top = ((h + m / 60) / 24) * 100
      const height = (0.5 / 24) * 100
      return { ...t, top, height }
    })
    return { date: dateStr, weekName: names[i], dayNum: d.getDate(), isToday: dateStr === today, tasks }
  })
})

const selectedDateTasks = computed(() => calendarTaskData.value.filter(t => t.date === selectedDate.value))

const selectDate = (date) => { selectedDate.value = date }
const goToday = () => { currentDate.value = new Date(); selectedDate.value = new Date().toISOString().slice(0, 10) }
const prevPeriod = () => {
  if (calendarView.value === 'month') currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() - 1, 1)
  else currentDate.value = new Date(currentDate.value.getTime() - 7 * 86400000)
}
const nextPeriod = () => {
  if (calendarView.value === 'month') currentDate.value = new Date(currentDate.value.getFullYear(), currentDate.value.getMonth() + 1, 1)
  else currentDate.value = new Date(currentDate.value.getTime() + 7 * 86400000)
}

const chartData = ref([])

const createExperiment = () => ElMessage.info('新建实验：请填写实验信息')
const viewResults = (row) => ElMessage.info(`查看实验 ${row.name} 的详细结果`)
async function stopExperiment(row) {
  try {
    await ElMessageBox.confirm('确定停止此实验吗？')
    await axios.post(`/api/acquisition/ab-test/${row.id}/stop`)
    row.status = 'completed'
    ElMessage.success('实验已停止')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('停止失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}
async function toggleStrategy(s) {
  try {
    await axios.post('/api/acquisition/strategy/apply', { platform: 'douyin', strategy: s.key, enabled: !s.enabled })
    s.enabled = !s.enabled
    ElMessage.success(`${s.name} 已${s.enabled ? '启用' : '禁用'}`)
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ==================== Tab 3: 审计日志 ====================
const auditFilters = ref({ operator: '', action: '', target: '', dateRange: null, search: '' })

const filteredLogs = computed(() => {
  return logs.value.filter(l => {
    if (auditFilters.value.operator && l.operator !== auditFilters.value.operator) return false
    if (auditFilters.value.action && l.action !== auditFilters.value.action) return false
    if (auditFilters.value.target && l.target !== auditFilters.value.target) return false
    if (auditFilters.value.search && !l.detail.includes(auditFilters.value.search) && !l.operator.includes(auditFilters.value.search)) return false
    return true
  })
})

const actionLabel = (a) => ({ create: '创建', update: '修改', delete: '删除', query: '查询', send: '发送' }[a] || a)
const actionTagType = (a) => ({ create: 'success', update: 'primary', delete: 'danger', query: 'info', send: 'warning' }[a] || 'info')
const onExpandLog = () => {}
async function refreshLogs() {
  await loadOpsData()
  ElMessage.success('日志已刷新')
}
</script>

<style scoped>
.ops-studio { padding: 24px; }
.page-title { margin: 0 0 20px; font-size: 18px; color: var(--text-primary); font-weight: 600; }
.studio-tabs :deep(.el-tabs__content) { padding: 16px; background: var(--card-bg); border: 1px solid var(--border-color); border-top: none; border-radius: 0 0 8px 8px; }
.tab-content { min-height: 500px; }

/* 通用 */
.section-card { margin-bottom: 20px; }
.section-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; color: var(--text-primary); }

/* 筛选栏 */
.filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.config-text { font-size: 12px; color: var(--text-secondary); font-family: monospace; }

/* 日历 — 月视图 */
.calendar-controls { display: flex; align-items: center; gap: 8px; }
.calendar-title { font-size: 14px; font-weight: 600; color: var(--text-primary); min-width: 120px; text-align: center; }
.calendar-month { margin-top: 8px; }
.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; margin-bottom: 1px; }
.cal-weekday { text-align: center; padding: 8px; font-size: 12px; font-weight: 600; color: var(--text-tertiary); background: var(--bg-main); }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; background: var(--border-color); border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; }
.cal-day { background: var(--card-bg); padding: 6px; min-height: 80px; cursor: pointer; transition: background 0.2s; position: relative; }
.cal-day:hover { background: var(--hover-bg); }
.cal-day.other-month { background: var(--bg-main); color: var(--text-muted); }
.cal-day.today { background: var(--selected-bg); }
.cal-day.today .day-num { color: var(--accent-primary); font-weight: 700; }
.cal-day.selected { outline: 2px solid var(--accent-primary); outline-offset: -2px; }
.day-num { font-size: 13px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px; }
.day-dots { display: flex; gap: 3px; flex-wrap: wrap; }
.day-dot { width: 6px; height: 6px; border-radius: 50%; }

/* 日历 — 周视图 */
.calendar-week { margin-top: 8px; border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; }
.week-header { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; background: var(--border-color); }
.week-day-header { background: var(--bg-main); padding: 10px; text-align: center; }
.week-day-header.today { background: var(--selected-bg); }
.week-day-name { font-size: 12px; color: var(--text-tertiary); }
.week-day-num { font-size: 16px; font-weight: 600; color: var(--text-primary); margin-top: 2px; }
.week-day-header.today .week-day-num { color: var(--accent-primary); }
.week-body { display: grid; grid-template-columns: repeat(7, 1fr); gap: 1px; background: var(--border-color); height: 400px; position: relative; }
.week-day-col { background: var(--card-bg); position: relative; }
.week-task { position: absolute; left: 4px; right: 4px; border-radius: 4px; padding: 2px 6px; font-size: 11px; color: #fff; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; cursor: pointer; }
.week-task-name { font-weight: 600; }
.week-task-time { opacity: 0.8; margin-left: 4px; }

/* 当天任务 */
.day-tasks { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-color); }
.day-tasks-title { font-weight: 600; color: var(--text-primary); margin-bottom: 10px; font-size: 14px; }
.day-task-list { display: flex; flex-direction: column; gap: 8px; }
.day-task-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; background: var(--bg-main); }
.task-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.task-name { flex: 1; font-size: 13px; color: var(--text-primary); }
.task-time { font-size: 12px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }

/* 策略卡片 */
.strategy-card { border: 1px solid var(--border-color); border-radius: 12px; padding: 16px; cursor: pointer; transition: box-shadow 0.2s, border-color 0.2s; background: var(--card-bg); margin-bottom: 16px; }
.strategy-card:hover { border-color: var(--accent-primary); box-shadow: var(--shadow-md); }
.strategy-card.active { border-color: var(--accent-primary); background: var(--hover-bg); }
.strategy-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.strategy-name { font-weight: 700; font-size: 16px; color: var(--text-primary); }
.strategy-desc { font-size: 13px; color: var(--text-secondary); margin: 0 0 12px; line-height: 1.5; }
.strategy-params { display: flex; flex-direction: column; gap: 6px; }
.param-row { display: flex; justify-content: space-between; font-size: 12px; }
.param-label { color: var(--text-tertiary); }
.param-value { color: var(--text-primary); font-weight: 600; font-variant-numeric: tabular-nums; }

/* 条形图 */
.chart-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
@media (max-width: 1279px) { .chart-grid { grid-template-columns: 1fr; } }
.chart-box { background: var(--bg-main); border-radius: 10px; padding: 16px; }
.chart-title { font-weight: 600; color: var(--text-primary); margin-bottom: 16px; font-size: 14px; }
.bar-chart { display: flex; flex-direction: column; gap: 14px; }
.bar-row { display: flex; align-items: center; gap: 10px; }
.bar-label { width: 80px; font-size: 13px; color: var(--text-secondary); flex-shrink: 0; text-align: right; }
.bar-track { flex: 1; height: 22px; background: var(--card-bg); border-radius: 11px; overflow: hidden; position: relative; }
.bar-fill { height: 100%; border-radius: 11px; transition: width 0.6s ease; min-width: 4px; }
.bar-value { width: 50px; font-size: 13px; font-weight: 600; color: var(--text-primary); font-variant-numeric: tabular-nums; }

/* 日志 */
.target-id { font-size: 11px; color: var(--text-tertiary); margin-left: 4px; }
.log-expand { padding: 16px 24px; background: var(--bg-main); border-radius: 8px; margin: 8px 0; }
.expand-title { font-weight: 600; color: var(--text-primary); margin-bottom: 12px; font-size: 14px; }
.chain-node { background: var(--card-bg); padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border-color); }
.chain-title { font-weight: 600; font-size: 13px; color: var(--text-primary); }
.chain-desc { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.log-pagination { margin-top: 16px; justify-content: flex-end; }
</style>
