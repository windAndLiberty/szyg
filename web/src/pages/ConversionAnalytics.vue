<template>
  <div class="page-container">
    <h2 class="page-title">转化分析</h2>
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6" v-for="s in funnelStats" :key="s.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-rate">{{ s.rate }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs" style="margin-top:16px">
      <el-tab-pane label="转化漏斗" name="funnel">
        <div class="funnel-container">
          <div v-for="(stage, i) in funnelStages" :key="stage.name" class="funnel-stage">
            <div class="funnel-bar" :style="{ width: stage.width + '%', background: stage.color }">
              <span class="funnel-label">{{ stage.name }}: {{ stage.count }}</span>
            </div>
            <div v-if="i < funnelStages.length - 1" class="funnel-arrow">↓ {{ stage.conversionRate }}%</div>
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane label="线索分布" name="distribution">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never">
              <template #header><span>等级分布</span></template>
              <el-table :data="gradeData" stripe>
                <el-table-column prop="grade" label="等级" width="80" />
                <el-table-column prop="count" label="数量" width="80" />
                <el-table-column prop="percentage" label="占比" width="80" />
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never">
              <template #header><span>平台对比</span></template>
              <el-table :data="platformData" stripe>
                <el-table-column prop="platform" label="平台" width="100" />
                <el-table-column prop="leads" label="线索量" width="80" />
                <el-table-column prop="converted" label="转化数" width="80" />
                <el-table-column prop="rate" label="转化率" width="80" />
              </el-table>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
      <el-tab-pane label="跟进效率" name="efficiency">
        <el-table :data="efficiencyData" stripe>
          <el-table-column prop="metric" label="指标" min-width="160" />
          <el-table-column prop="value" label="数值" width="120" />
          <el-table-column prop="trend" label="趋势" width="100" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('funnel')
const funnelStats = ref([
  { label: '发现线索', value: '0', rate: '100%' },
  { label: '已回复', value: '0', rate: '0%' },
  { label: '已私信', value: '0', rate: '0%' },
  { label: '已成交', value: '0', rate: '0%' },
])
const funnelStages = ref([])
const gradeData = ref([])
const platformData = ref([])
const efficiencyData = ref([])

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/acquisition/leads/funnel')
    if (data.stages) funnelStages.value = data.stages
    if (data.stats) funnelStats.value = data.stats
    if (data.grades) gradeData.value = data.grades
    if (data.platforms) platformData.value = data.platforms
    if (data.efficiency) efficiencyData.value = data.efficiency
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
.stat-rate { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }
.studio-tabs { border-radius: 8px; }
.funnel-container { padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.funnel-stage { display: flex; flex-direction: column; align-items: center; }
.funnel-bar { height: 40px; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 13px; font-weight: 600; min-width: 200px; transition: width 0.3s; }
.funnel-arrow { font-size: 12px; color: var(--text-tertiary); margin: 4px 0; }
</style>
