<template>
  <div class="conversion-studio">
    <h2 class="page-title">客户转化</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <!-- ════════════════════════════════════════════════════════════ Tab 1: 线索管理 ═══════ -->
      <el-tab-pane label="线索管理" name="leads">
        <div class="tab-content">
          <!-- 筛选栏 -->
          <div class="filter-bar">
            <el-select v-model="leadFilters.grade" placeholder="等级" clearable style="width:120px">
              <el-option label="全部" value="" />
              <el-option label="A - 高价值" value="A" />
              <el-option label="B - 潜力" value="B" />
              <el-option label="C - 一般" value="C" />
              <el-option label="D - 低价值" value="D" />
            </el-select>
            <el-select v-model="leadFilters.platform" placeholder="平台" clearable style="width:120px">
              <el-option label="全部" value="" />
              <el-option label="抖音" value="douyin" />
              <el-option label="小红书" value="xhs" />
              <el-option label="B站" value="bilibili" />
              <el-option label="快手" value="kuaishou" />
              <el-option label="微信" value="wechat" />
            </el-select>
            <el-date-picker v-model="leadFilters.dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" style="width:240px" />
            <el-input v-model="leadFilters.search" placeholder="搜索客户昵称..." clearable style="width:200px">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" @click="refreshLeads"><el-icon><Refresh /></el-icon>刷新</el-button>
          </div>

          <!-- Kanban 漏斗 -->
          <div class="kanban-board">
            <div v-for="col in kanbanColumns" :key="col.status" class="kanban-column" :style="{ borderTop: `3px solid ${col.color}` }">
              <div class="kanban-header">
                <span class="kanban-title">{{ col.label }}</span>
                <el-tag size="small" effect="plain">{{ filteredLeadsByStatus(col.status).length }}</el-tag>
              </div>
              <div class="kanban-cards">
                <div v-for="lead in filteredLeadsByStatus(col.status)" :key="lead.id" class="lead-card">
                  <div class="lead-top">
                    <span class="lead-name">{{ lead.name }}</span>
                    <el-tag size="small" :type="platformType(lead.platform)" effect="plain">{{ platformLabel(lead.platform) }}</el-tag>
                  </div>
                  <div class="lead-grade-row">
                    <el-tag :type="gradeType(lead.grade)" size="small" effect="dark">{{ lead.grade }}</el-tag>
                    <span class="lead-grade-label">{{ gradeLabel(lead.grade) }}</span>
                  </div>
                  <p class="lead-note">{{ lead.note }}</p>
                  <div class="lead-meta">
                    <span><el-icon><ChatLineRound /></el-icon> {{ lead.followCount }} 次</span>
                    <span class="lead-time">{{ lead.lastContact }}</span>
                  </div>
                  <div class="lead-actions">
                    <el-button size="small" type="primary" plain @click="followLead(lead)">跟进</el-button>
                    <el-button size="small" type="warning" plain @click="transferLead(lead)">转移</el-button>
                    <el-button size="small" type="danger" plain @click="closeLead(lead)">关闭</el-button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════════════════════ Tab 2: 客户跟进 ═══════ -->
      <el-tab-pane label="客户跟进" name="follow">
        <div class="tab-content">
          <el-row :gutter="20" class="follow-layout">
            <!-- 左侧客户列表 -->
            <el-col :span="8" class="follow-left">
              <el-card shadow="never" class="customer-panel">
                <template #header>
                  <div class="panel-header">客户列表 <el-tag size="small" type="info">{{ filteredCustomers.length }}</el-tag></div>
                </template>
                <el-input v-model="customerSearch" placeholder="搜索客户..." clearable style="margin-bottom:12px">
                  <template #prefix><el-icon><Search /></el-icon></template>
                </el-input>
                <div class="customer-list">
                  <div v-for="c in filteredCustomers" :key="c.id" :class="['customer-item', { active: selectedCustomer?.id === c.id }]" @click="selectCustomer(c)">
                    <el-avatar :size="40">{{ c.name[0] }}</el-avatar>
                    <div class="customer-info">
                      <div class="customer-name-row">
                        <span class="customer-name">{{ c.name }}</span>
                        <el-badge v-if="c.unread > 0" :value="c.unread" class="unread-badge" />
                      </div>
                      <div class="customer-summary">{{ c.lastMessage }}</div>
                      <div class="customer-meta">
                        <el-tag size="small" effect="plain" :type="platformType(c.platform)">{{ platformLabel(c.platform) }}</el-tag>
                        <span class="customer-time">{{ c.lastTime }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </el-card>
            </el-col>

            <!-- 右侧聊天面板 -->
            <el-col :span="16" class="follow-right">
              <el-card shadow="never" class="chat-panel" v-if="selectedCustomer">
                <template #header>
                  <div class="chat-header">
                    <div class="chat-customer">
                      <el-avatar :size="32">{{ selectedCustomer.name[0] }}</el-avatar>
                      <span class="chat-name">{{ selectedCustomer.name }}</span>
                      <el-tag size="small" effect="plain" :type="platformType(selectedCustomer.platform)">{{ platformLabel(selectedCustomer.platform) }}</el-tag>
                    </div>
                    <el-button size="small" type="primary" plain @click="showAiSuggestions = true"><el-icon><MagicStick /></el-icon>AI 回复建议</el-button>
                  </div>
                </template>
                <div class="chat-messages" ref="msgBox">
                  <div v-for="(msg, i) in currentMessages" :key="i" :class="['msg-bubble', msg.sender]">
                    <div class="msg-content">{{ msg.text }}</div>
                    <div class="msg-time">{{ msg.time }}</div>
                  </div>
                </div>
                <div class="chat-input-area">
                  <el-input v-model="chatInput" type="textarea" :rows="3" placeholder="输入回复..." resize="none" @keydown.enter.exact.prevent="sendMessage" />
                  <div class="chat-toolbar">
                    <el-button size="small" type="primary" plain @click="showAiSuggestions = true"><el-icon><MagicStick /></el-icon>AI 建议</el-button>
                    <el-button type="primary" @click="sendMessage" :disabled="!chatInput.trim()"><el-icon><Promotion /></el-icon>发送</el-button>
                  </div>
                </div>
              </el-card>
              <el-empty v-else description="请选择左侧客户开始对话" />
            </el-col>
          </el-row>

          <!-- AI 回复建议弹窗 -->
          <el-dialog v-model="showAiSuggestions" title="AI 回复建议" width="500px" destroy-on-close>
            <div class="ai-suggestions">
              <div v-for="(s, i) in aiSuggestions" :key="i" class="suggestion-item" @click="applySuggestion(s)">
                <div class="suggestion-index">{{ i + 1 }}</div>
                <div class="suggestion-text">{{ s }}</div>
              </div>
            </div>
          </el-dialog>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════════════════════ Tab 3: SOP 引擎 ═══════ -->
      <el-tab-pane label="SOP 引擎" name="sop">
        <div class="tab-content">
          <!-- SOP 列表 -->
          <el-card shadow="never" class="sop-section">
            <template #header>
              <div class="section-header">
                <span>SOP 列表</span>
                <el-button type="primary" size="small" @click="createSop"><el-icon><Plus /></el-icon>新建 SOP</el-button>
              </div>
            </template>
            <el-table :data="sopList" stripe>
              <el-table-column prop="name" label="SOP 名称" min-width="160" />
              <el-table-column prop="scene" label="适用场景" width="120" />
              <el-table-column prop="steps.length" label="步骤数" width="80" />
              <el-table-column label="状态" width="100">
                <template #default="{row}">
                  <el-switch v-model="row.enabled" active-text="启用" inactive-text="禁用" inline-prompt />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="240">
                <template #default="{row}">
                  <el-button size="small" @click="editSop(row)">编辑</el-button>
                  <el-button size="small" type="danger" plain @click="deleteSop(row)">删除</el-button>
                  <el-button size="small" type="primary" plain @click="trackSop(row)">执行追踪</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- SOP 编辑器 Drawer -->
          <el-drawer v-model="sopDrawerVisible" title="SOP 编辑器" size="600px" destroy-on-close>
            <div class="sop-editor" v-if="editingSop">
              <el-form :model="editingSop" label-width="80px">
                <el-form-item label="名称">
                  <el-input v-model="editingSop.name" />
                </el-form-item>
                <el-form-item label="场景">
                  <el-input v-model="editingSop.scene" />
                </el-form-item>
              </el-form>
              <div class="step-editor">
                <div class="step-editor-title">步骤配置（可拖拽排序）</div>
                <div class="step-list">
                  <div v-for="(step, idx) in editingSop.steps" :key="step.id" class="step-item" draggable="true" @dragstart="dragStart(idx)" @dragover.prevent @drop="drop(idx)">
                    <div class="step-drag">⋮⋮</div>
                    <div class="step-body">
                      <el-input v-model="step.name" placeholder="步骤名称" size="small" style="width:160px" />
                      <el-select v-model="step.action" placeholder="动作" size="small" style="width:130px">
                        <el-option label="发送消息" value="send" />
                        <el-option label="等待回复" value="wait" />
                        <el-option label="条件判断" value="condition" />
                        <el-option label="标记线索" value="tag" />
                      </el-select>
                      <el-input v-model="step.param" placeholder="参数" size="small" style="width:140px" />
                    </div>
                    <el-button size="small" type="danger" text @click="removeStep(idx)"><el-icon><Delete /></el-icon></el-button>
                  </div>
                </div>
                <el-button type="primary" plain @click="addStep" style="margin-top:12px"><el-icon><Plus /></el-icon>添加步骤</el-button>
              </div>
              <div class="drawer-footer">
                <el-button @click="sopDrawerVisible = false">取消</el-button>
                <el-button type="primary" @click="saveSop">保存</el-button>
              </div>
            </div>
          </el-drawer>

          <!-- 执行追踪 -->
          <el-card shadow="never" class="sop-section">
            <template #header>
              <div class="section-header"><span>执行追踪</span></div>
            </template>
            <el-table :data="sopExecutions" stripe>
              <el-table-column prop="sopName" label="SOP 名称" min-width="140" />
              <el-table-column prop="customer" label="客户" width="120" />
              <el-table-column prop="currentStep" label="当前步骤" width="140" />
              <el-table-column label="状态" width="100">
                <template #default="{row}">
                  <el-tag :type="executionType(row.status)" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="startTime" label="开始时间" width="160" />
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════════════════════ Tab 4: 知识库 ═══════ -->
      <el-tab-pane label="知识库" name="knowledge">
        <div class="tab-content">
          <el-row :gutter="20" class="knowledge-layout">
            <!-- 左侧文档管理 -->
            <el-col :span="8">
              <el-card shadow="never" class="doc-panel">
                <template #header>
                  <div class="panel-header">文档管理</div>
                </template>
                <div class="upload-zone" @click="handleUploadClick">
                  <el-icon :size="32"><Upload /></el-icon>
                  <p>拖拽文件到此处上传</p>
                  <p class="upload-hint">或点击选择文件</p>
                </div>
                <el-table :data="docList" size="small" class="doc-table">
                  <el-table-column prop="name" label="文件名" min-width="120" show-overflow-tooltip />
                  <el-table-column prop="type" label="类型" width="70" />
                  <el-table-column label="状态" width="80">
                    <template #default="{row}">
                      <el-tag :type="row.status === 'indexed' ? 'success' : 'warning'" size="small">{{ row.status === 'indexed' ? '已索引' : '待索引' }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="100">
                    <template #default="{row}">
                      <el-button size="small" text @click="reindexDoc(row)">重新索引</el-button>
                      <el-button size="small" text type="danger" @click="deleteDoc(row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-card>
            </el-col>

            <!-- 右侧 RAG 问答 -->
            <el-col :span="16">
              <el-card shadow="never" class="rag-panel">
                <template #header>
                  <div class="rag-header">
                    <span>RAG 语义检索</span>
                  </div>
                </template>
                <div class="rag-search">
                  <el-input v-model="ragQuery" placeholder="输入问题，检索知识库..." clearable>
                    <template #append>
                      <el-button type="primary" @click="performRagSearch"><el-icon><Search /></el-icon>检索</el-button>
                    </template>
                  </el-input>
                </div>
                <div v-if="ragResults.length > 0" class="rag-results">
                  <div class="result-section-title">相关片段</div>
                  <div v-for="(r, i) in ragResults" :key="i" class="rag-result-item">
                    <div class="result-score">相似度 {{ r.score }}%</div>
                    <div class="result-text">{{ r.text }}</div>
                    <div class="result-source">来源：{{ r.source }}</div>
                  </div>
                  <div class="result-section-title" style="margin-top:16px">AI 综合回答</div>
                  <div class="rag-answer">{{ ragAnswer }}</div>
                </div>
                <el-empty v-else description="输入问题并点击检索，获取知识库回答" />
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

// ==================== 通用 ====================
const activeTab = ref('leads')

const platformLabel = (p) => ({ douyin: '抖音', xhs: '小红书', bilibili: 'B站', kuaishou: '快手', wechat: '微信' }[p] || p)
const platformType = (p) => ({ douyin: 'danger', xhs: 'warning', bilibili: 'primary', kuaishou: 'success', wechat: 'success' }[p] || 'info')
const gradeType = (g) => ({ A: 'danger', B: 'warning', C: 'info', D: '' }[g] || 'info')
const gradeLabel = (g) => ({ A: 'HOT', B: '潜力', C: '一般', D: '低价值' }[g] || g)

// ==================== Tab 1: 线索管理 ====================
const leadFilters = ref({ grade: '', platform: '', dateRange: null, search: '' })
const kanbanColumns = [
  { status: 'new', label: '新线索', color: '#4f46e5' },
  { status: 'pending', label: '待跟进', color: '#409eff' },
  { status: 'contacting', label: '沟通中', color: '#67c23a' },
  { status: 'blocked', label: '受阻', color: '#e6a23c' },
  { status: 'won', label: '已成交', color: '#14b8a6' },
  { status: 'lost', label: '已流失', color: '#909399' },
]

const leads = ref([])
const customers = ref([])
const messagesMap = ref({})
const sops = ref([])
const sopExecutions = ref([])
const docList = ref([])

async function loadConversionData() {
  try {
    const [{ data: leadsData }, { data: customersData }, { data: messagesData }, { data: sopsData }, { data: executionsData }, { data: docsData }] = await Promise.all([
      axios.get('/api/acquisition/leads'),
      axios.get('/api/acquisition/customers'),
      axios.get('/api/acquisition/messages'),
      axios.get('/api/sop/list'),
      axios.get('/api/sop/executions'),
      axios.get('/api/knowledge/documents'),
    ])
    leads.value = leadsData.leads || []
    customers.value = customersData.customers || []
    const msgs = messagesData.messages || []
    const map = {}
    msgs.forEach(m => {
      const cid = m.customer_id
      if (!map[cid]) map[cid] = []
      map[cid].push(m)
    })
    messagesMap.value = map
    sops.value = sopsData.sops || []
    sopExecutions.value = executionsData.executions || []
    docList.value = docsData.items || []
  } catch (e) {
    ElMessage.error('加载转化数据失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadConversionData()
})

const filteredLeadsByStatus = (status) => {
  return leads.value.filter(l => {
    if (l.status !== status) return false
    if (leadFilters.value.grade && l.grade !== leadFilters.value.grade) return false
    if (leadFilters.value.platform && l.platform !== leadFilters.value.platform) return false
    if (leadFilters.value.search && !l.name.includes(leadFilters.value.search)) return false
    return true
  })
}

async function refreshLeads() {
  await loadConversionData()
  ElMessage.success('线索数据已刷新')
}
async function followLead(lead) {
  try {
    await axios.post(`/api/acquisition/leads/${lead.id}/follow`)
    lead.followCount = (lead.followCount || 0) + 1
    lead.lastContact = new Date().toLocaleString('zh-CN', { hour12: false })
    ElMessage.success(`已开始跟进 ${lead.name}`)
  } catch (e) {
    ElMessage.error('跟进失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function transferLead(lead) {
  try {
    const { value } = await ElMessageBox.prompt('选择目标阶段', '转移线索', { confirmButtonText: '确定', cancelButtonText: '取消' })
    await axios.put(`/api/acquisition/leads/${lead.id}`, { status: value })
    lead.status = value
    ElMessage.success(`已将 ${lead.name} 转移到 ${value}`)
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('转移失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}
async function closeLead(lead) {
  try {
    await ElMessageBox.confirm(`确定关闭线索 ${lead.name} 吗？`, '确认关闭')
    await axios.put(`/api/acquisition/leads/${lead.id}`, { status: 'lost' })
    lead.status = 'lost'
    ElMessage.success('已关闭')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('关闭失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

// ==================== Tab 2: 客户跟进 ====================
const customerSearch = ref('')
const selectedCustomer = ref(null)
const chatInput = ref('')
const showAiSuggestions = ref(false)
const msgBox = ref(null)

const filteredCustomers = computed(() => {
  if (!customerSearch.value) return customers.value
  return customers.value.filter(c => c.name.includes(customerSearch.value) || c.lastMessage.includes(customerSearch.value))
})

const currentMessages = computed(() => selectedCustomer.value ? (messagesMap.value[selectedCustomer.value.id] || []) : [])

const selectCustomer = (c) => {
  selectedCustomer.value = c
  c.unread = 0
  nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight })
}

const sendMessage = async () => {
  if (!chatInput.value.trim() || !selectedCustomer.value) return
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  const msg = { sender: 'assistant', text: chatInput.value, time }
  try {
    await axios.post(`/api/acquisition/messages/${selectedCustomer.value.id}`, msg)
    const list = messagesMap.value[selectedCustomer.value.id] || []
    list.push(msg)
    messagesMap.value[selectedCustomer.value.id] = list
    chatInput.value = ''
    nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight })
  } catch (e) {
    ElMessage.error('发送失败: ' + (e.response?.data?.detail || e.message))
  }
}

const aiSuggestions = ref([
  '您好！目前我们正在进行夏日促销活动，全场满300减50，您看需要我给您推荐几款适合的产品吗？',
  '完全理解您的顾虑，我们可以为您提供小样试用，满意后再购买，您看可以吗？',
  '感谢您的关注！我们支持7天无理由退换，您可以放心下单体验。',
])

const applySuggestion = (text) => {
  chatInput.value = text
  showAiSuggestions.value = false
}

// ==================== Tab 3: SOP 引擎 ====================
const sopDrawerVisible = ref(false)
const editingSop = ref(null)
let dragIdx = null

const executionType = (s) => ({ '进行中': 'primary', '已完成': 'success', '待执行': 'info', '失败': 'danger' }[s] || 'info')

const createSop = () => {
  editingSop.value = { id: Date.now(), name: '新 SOP', scene: '', steps: [], enabled: true }
  sopDrawerVisible.value = true
}

const editSop = (row) => {
  editingSop.value = JSON.parse(JSON.stringify(row))
  sopDrawerVisible.value = true
}

async function deleteSop(row) {
  try {
    await ElMessageBox.confirm('确定删除此 SOP 吗？', '确认')
    await axios.delete(`/api/sop/${row.id}`)
    sops.value = sops.value.filter(s => s.id !== row.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}
const trackSop = (row) => ElMessage.info(`正在追踪 ${row.name} 的执行情况...`)

const addStep = () => {
  editingSop.value.steps.push({ id: 's' + Date.now(), name: '', action: 'send', param: '' })
}
const removeStep = (idx) => { editingSop.value.steps.splice(idx, 1) }
const dragStart = (idx) => { dragIdx = idx }
const drop = (idx) => {
  if (dragIdx === null || dragIdx === idx) return
  const item = editingSop.value.steps.splice(dragIdx, 1)[0]
  editingSop.value.steps.splice(idx, 0, item)
  dragIdx = null
}

async function saveSop() {
  if (!editingSop.value.name) return ElMessage.warning('请填写 SOP 名称')
  try {
    const idx = sops.value.findIndex(s => s.id === editingSop.value.id)
    if (idx >= 0) {
      await axios.put(`/api/sop/${editingSop.value.id}`, editingSop.value)
      sops.value[idx] = JSON.parse(JSON.stringify(editingSop.value))
    } else {
      const { data } = await axios.post('/api/sop/define', {
        name: editingSop.value.name,
        description: editingSop.value.description || '',
        steps: editingSop.value.steps || [],
      })
      sops.value.push(data)
    }
    sopDrawerVisible.value = false
    ElMessage.success('SOP 已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ==================== Tab 4: 知识库 ====================
const ragQuery = ref('')
const ragResults = ref([])
const ragAnswer = ref('')

async function performRagSearch() {
  if (!ragQuery.value.trim()) return
  try {
    const { data } = await axios.get('/api/knowledge/search', { params: { q: ragQuery.value } })
    ragResults.value = data.results || []
    ragAnswer.value = data.answer || '已找到相关答案'
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message))
  }
}

const handleUploadClick = () => ElMessage.info('请选择文件并上传')
async function reindexDoc(row) {
  try {
    await axios.post('/api/knowledge/ingest', { text: row.name, source: row.name })
    row.status = 'indexed'
    ElMessage.success(`${row.name} 已重新索引`)
  } catch (e) {
    ElMessage.error('索引失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function deleteDoc(row) {
  try {
    await ElMessageBox.confirm('确定删除该文档吗？')
    await axios.delete(`/api/knowledge/documents/${row.id}`)
    docList.value = docList.value.filter(d => d.id !== row.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}
</script>

<style scoped>
.conversion-studio { padding: 24px; }
.page-title { margin: 0 0 20px; font-size: 18px; color: var(--text-primary); font-weight: 600; }
.studio-tabs :deep(.el-tabs__content) { padding: 16px; background: var(--card-bg); border: 1px solid var(--border-color); border-top: none; border-radius: 0 0 8px 8px; }
.tab-content { min-height: 500px; }

/* 筛选栏 */
.filter-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 20px; }

/* Kanban */
.kanban-board { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; overflow-x: auto; }
@media (max-width: 1279px) { .kanban-board { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 767px) { .kanban-board { grid-template-columns: 1fr; } }

.kanban-column { background: var(--bg-main); border-radius: 8px; padding: 12px; min-height: 400px; }
.kanban-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-weight: 600; color: var(--text-primary); }
.kanban-cards { display: flex; flex-direction: column; gap: 10px; }
.lead-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; cursor: pointer; transition: box-shadow 0.2s, transform 0.2s; }
.lead-card:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
.lead-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.lead-name { font-weight: 600; color: var(--text-primary); font-size: 14px; }
.lead-grade-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.lead-grade-label { font-size: 11px; color: var(--text-tertiary); }
.lead-note { font-size: 12px; color: var(--text-secondary); margin: 0 0 8px; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.lead-meta { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-tertiary); margin-bottom: 8px; }
.lead-meta span { display: flex; align-items: center; gap: 4px; }
.lead-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.lead-actions .el-button { padding: 4px 8px; font-size: 12px; }

/* 客户跟进 */
.follow-layout { height: calc(100vh - 220px); min-height: 500px; }
.follow-left, .follow-right { height: 100%; }
.customer-panel, .chat-panel { height: 100%; display: flex; flex-direction: column; }
.panel-header { font-weight: 600; display: flex; align-items: center; gap: 8px; }
.customer-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.customer-item { display: flex; gap: 10px; padding: 10px; border-radius: 8px; cursor: pointer; transition: background 0.2s; align-items: center; }
.customer-item:hover, .customer-item.active { background: var(--hover-bg); }
.customer-info { flex: 1; min-width: 0; }
.customer-name-row { display: flex; justify-content: space-between; align-items: center; }
.customer-name { font-weight: 600; font-size: 14px; color: var(--text-primary); }
.customer-summary { font-size: 12px; color: var(--text-secondary); margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.customer-meta { display: flex; align-items: center; gap: 8px; margin-top: 4px; font-size: 11px; color: var(--text-tertiary); }
.customer-time { margin-left: auto; }

.chat-header { display: flex; justify-content: space-between; align-items: center; }
.chat-customer { display: flex; align-items: center; gap: 8px; }
.chat-name { font-weight: 600; color: var(--text-primary); }
.chat-messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; min-height: 200px; background: var(--bg-main); border-radius: 8px; margin-bottom: 12px; }
.msg-bubble { max-width: 70%; padding: 10px 14px; border-radius: 12px; font-size: 13px; line-height: 1.5; }
.msg-bubble.user { align-self: flex-end; background: var(--accent-primary); color: var(--text-inverse); border-bottom-right-radius: 4px; }
.msg-bubble.assistant { align-self: flex-start; background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-primary); border-bottom-left-radius: 4px; }
.msg-time { font-size: 10px; opacity: 0.7; margin-top: 4px; text-align: right; }
.chat-input-area { display: flex; flex-direction: column; gap: 8px; }
.chat-toolbar { display: flex; justify-content: space-between; align-items: center; }

.ai-suggestions { display: flex; flex-direction: column; gap: 12px; }
.suggestion-item { display: flex; gap: 12px; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer; transition: background 0.2s; background: var(--card-bg); }
.suggestion-item:hover { background: var(--hover-bg); }
.suggestion-index { width: 28px; height: 28px; border-radius: 50%; background: var(--accent-primary); color: var(--text-inverse); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; flex-shrink: 0; }
.suggestion-text { font-size: 13px; color: var(--text-primary); line-height: 1.5; }

/* SOP */
.sop-section { margin-bottom: 20px; }
.section-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.step-editor { margin-top: 20px; }
.step-editor-title { font-weight: 600; margin-bottom: 12px; color: var(--text-primary); }
.step-list { display: flex; flex-direction: column; gap: 8px; }
.step-item { display: flex; align-items: center; gap: 8px; padding: 10px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--card-bg); cursor: move; }
.step-drag { color: var(--text-muted); font-size: 12px; cursor: grab; user-select: none; }
.step-body { flex: 1; display: flex; gap: 8px; flex-wrap: wrap; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border-color); }

/* 知识库 */
.knowledge-layout { min-height: 500px; }
.doc-panel { height: 100%; }
.upload-zone { border: 2px dashed var(--border-color); border-radius: 12px; padding: 32px; text-align: center; cursor: pointer; transition: background 0.2s, border-color 0.2s; color: var(--text-secondary); margin-bottom: 16px; }
.upload-zone:hover { background: var(--hover-bg); border-color: var(--accent-primary); }
.upload-hint { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; }
.doc-table { margin-top: 8px; }
.rag-panel { height: 100%; }
.rag-header { font-weight: 600; }
.rag-search { margin-bottom: 16px; }
.rag-results { max-height: 600px; overflow-y: auto; }
.result-section-title { font-weight: 600; color: var(--text-primary); margin-bottom: 8px; font-size: 14px; }
.rag-result-item { padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 10px; background: var(--bg-main); }
.result-score { font-size: 11px; color: var(--accent-primary); font-weight: 600; margin-bottom: 4px; }
.result-text { font-size: 13px; color: var(--text-primary); line-height: 1.5; }
.result-source { font-size: 11px; color: var(--text-tertiary); margin-top: 6px; }
.rag-answer { padding: 16px; background: var(--bg-main); border-radius: 8px; border-left: 3px solid var(--accent-primary); font-size: 14px; line-height: 1.7; color: var(--text-primary); white-space: pre-wrap; }
</style>
