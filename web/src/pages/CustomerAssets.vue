<template>
  <div class="customer-assets-page">
    <!-- 顶部区域 -->
    <div class="page-header">
      <div class="title-section">
        <h1 class="page-title">客户资产</h1>
        <p class="page-subtitle">线索沉淀与转化追踪</p>
      </div>
      <div class="filter-section">
        <el-input
          v-model="searchQuery"
          placeholder="搜索昵称/备注"
          clearable
          class="search-input"
          :prefix-icon="Search"
        />
        <el-select
          v-model="filterGrades"
          multiple
          collapse-tags
          placeholder="等级"
          class="filter-item"
        >
          <el-option label="A级" value="A" />
          <el-option label="B级" value="B" />
          <el-option label="C级" value="C" />
          <el-option label="D级" value="D" />
        </el-select>
        <el-select v-model="filterSource" placeholder="来源平台" clearable class="filter-item">
          <el-option label="抖音" value="douyin" />
          <el-option label="小红书" value="xhs" />
          <el-option label="快手" value="kuaishou" />
          <el-option label="B站" value="bilibili" />
          <el-option label="微信" value="wechat" />
        </el-select>
        <el-date-picker
          v-model="filterDateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          class="filter-item"
          value-format="YYYY-MM-DD"
        />
        <el-select v-model="filterStatus" placeholder="状态" clearable class="filter-item">
          <el-option label="合格" value="qualified" />
          <el-option label="跟进中" value="contacting" />
          <el-option label="已成交" value="converted" />
          <el-option label="已流失" value="lost" />
        </el-select>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="border-card" class="content-tabs">
      <!-- 子标签 1 — 线索列表 -->
      <el-tab-pane label="线索列表" name="leads">
        <el-table
          :data="filteredLeads"
          stripe
          style="width: 100%"
          class="assets-table"
        >
          <el-table-column prop="name" label="昵称" min-width="100" show-overflow-tooltip />
          <el-table-column label="来源平台" min-width="100">
            <template #default="{ row }">
              {{ platformMap[row.platform] || row.platform }}
            </template>
          </el-table-column>
          <el-table-column label="意向等级" width="90">
            <template #default="{ row }">
              <el-tag :type="gradeType(row.grade)" size="small">
                {{ row.grade }}级
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="firstContact" label="首次接触" width="110" />
          <el-table-column prop="lastContact" label="最近互动" width="110" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openLeadDetail(row)">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 子标签 2 — 跟进记录 -->
      <el-tab-pane label="跟进记录" name="follow">
        <div class="follow-toggle">
          <el-radio-group v-model="followView" size="small">
            <el-radio-button label="timeline">时间线</el-radio-button>
            <el-radio-button label="table">表格</el-radio-button>
          </el-radio-group>
          <el-select
            v-model="followFilterCustomer"
            placeholder="按客户筛选"
            clearable
            class="follow-filter"
          >
            <el-option
              v-for="lead in leads"
              :key="lead.id"
              :label="lead.name"
              :value="lead.id"
            />
          </el-select>
        </div>

        <!-- 时间线视图 -->
        <el-timeline v-if="followView === 'timeline'" class="follow-timeline">
          <el-timeline-item
            v-for="rec in filteredFollowRecords"
            :key="rec.id"
            :type="rec.result === 'success' ? 'success' : rec.result === 'failed' ? 'danger' : 'primary'"
            :timestamp="rec.time"
            placement="top"
          >
            <div class="follow-card">
              <div class="follow-header">
                <span class="follow-customer">{{ rec.customerName }}</span>
                <el-tag size="small" :type="followMethodType(rec.method)">
                  {{ followMethodText(rec.method) }}
                </el-tag>
              </div>
              <p class="follow-content">{{ rec.content }}</p>
              <div class="follow-footer">
                <span class="follow-result">结果：{{ rec.result }}</span>
                <span class="follow-next">下一步：{{ rec.nextStep }}</span>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>

        <!-- 表格视图 -->
        <el-table
          v-else
          :data="filteredFollowRecords"
          stripe
          style="width: 100%"
          class="assets-table"
        >
          <el-table-column prop="time" label="时间" width="150" />
          <el-table-column prop="customerName" label="客户" min-width="100" />
          <el-table-column label="跟进方式" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="followMethodType(row.method)">
                {{ followMethodText(row.method) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="内容摘要" min-width="200" show-overflow-tooltip />
          <el-table-column prop="result" label="结果" min-width="100" />
          <el-table-column prop="nextStep" label="下一步" min-width="140" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>

      <!-- 子标签 3 — 成交记录 -->
      <el-tab-pane label="成交记录" name="deals">
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-label">总成交数</div>
            <div class="stat-value">{{ dealStats.totalCount }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">总成交金额</div>
            <div class="stat-value">¥{{ formatCurrency(dealStats.totalAmount) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">平均客单价</div>
            <div class="stat-value">¥{{ formatCurrency(dealStats.avgAmount) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">平均成交周期</div>
            <div class="stat-value">{{ dealStats.avgCycle }} 天</div>
          </div>
        </div>
        <el-table
          :data="filteredDeals"
          stripe
          style="width: 100%"
          class="assets-table"
          @sort-change="handleDealSort"
        >
          <el-table-column prop="customerName" label="客户名称" min-width="120" show-overflow-tooltip />
          <el-table-column prop="amount" label="成交金额" width="130" sortable>
            <template #default="{ row }">
              <span class="amount-cell">¥{{ formatCurrency(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="dealTime" label="成交时间" width="150" sortable />
          <el-table-column label="来源平台" min-width="100">
            <template #default="{ row }">
              {{ platformMap[row.platform] || row.platform }}
            </template>
          </el-table-column>
          <el-table-column prop="followCount" label="跟进次数" width="110" sortable />
          <el-table-column prop="cycleDays" label="成交周期" width="110" sortable>
            <template #default="{ row }">
              {{ row.cycleDays }} 天
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 子标签 4 — 转化漏斗 -->
      <el-tab-pane label="转化漏斗" name="funnel">
        <div class="funnel-layout">
          <div class="funnel-visual">
            <div class="funnel-stage" v-for="(stage, idx) in funnelStages" :key="stage.name">
              <div class="funnel-bar" :style="funnelBarStyle(idx)">
                <span class="funnel-name">{{ stage.name }}</span>
                <span class="funnel-count">{{ formatNumber(stage.count) }}</span>
                <span class="funnel-rate">{{ stage.rate }}%</span>
              </div>
            </div>
          </div>
          <div class="funnel-side">
            <div class="funnel-metric-card">
              <div class="funnel-metric-label">总体转化率</div>
              <div class="funnel-metric-value">{{ funnelMetrics.overall }}%</div>
            </div>
            <div class="funnel-metric-card">
              <div class="funnel-metric-label">7日转化率</div>
              <div class="funnel-metric-value">{{ funnelMetrics.week }}%</div>
            </div>
            <div class="funnel-metric-card">
              <div class="funnel-metric-label">30日转化率</div>
              <div class="funnel-metric-value">{{ funnelMetrics.month }}%</div>
            </div>
          </div>
        </div>
        <div class="funnel-table-wrap">
          <h4 class="funnel-table-title">各阶段详细数据</h4>
          <el-table :data="funnelStages" stripe style="width: 100%" class="assets-table">
            <el-table-column prop="name" label="阶段" min-width="100" />
            <el-table-column prop="count" label="数量" width="120">
              <template #default="{ row }">
                {{ formatNumber(row.count) }}
              </template>
            </el-table-column>
            <el-table-column prop="rate" label="转化率" width="120">
              <template #default="{ row }">
                {{ row.rate }}%
              </template>
            </el-table-column>
            <el-table-column prop="dropOff" label="流失数" width="120">
              <template #default="{ row }">
                {{ formatNumber(row.dropOff) }}
              </template>
            </el-table-column>
            <el-table-column prop="dropOffRate" label="流失率" width="120">
              <template #default="{ row }">
                {{ row.dropOffRate }}%
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 线索详情 Drawer -->
    <el-drawer
      v-model="leadDrawerVisible"
      title="线索详情"
      size="480"
      :destroy-on-close="true"
      class="detail-drawer"
    >
      <div v-if="selectedLead" class="drawer-content">
        <div class="lead-header">
          <div class="lead-avatar">{{ selectedLead.name?.[0] }}</div>
          <div class="lead-info">
            <h3 class="lead-name">{{ selectedLead.name }}</h3>
            <el-tag :type="gradeType(selectedLead.grade)" size="small">
              {{ selectedLead.grade }}级
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">客户信息</div>
          <div class="lead-info-row">
            <span class="info-label">来源平台：</span>
            <span class="info-value">{{ platformMap[selectedLead.platform] || selectedLead.platform }}</span>
          </div>
          <div class="lead-info-row">
            <span class="info-label">首次接触：</span>
            <span class="info-value">{{ selectedLead.firstContact }}</span>
          </div>
          <div class="lead-info-row">
            <span class="info-label">最近互动：</span>
            <span class="info-value">{{ selectedLead.lastContact }}</span>
          </div>
          <div class="lead-info-row">
            <span class="info-label">当前状态：</span>
            <el-tag :type="statusType(selectedLead.status)" size="small">
              {{ statusText(selectedLead.status) }}
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">来源视频</div>
          <div class="lead-source-content">{{ selectedLead.sourceContent || '暂无来源内容' }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">互动历史</div>
          <el-timeline class="lead-timeline">
            <el-timeline-item
              v-for="(hist, idx) in selectedLead.history"
              :key="idx"
              :timestamp="hist.time"
              placement="top"
            >
              <div class="lead-history-item">{{ hist.action }}</div>
            </el-timeline-item>
          </el-timeline>
        </div>
        <div class="detail-section">
          <div class="detail-label">标签</div>
          <div class="detail-tags">
            <el-tag
              v-for="tag in selectedLead.tags"
              :key="tag"
              type="info"
              class="tag-item"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">备注</div>
          <div class="detail-text">{{ selectedLead.note }}</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import axios from 'axios'

const activeTab = ref('leads')
const searchQuery = ref('')
const filterGrades = ref([])
const filterSource = ref('')
const filterDateRange = ref([])
const filterStatus = ref('')

const leadDrawerVisible = ref(false)
const selectedLead = ref(null)

const followView = ref('timeline')
const followFilterCustomer = ref('')

const leads = ref([])

async function loadLeads() {
  try {
    const { data } = await axios.get('/api/acquisition/leads')
    leads.value = data.leads || []
  } catch (e) {
    ElMessage.error('加载线索失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadLeads()
  loadFunnel()
  loadConversions()
})

const platformMap = {
  douyin: '抖音',
  xhs: '小红书',
  kuaishou: '快手',
  bilibili: 'B站',
  videochannel: '视频号',
  weibo: '微博',
  wechat: '微信'
}

const gradeType = (grade) => {
  const map = { A: 'danger', B: 'warning', C: 'info', D: 'info' }
  return map[grade] || 'info'
}
const statusType = (status) => {
  const map = { qualified: 'success', contacting: 'warning', converted: 'success', lost: 'info' }
  return map[status] || 'info'
}
const statusText = (status) => {
  const map = { qualified: '合格', contacting: '跟进中', converted: '已成交', lost: '已流失' }
  return map[status] || status
}
const followMethodType = (method) => {
  const map = { dm: 'primary', phone: 'success', wechat: 'success', email: 'info' }
  return map[method] || 'info'
}
const followMethodText = (method) => {
  const map = { dm: '私信', phone: '电话', wechat: '微信', email: '邮件' }
  return map[method] || method
}


const followRecords = computed(() => {
  const records = []
  let id = 1
  for (const lead of leads.value) {
    const history = lead.history || []
    for (const h of history) {
      records.push({
        id: id++,
        customerId: lead.id,
        customerName: lead.name,
        time: h.time,
        method: h.method || h.channel || '—',
        content: h.action || h.note || '—',
        result: h.result || '—',
        nextStep: h.nextStep || '—',
      })
    }
  }
  return records
})

const dealRecords = ref([])

async function loadConversions() {
  try {
    const { data } = await axios.get('/api/acquisition/conversions')
    const conversions = data?.conversions || data || []
    dealRecords.value = (Array.isArray(conversions) ? conversions : []).map((c, i) => ({
      id: c.id || i + 1,
      customerName: c.customer_name || c.name || '—',
      amount: c.amount || c.deal_amount || 0,
      dealTime: c.converted_at || c.deal_time || c.created_at || '',
      platform: c.platform || '—',
      followCount: c.follow_count || 0,
      cycleDays: c.cycle_days || 0,
    }))
  } catch {
    dealRecords.value = []
  }
}

// 漏斗数据 — 从 API 加载
const STAGE_LABELS = { discovered: '发现', replied: '互动', dm_sent: '私信', responded: '回复', qualified: '线索', converted: '成交' }
const STAGE_COLORS = ['#4f46e5', '#3b82f6', '#22c55e', '#fbbf24', '#f43f5e', '#ec4899']
const funnelStages = ref([])
const funnelMetrics = ref({ overall: 0, week: 0, month: 0 })

async function loadFunnel() {
  try {
    const { data } = await axios.get('/api/acquisition/leads/funnel')
    const stages = data?.funnel || []
    const total = data?.total_leads || 1
    funnelStages.value = stages.map((s, i) => {
      const prevCount = i > 0 ? stages[i - 1].count : s.count
      const dropOff = i > 0 ? prevCount - s.count : 0
      return {
        name: STAGE_LABELS[s.stage] || s.stage,
        count: s.count,
        rate: total > 0 ? ((s.count / total) * 100) : 0,
        dropOff: Math.max(0, dropOff),
        dropOffRate: prevCount > 0 ? Math.round((dropOff / prevCount) * 1000) / 10 : 0,
        color: STAGE_COLORS[i] || '#409eff',
      }
    })
    funnelMetrics.value = {
      overall: data?.conversion_rate || 0,
      week: 0,
      month: 0,
    }
  } catch {
    funnelStages.value = []
  }
}

// ========== 筛选逻辑 ==========
const baseFilter = (list) => {
  return list.filter(item => {
    const matchSearch = !searchQuery.value ||
      item.name?.includes(searchQuery.value) ||
      item.note?.includes(searchQuery.value) ||
      item.customerName?.includes(searchQuery.value)
    const matchGrade = filterGrades.value.length === 0 || filterGrades.value.includes(item.grade)
    const matchSource = !filterSource.value || item.platform === filterSource.value
    let matchDate = true
    if (filterDateRange.value && filterDateRange.value.length === 2) {
      const d = item.firstContact || item.dealTime?.slice(0, 10) || item.time?.slice(0, 10)
      matchDate = d >= filterDateRange.value[0] && d <= filterDateRange.value[1]
    }
    const matchStatus = !filterStatus.value || item.status === filterStatus.value
    return matchSearch && matchGrade && matchSource && matchDate && matchStatus
  })
}

const filteredLeads = computed(() => baseFilter(leads))
const filteredDeals = computed(() => baseFilter(dealRecords.value))

const filteredFollowRecords = computed(() => {
  const base = baseFilter(followRecords)
  if (followFilterCustomer.value) {
    return base.filter(r => r.customerId === followFilterCustomer.value)
  }
  return base
})

const dealStats = computed(() => {
  const items = filteredDeals.value
  const totalCount = items.length
  const totalAmount = items.reduce((s, i) => s + i.amount, 0)
  const avgAmount = totalCount ? Math.round(totalAmount / totalCount) : 0
  const avgCycle = totalCount ? Math.round(items.reduce((s, i) => s + i.cycleDays, 0) / totalCount) : 0
  return { totalCount, totalAmount, avgAmount, avgCycle }
})

function formatNumber(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n?.toString() || '0'
}

function formatCurrency(n) {
  return n.toLocaleString('zh-CN')
}

function openLeadDetail(row) {
  selectedLead.value = row
  leadDrawerVisible.value = true
}

function handleDealSort() {}

// 漏斗条形样式
function funnelBarStyle(idx) {
  const widths = ['100%', '90%', '75%', '60%', '45%']
  const colors = ['#4f46e5', '#3b82f6', '#22c55e', '#fbbf24', '#f43f5e']
  const lightColors = ['rgba(79,70,229,0.15)', 'rgba(59,130,246,0.15)', 'rgba(34,197,94,0.15)', 'rgba(251,191,36,0.15)', 'rgba(244,63,94,0.15)']
  return {
    width: widths[idx],
    background: `linear-gradient(90deg, ${lightColors[idx]}, ${colors[idx]})`,
    boxShadow: `0 4px 12px ${colors[idx]}30`
  }
}
</script>

<style scoped>
.customer-assets-page {
  padding: 24px;
  min-height: 100vh;
}

.page-header {
  margin-bottom: 20px;
}

.title-section {
  margin-bottom: 16px;
}

.page-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}

.filter-section {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.search-input {
  width: 240px;
}

.filter-item {
  width: 160px;
}

.content-tabs {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

:deep(.content-tabs .el-tabs__header) {
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  margin: 0;
}

:deep(.content-tabs .el-tabs__content) {
  padding: 16px;
}

/* 表格 */
.assets-table {
  background: transparent;
}

:deep(.assets-table .el-table__header-wrapper th) {
  background: var(--table-header-bg);
  color: var(--text-secondary);
  font-weight: 600;
}

:deep(.assets-table .el-table__row:hover > td) {
  background: var(--hover-bg) !important;
}

.platform-tag {
  margin-right: 4px;
}

.tag-item {
  margin-right: 4px;
}

/* 跟进记录切换 */
.follow-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 10px;
}

.follow-filter {
  width: 200px;
}

.follow-timeline {
  padding-left: 8px;
}

.follow-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px;
  box-shadow: var(--shadow-sm);
}

.follow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.follow-customer {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.follow-content {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.follow-footer {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent-primary);
  font-variant-numeric: tabular-nums;
}

.amount-cell {
  font-weight: 600;
  color: var(--accent-primary);
  font-variant-numeric: tabular-nums;
}

/* 漏斗 */
.funnel-layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.funnel-visual {
  flex: 1;
  min-width: 320px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px;
}

.funnel-stage {
  width: 100%;
  display: flex;
  justify-content: center;
}

.funnel-bar {
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  color: var(--text-inverse);
  font-weight: 600;
  transition: all 0.3s ease;
  position: relative;
}

.funnel-bar:hover {
  transform: scale(1.02);
}

.funnel-name {
  font-size: 14px;
}

.funnel-count {
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}

.funnel-rate {
  font-size: 12px;
  opacity: 0.9;
  font-variant-numeric: tabular-nums;
}

.funnel-side {
  width: 220px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.funnel-metric-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.funnel-metric-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.funnel-metric-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--accent-primary);
  font-variant-numeric: tabular-nums;
}

.funnel-table-wrap {
  margin-top: 8px;
}

.funnel-table-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Drawer */
:deep(.detail-drawer .el-drawer__body) {
  padding: 0;
}

.drawer-content {
  padding: 20px;
}

.lead-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.lead-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--accent-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.lead-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.lead-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-section {
  margin-bottom: 16px;
}

.detail-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.detail-text {
  font-size: 13px;
  color: var(--text-primary);
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.lead-info-row {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.info-label {
  color: var(--text-tertiary);
  min-width: 80px;
}

.info-value {
  color: var(--text-primary);
}

.lead-source-content {
  font-size: 13px;
  color: var(--text-primary);
  padding: 10px 12px;
  background: var(--bg-canvas);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.lead-timeline {
  padding-left: 4px;
}

.lead-history-item {
  font-size: 13px;
  color: var(--text-primary);
}

/* 响应式 */
@media (max-width: 1280px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .funnel-layout {
    flex-direction: column;
  }
  .funnel-side {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }
  .funnel-metric-card {
    flex: 1;
    min-width: 140px;
  }
}

@media (max-width: 768px) {
  .filter-section {
    flex-direction: column;
    align-items: stretch;
  }
  .search-input,
  .filter-item {
    width: 100%;
  }
  .stats-row {
    grid-template-columns: 1fr;
  }
  .follow-toggle {
    flex-direction: column;
    align-items: stretch;
  }
  .follow-filter {
    width: 100%;
  }
  .funnel-bar {
    height: 40px;
    padding: 0 10px;
  }
  .funnel-name {
    font-size: 12px;
  }
  .funnel-count {
    font-size: 13px;
  }
  .funnel-rate {
    display: none;
  }
}
</style>
