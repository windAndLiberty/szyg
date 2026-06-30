<template>
  <div class="page-container">
    <h2 class="page-title">内容分析</h2>
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6" v-for="s in summaryStats" :key="s.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ s.label }}</div>
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-change" :class="s.change >= 0 ? 'up' : 'down'">{{ s.change >= 0 ? '↗' : '↘' }} {{ Math.abs(s.change) }}%</div>
        </el-card>
      </el-col>
    </el-row>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs" style="margin-top:16px">
      <el-tab-pane label="生产统计" name="production">
        <el-table :data="productionData" stripe>
          <el-table-column prop="date" label="日期" width="120" />
          <el-table-column prop="articles" label="图文" width="80" />
          <el-table-column prop="videos" label="视频" width="80" />
          <el-table-column prop="images" label="图片" width="80" />
          <el-table-column prop="audios" label="音频" width="80" />
          <el-table-column prop="total" label="总计" width="80" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="发布分析" name="publish">
        <el-table :data="publishData" stripe>
          <el-table-column prop="platform" label="平台" width="100" />
          <el-table-column prop="total" label="发布数" width="80" />
          <el-table-column prop="success" label="成功" width="80" />
          <el-table-column prop="failed" label="失败" width="80" />
          <el-table-column label="成功率" width="100">
            <template #default="{ row }">
              <el-progress :percentage="row.total ? Math.round(row.success / row.total * 100) : 0" :stroke-width="6" />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="内容表现" name="performance">
        <el-table :data="performanceData" stripe>
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column prop="platform" label="平台" width="90" />
          <el-table-column prop="views" label="播放" width="80" />
          <el-table-column prop="likes" label="点赞" width="80" />
          <el-table-column prop="comments" label="评论" width="80" />
          <el-table-column prop="shares" label="分享" width="80" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('production')
const summaryStats = ref([
  { label: '总内容数', value: '0', change: 0 },
  { label: '本月生产', value: '0', change: 0 },
  { label: '发布成功率', value: '0%', change: 0 },
  { label: '总播放量', value: '0', change: 0 },
])
const productionData = ref([])
const publishData = ref([])
const performanceData = ref([])

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/publisher/stats')
    if (data.summary) summaryStats.value = data.summary
    if (data.production) productionData.value = data.production
    if (data.publish) publishData.value = data.publish
    if (data.performance) performanceData.value = data.performance
  } catch {
    // API not ready, keep empty state
  }
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
.stat-change { font-size: 12px; margin-top: 4px; }
.stat-change.up { color: #22c55e; }
.stat-change.down { color: #f43f5e; }
.studio-tabs { border-radius: 8px; }
</style>
