<template>
    <div class="publisher">
      <div class="pub-header">
        <h2>📝 内容发布管道</h2>
        <div class="header-actions">
          <el-button type="primary" @click="showCreate = true"><el-icon><Plus /></el-icon>新建内容</el-button>
          <el-button @click="showCalendar = !showCalendar"><el-icon><Calendar /></el-icon>{{ showCalendar ? '列表' : '日历' }}</el-button>
        </div>
      </div>

      <!-- Stats -->
      <el-row :gutter="16" class="stats-mini">
        <el-col :span="4" v-for="s in statCards" :key="s.label">
          <div :class="['stat-chip', s.color]">
            <span class="chip-num">{{ s.value }}</span><span class="chip-label">{{ s.label }}</span>
          </div>
        </el-col>
      </el-row>

      <!-- Content List -->
      <el-card v-if="!showCalendar">
        <el-tabs v-model="filterStatus" @tab-change="loadContents">
          <el-tab-pane label="全部" name="" />
          <el-tab-pane label="草稿" name="draft" />
          <el-tab-pane label="待审核" name="pending" />
          <el-tab-pane label="已批准" name="approved" />
          <el-tab-pane label="已发布" name="published" />
        </el-tabs>

        <el-table :data="contents" stripe v-loading="loading">
          <el-table-column prop="title" label="标题" min-width="200">
            <template #default="{row}">
              <span @click="openContent(row)" class="content-link">{{ row.title }}</span>
              <el-tag v-if="row.ai_generated" size="small" type="info" effect="plain">AI</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{row}">{{ typeLabels[row.content_type] || row.content_type }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{row}">
              <el-tag :type="statusType(row.status)" size="small">{{ statusLabels[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="定时发布" width="170">
            <template #default="{row}">{{ row.scheduled_at?.slice(0,16) || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{row}">
              <el-button v-if="row.status==='draft'" size="small" type="warning" @click="submitReview(row.id)">提交审核</el-button>
              <el-button v-if="row.status==='pending'" size="small" type="success" @click="approveContent(row.id)">通过</el-button>
              <el-button v-if="row.status==='approved'" size="small" type="primary" @click="publishNow(row.id)">立即发布</el-button>
              <el-button size="small" @click="openContent(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Calendar View -->
      <el-card v-if="showCalendar">
        <div class="calendar-placeholder">
          📅 内容日历视图 — {{ currentMonth }}
          <div v-for="e in calendarEvents" :key="e.id" class="cal-event">
            <el-tag size="small">{{ e.scheduled_at?.slice(0,16) }}</el-tag> {{ e.title }}
          </div>
          <div v-if="!calendarEvents.length" style="color:#909399;margin-top:20px;">暂无定时发布内容</div>
        </div>
      </el-card>

      <!-- Create/Edit Dialog -->
      <el-dialog v-model="showCreate" :title="editingId ? '编辑内容' : '新建内容'" width="750px" top="5vh">
        <el-form :model="form" label-width="80px">
          <el-form-item label="标题"><el-input v-model="form.title" placeholder="内容标题" /></el-form-item>
          <el-form-item label="类型">
            <el-select v-model="form.content_type">
              <el-option v-for="(v,k) in typeLabels" :key="k" :label="v" :value="k" />
            </el-select>
          </el-form-item>
          <el-form-item label="正文">
            <el-input v-model="form.body" type="textarea" :rows="10" placeholder="Markdown格式正文" />
          </el-form-item>
          <el-form-item label="平台">
            <div class="platform-checkboxes">
              <el-checkbox-group v-model="form.platforms">
                <el-checkbox v-for="p in platforms" :key="p.value" :value="p.value" :label="p.label" />
              </el-checkbox-group>
              <div class="platform-status-hints">
                <span v-for="p in platforms" :key="'hint-'+p.value" class="status-hint">
                  <el-tag v-if="p.value !== 'all' && platformReady(p.value)" size="small" type="success" effect="plain">✓</el-tag>
                  <el-tag v-else-if="p.value !== 'all'" size="small" type="info" effect="plain">?</el-tag>
                </span>
              </div>
            </div>
          </el-form-item>
          <el-form-item label="标签"><el-input v-model="form.tags" placeholder="逗号分隔" /></el-form-item>
          <el-form-item label="定时发布">
            <el-date-picker v-model="form.scheduled_at" type="datetime" placeholder="选择时间（可选）" />
          </el-form-item>
          <el-form-item>
            <el-button @click="aiGenerate">🤖 AI生成草稿</el-button>
            <el-button type="primary" @click="saveContent">保存</el-button>
          </el-form-item>
        </el-form>
      </el-dialog>

      <!-- AI Generate Dialog -->
      <el-dialog v-model="showAiGen" title="AI生成内容" width="500px">
        <el-form>
          <el-form-item label="主题"><el-input v-model="aiTopic" placeholder="输入主题" /></el-form-item>
          <el-form-item label="Agent">
            <el-select v-model="aiAgent">
              <el-option label="营销文案师" value="copywriter" />
              <el-option label="视频脚本生成器" value="video-script-writer" />
              <el-option label="通用助手" value="general-assistant" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="aiLoading" @click="doAiGenerate">生成</el-button>
          </el-form-item>
        </el-form>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const contents = ref([])
const loading = ref(false)
const showCreate = ref(false)
const showCalendar = ref(false)
const showAiGen = ref(false)
const editingId = ref('')
const filterStatus = ref('')
const currentMonth = ref(new Date().toISOString().slice(0,7))
const calendarEvents = ref([])
const aiTopic = ref('')
const aiAgent = ref('copywriter')
const aiLoading = ref(false)

const form = reactive({ title: '', body: '', content_type: 'post', platforms: ['all'], tags: '', scheduled_at: '' })
const platforms = [
  { value: 'all', label: '全平台' }, { value: 'wechat_mp', label: '公众号' },
  { value: 'wecom', label: '企微' }, { value: 'douyin', label: '抖音' },
  { value: 'xhs', label: '小红书' }, { value: 'kuaishou', label: '快手' },
  { value: 'bilibili', label: 'B站' }, { value: 'weibo', label: '微博' },
]
const typeLabels = { post: '短帖', article: '长文', video: '视频脚本', image: '图文' }
const statusLabels = { draft: '草稿', pending: '待审核', approved: '已批准', published: '已发布', rejected: '已拒绝' }
const statusType = (s) => ({ draft:'info',pending:'warning',approved:'success',published:'',rejected:'danger' }[s]||'')
const statCards = ref([
  { label: '总计', value: 0, color: 'gray' }, { label: '草稿', value: 0, color: 'blue' },
  { label: '待审', value: 0, color: 'orange' }, { label: '批准', value: 0, color: 'green' },
  { label: '已发布', value: 0, color: 'purple' }, { label: '已拒绝', value: 0, color: 'red' },
])

const platformLogins = ref({})  // { douyin: true, xhs: false, ... }

function platformReady(pid) {
  return platformLogins.value[pid] || false
}

async function loadPlatformStatus() {
  try {
    const { data } = await axios.get('/api/platforms')
    const logins = {}
    for (const p of (data.platforms || [])) {
      logins[p.id] = p.login?.is_logged_in || false
    }
    platformLogins.value = logins
  } catch (_) {}
}

onMounted(() => { loadContents(); loadStats(); loadPlatformStatus() })

async function loadContents() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/publisher/contents', { params: { status: filterStatus.value, limit: 50 } })
    contents.value = data
  } catch (_) {}
  loading.value = false
}

async function loadStats() {
  try {
    const { data } = await axios.get('/api/publisher/stats')
    statCards.value[0].value = data.total || 0
    statCards.value[1].value = data.drafts || 0
    statCards.value[2].value = data.pending_review || 0
    statCards.value[3].value = data.approved || 0
    statCards.value[4].value = data.published || 0
    statCards.value[5].value = data.by_status?.rejected || 0
  } catch (_) {}
  try {
    const { data } = await axios.get('/api/publisher/calendar', { params: { month: currentMonth.value } })
    calendarEvents.value = data
  } catch (_) {}
}

async function saveContent() {
  if (!form.title) return ElMessage.warning('请填写标题')
  try {
    if (editingId.value) {
      await axios.put(`/api/publisher/contents/${editingId.value}`, null, { params: form })
    } else {
      await axios.post('/api/publisher/contents', null, { params: form })
    }
    showCreate.value = false
    ElMessage.success('保存成功')
    loadContents(); loadStats()
  } catch (e) { ElMessage.error('保存失败') }
}

function openContent(row) {
  Object.assign(form, {
    title: row.title, body: row.body, content_type: row.content_type,
    platforms: row.platforms||['all'], tags: (row.tags||[]).join(','),
    scheduled_at: row.scheduled_at || ''
  })
  editingId.value = row.id
  showCreate.value = true
}

function submitReview(id) { axios.post(`/api/publisher/contents/${id}/submit`).then(() => { loadContents(); loadStats() }) }
function approveContent(id) { axios.post(`/api/publisher/contents/${id}/approve`).then(() => { loadContents(); loadStats() }) }
function publishNow(id) { axios.post(`/api/publisher/contents/${id}/publish`).then(() => { ElMessage.success('发布成功'); loadContents(); loadStats() }) }
function aiGenerate() { showAiGen.value = true }
async function doAiGenerate() {
  aiLoading.value = true
  try {
    const { data } = await axios.post('/api/publisher/ai-generate', null, { params: { topic: aiTopic.value, agent_id: aiAgent.value } })
    ElMessage.success(`AI已生成: ${data.title}`)
    showAiGen.value = false; loadContents(); loadStats()
  } catch (_) { ElMessage.error('生成失败') }
  aiLoading.value = false
}
</script>

<style scoped>
.publisher { max-width: 1400px; margin: 0 auto; }
.pub-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.pub-header h2 { margin: 0; }
.header-actions { display: flex; gap: 8px; }
.stats-mini { margin-bottom: 16px; }
.stat-chip { text-align: center; padding: 10px; border-radius: 8px; background: #f5f7fa; }
.stat-chip.blue .chip-num { color: #409eff; } .stat-chip.green .chip-num { color: #67c23a; }
.stat-chip.orange .chip-num { color: #e6a23c; } .stat-chip.purple .chip-num { color: #9b59b6; }
.stat-chip.red .chip-num { color: #f56c6c; } .stat-chip.gray .chip-num { color: #909399; }
.chip-num { font-size: 28px; font-weight: bold; display: block; }
.chip-label { font-size: 12px; color: #909399; }
.content-link { cursor: pointer; color: #409eff; }
.content-link:hover { text-decoration: underline; }
.calendar-placeholder { min-height: 300px; padding: 20px; }
.cal-event { padding: 8px 0; border-bottom: 1px solid #ebeef5; }
</style>
