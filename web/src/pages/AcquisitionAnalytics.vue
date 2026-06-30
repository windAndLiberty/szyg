<template>
  <div class="page-container">
    <h2 class="page-title">截流效果</h2>
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6" v-for="s in summaryStats" :key="s.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs" style="margin-top:16px">
      <el-tab-pane label="截流概览" name="overview">
        <el-table :data="dailyData" stripe>
          <el-table-column prop="date" label="日期" width="120" />
          <el-table-column prop="sent" label="发送量" width="100" />
          <el-table-column prop="replied" label="回复量" width="100" />
          <el-table-column label="回复率" width="120">
            <template #default="{ row }">
              <el-progress :percentage="row.sent ? Math.round(row.replied / row.sent * 100) : 0" :stroke-width="6" />
            </template>
          </el-table-column>
          <el-table-column prop="leads" label="线索数" width="100" />
          <el-table-column prop="converted" label="转化数" width="100" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="平台对比" name="platform">
        <el-table :data="platformData" stripe>
          <el-table-column prop="platform" label="平台" width="100" />
          <el-table-column prop="sent" label="发送量" width="100" />
          <el-table-column prop="replied" label="回复量" width="100" />
          <el-table-column prop="leads" label="线索数" width="100" />
          <el-table-column prop="conversionRate" label="转化率" width="100" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="策略对比" name="strategy">
        <el-table :data="strategyData" stripe>
          <el-table-column prop="name" label="测试名称" min-width="160" />
          <el-table-column prop="winner" label="胜出策略" width="100" />
          <el-table-column prop="improvement" label="提升幅度" width="100" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('overview')
const summaryStats = ref([
  { label: '评论发送总量', value: '0' },
  { label: '平均回复率', value: '0%' },
  { label: '线索发现数', value: '0' },
  { label: '客户转化数', value: '0' },
])
const dailyData = ref([])
const platformData = ref([])
const strategyData = ref([])

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/acquisition/stats')
    if (data.summary) summaryStats.value = data.summary
    if (data.daily) dailyData.value = data.daily
    if (data.platforms) platformData.value = data.platforms
  } catch {}
  try {
    const { data } = await axios.get('/api/acquisition/ab/list')
    if (Array.isArray(data)) strategyData.value = data
  } catch {}
})
</script>

<style scoped>
.page-container { padding: 24px; }
.page-title { margin: 0 0 20px; font-size: 18px; }
.stats-row { margin-bottom: 4px; }
.stat-card { text-align: center; }
.stat-card :deep(.el-card__body) { padding: 16px; }
.stat-label { font-size: 12px; color: var(--text-tertiary); margin-bottom: 8px; }
.stat-value { font-size: 24px; font-weight: 700; color: var(--text-primary); }
.studio-tabs { border-radius: 8px; }
</style>
