<template>
    <div class="scheduler">
      <div class="sched-header">
        <h2>⚡ 智能调度引擎</h2>
        <el-button type="primary" @click="showCreate = true"><el-icon><Plus /></el-icon>新建任务</el-button>
      </div>

      <!-- Stats -->
      <el-row :gutter="16" class="stats-mini">
        <el-col :span="4" v-for="s in statCards" :key="s.label">
          <div :class="['stat-chip', s.color]"><span class="chip-num">{{ s.value }}</span><span class="chip-label">{{ s.label }}</span></div>
        </el-col>
      </el-row>

      <!-- Job List -->
      <el-card>
        <el-table :data="jobs" stripe v-loading="loading">
          <el-table-column prop="name" label="任务名称" min-width="180" />
          <el-table-column label="触发方式" width="100">
            <template #default="{row}">{{ triggerLabels[row.trigger_type] }}</template>
          </el-table-column>
          <el-table-column label="触发配置" width="160">
            <template #default="{row}">
              <el-tag v-if="row.trigger_config?.cron" size="small">cron: {{ row.trigger_config.cron }}</el-tag>
              <el-tag v-else-if="row.trigger_config?.minutes" size="small">每{{ row.trigger_config.minutes }}分钟</el-tag>
              <span v-else>手动</span>
            </template>
          </el-table-column>
          <el-table-column label="动作" width="130">
            <template #default="{row}">{{ actionLabels[row.action] }}</template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{row}">
              <el-tag :type="statusType(row.status)" size="small">{{ statusLabels[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="优先级" width="70">
            <template #default="{row}"><el-rate :model-value="row.priority" disabled show-score :max="10" size="small" /></template>
          </el-table-column>
          <el-table-column label="下次执行" width="170">
            <template #default="{row}">{{ row.next_run_at?.slice(0,16) || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{row}">
              <el-button size="small" type="primary" @click="runJob(row.id)">▶ 执行</el-button>
              <el-button v-if="row.status==='active'" size="small" type="warning" @click="pauseJob(row.id)">⏸</el-button>
              <el-button v-if="row.status==='paused'" size="small" type="success" @click="resumeJob(row.id)">▶</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Execution History -->
      <el-card style="margin-top:20px">
        <template #header><h3>📜 执行历史</h3></template>
        <el-timeline>
          <el-timeline-item v-for="h in history" :key="h.id"
            :timestamp="h.started_at?.slice(0,19)"
            :color="h.status==='success'?'#67c23a':h.status==='failed'?'#f56c6c':'#409eff'"
            placement="top">
            <strong>{{ h.job_name }}</strong>
            <el-tag :type="h.status==='success'?'success':'danger'" size="small" style="margin-left:8px">{{ h.status }}</el-tag>
            <div v-if="h.error" style="color:#f56c6c;font-size:12px;">{{ h.error }}</div>
            <div v-if="h.result" style="color:#67c23a;font-size:12px;">{{ h.result }}</div>
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <!-- Create Job Dialog -->
      <el-dialog v-model="showCreate" title="新建调度任务" width="600px">
        <el-form :model="form" label-width="100px">
          <el-form-item label="任务名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
          <el-form-item label="触发方式">
            <el-select v-model="form.trigger_type">
              <el-option v-for="(v,k) in triggerLabels" :key="k" :label="v" :value="k" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.trigger_type==='cron'" label="Cron表达式">
            <el-input v-model="form.cron" placeholder="0 9 * * *" />
            <div class="form-hint">分 时 日 月 星期 (如: 0 8 * * * = 每天8点)</div>
          </el-form-item>
          <el-form-item v-if="form.trigger_type==='interval'" label="间隔(分钟)">
            <el-input-number v-model="form.interval_minutes" :min="1" :max="1440" />
          </el-form-item>
          <el-form-item v-if="form.trigger_type==='once'" label="执行时间">
            <el-date-picker v-model="form.at_time" type="datetime" />
          </el-form-item>
          <el-form-item label="动作">
            <el-select v-model="form.action">
              <el-option v-for="(v,k) in actionLabels" :key="k" :label="v" :value="k" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-rate v-model="form.priority" :max="10" show-score />
          </el-form-item>
          <el-form-item label="标签"><el-input v-model="form.tags" placeholder="逗号分隔" /></el-form-item>
          <el-form-item>
            <el-button type="primary" @click="createJob">创建任务</el-button>
          </el-form-item>
        </el-form>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const jobs = ref([])
const history = ref([])
const loading = ref(false)
const showCreate = ref(false)

const form = reactive({ name: '', description: '', trigger_type: 'manual', cron: '', interval_minutes: 60, at_time: '', action: 'custom', priority: 5, tags: '' })
const triggerLabels = { cron: 'Cron定时', interval: '固定间隔', once: '一次性', manual: '手动', event: '事件触发' }
const actionLabels = {
  publish_content: '发布内容', generate_content: 'AI生成内容',
  run_workflow: '执行工作流', send_notification: '发送通知',
  execute_tool: '执行工具', custom: '自定义',
}
const statusLabels = { active:'运行中',paused:'已暂停',running:'执行中',completed:'已完成',failed:'失败',disabled:'已禁用' }
const statusType = (s) => ({ active:'success',paused:'warning',running:'',completed:'info',failed:'danger',disabled:'info' }[s]||'')
const statCards = ref([{label:'总任务',value:0,color:'gray'},{label:'运行中',value:0,color:'green'},{label:'已暂停',value:0,color:'orange'},{label:'已完成',value:0,color:'blue'},{label:'失败',value:0,color:'red'},{label:'今日执行',value:0,color:'purple'}])

onMounted(() => { loadData() })

async function loadData() {
  loading.value = true
  try {
    const [jRes, hRes, sRes] = await Promise.all([
      axios.get('/api/scheduler/jobs'),
      axios.get('/api/scheduler/history', { params: { limit: 20 } }),
      axios.get('/api/scheduler/stats'),
    ])
    jobs.value = jRes.data
    history.value = hRes.data
    const s = sRes.data
    statCards.value[0].value = s.total_jobs; statCards.value[1].value = s.active
    statCards.value[2].value = s.paused; statCards.value[3].value = s.completed
    statCards.value[4].value = s.failed; statCards.value[5].value = s.recent_executions
  } catch (_) {}
  loading.value = false
}

async function createJob() {
  if (!form.name) return ElMessage.warning('请填写任务名称')
  try {
    const params = {
      name: form.name, description: form.description,
      trigger_type: form.trigger_type, action: form.action,
      priority: form.priority, tags: form.tags,
    }
    if (form.cron) params.cron = form.cron
    if (form.interval_minutes) params.interval_minutes = form.interval_minutes
    if (form.at_time) params.at_time = form.at_time
    await axios.post('/api/scheduler/jobs', null, { params })
    showCreate.value = false
    ElMessage.success('任务已创建')
    loadData()
  } catch (e) { ElMessage.error('创建失败') }
}

function runJob(id) { axios.post(`/api/scheduler/jobs/${id}/execute`).then(() => { ElMessage.success('任务已执行'); loadData() }) }
function pauseJob(id) { axios.post(`/api/scheduler/jobs/${id}/pause`).then(() => { loadData() }) }
function resumeJob(id) { axios.post(`/api/scheduler/jobs/${id}/resume`).then(() => { loadData() }) }
</script>

<style scoped>
.scheduler { max-width: 1400px; margin: 0 auto; }
.sched-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.sched-header h2 { margin: 0; }
.stats-mini { margin-bottom: 16px; }
.stat-chip { text-align: center; padding: 10px; border-radius: 8px; background: #f5f7fa; }
.stat-chip.green .chip-num { color: #67c23a; } .stat-chip.orange .chip-num { color: #e6a23c; }
.stat-chip.blue .chip-num { color: #409eff; } .stat-chip.red .chip-num { color: #f56c6c; }
.stat-chip.purple .chip-num { color: #9b59b6; } .stat-chip.gray .chip-num { color: #909399; }
.chip-num { font-size: 28px; font-weight: bold; display: block; }
.chip-label { font-size: 12px; color: #909399; }
.form-hint { font-size: 11px; color: #909399; margin-top: 4px; }
</style>
