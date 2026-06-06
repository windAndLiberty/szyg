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

      <!-- Stats -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6" v-for="s in stats" :key="s.title">
          <el-card shadow="hover" :class="['stat-card', s.color]">
            <div class="stat-icon">{{ s.icon }}</div>
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-title">{{ s.title }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <!-- Hot Tools -->
        <el-col :span="16">
          <el-card class="section-card">
            <template #header><div class="card-header"><h3>🔥 热门工具</h3><el-button text type="primary" @click="$router.push('/tools')">全部工具 →</el-button></div></template>
            <el-row :gutter="16">
              <el-col :span="8" v-for="tool in hotTools" :key="tool.id">
                <div class="tool-mini" @click="openTool(tool)">
                  <div class="tool-mini-icon"><el-icon :size="32"><component :is="tool.icon||'Box'" /></el-icon></div>
                  <div class="tool-mini-title">{{ tool.title }}</div>
                  <div class="tool-mini-desc">{{ tool.desc?.slice(0,20) }}</div>
                  <el-button size="small" :type="tool.is_yun?'primary':'warning'" class="tool-mini-btn">
                    {{ tool.is_yun ? '启动' : '安装' }}
                  </el-button>
                </div>
              </el-col>
            </el-row>
          </el-card>
        </el-col>

        <!-- Update Log -->
        <el-col :span="8">
          <el-card class="section-card">
            <template #header><h3>📋 更新日志</h3></template>
            <el-timeline>
              <el-timeline-item v-for="(log, i) in updateLogs" :key="i"
                :timestamp="log.time" placement="top"
                :color="i === 0 ? '#409eff' : '#c0c4cc'">
                <div class="log-title">{{ log.title }}</div>
                <div class="log-desc">{{ log.desc }}</div>
              </el-timeline-item>
            </el-timeline>
          </el-card>
        </el-col>
      </el-row>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const announcements = ref([])
const stats = ref([
  { icon: '🧰', title: '工具总数', value: 0, color: 'blue' },
  { icon: '💾', title: '已安装', value: 0, color: 'green' },
  { icon: '🤖', title: 'AI智能体', value: 0, color: 'purple' },
  { icon: '👤', title: '用户数', value: 0, color: 'orange' },
])
const hotTools = ref([])
const updateLogs = ref([
  { time: '2024-06-04', title: 'AI智能体广场上线', desc: '12个中小企业场景智能体' },
  { time: '2024-06-03', title: 'AI工具导航上线', desc: '24个精选AI工具，8大分类' },
  { time: '2024-06-01', title: '系统 v1.0 发布', desc: '核心平台 + 5大AI能力上线' },
])

onMounted(async () => {
  try {
    const [toolRes, installRes, agentRes, announceRes, userRes] = await Promise.all([
      axios.get('/api/tools/catalog'),
      axios.get('/api/tools/installed'),
      axios.get('/api/agents/list'),
      axios.get('/api/announce/list'),
      axios.get('/api/auth/users').catch(() => ({ data: [] })),
    ])
    stats.value[0].value = toolRes.data.length
    stats.value[1].value = installRes.data.length
    stats.value[2].value = agentRes.data.length
    stats.value[3].value = Array.isArray(userRes.data) ? userRes.data.length : 1
    hotTools.value = toolRes.data.slice(0, 6)
    announcements.value = announceRes.data?.slice(0, 3) || []
  } catch (_) {}
})

function openTool(tool) {
  if (tool.is_yun && tool.windows_canshu) {
    try {
      const args = JSON.parse(`[${tool.windows_canshu}]`)
      router.push(args[0] || '/chat')
    } catch { router.push('/chat') }
  } else {
    ElMessage.info('本地工具需先安装')
  }
}
</script>

<style scoped>
.announce-bar { margin-bottom: 16px; }
.announce-item { margin-bottom: 8px; }
.stats-row { margin-bottom: 20px; }
.stat-card { text-align: center; }
.stat-card.blue .stat-value { color: #409eff; }
.stat-card.green .stat-value { color: #67c23a; }
.stat-card.purple .stat-value { color: #9b59b6; }
.stat-card.orange .stat-value { color: #e6a23c; }
.stat-icon { font-size: 28px; margin-bottom: 4px; }
.stat-value { font-size: 32px; font-weight: bold; }
.stat-title { color: #909399; margin-top: 4px; font-size: 13px; }
.section-card { margin-bottom: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header h3 { margin: 0; }
.tool-mini { text-align: center; padding: 12px 8px; cursor: pointer; border-radius: 8px; transition: .2s; }
.tool-mini:hover { background: #f5f7fa; transform: translateY(-2px); }
.tool-mini-icon { color: #409eff; margin-bottom: 6px; }
.tool-mini-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
.tool-mini-desc { font-size: 11px; color: #c0c4cc; margin-bottom: 8px; }
.tool-mini-btn { width: 100%; }
.log-title { font-weight: 600; font-size: 14px; }
.log-desc { font-size: 12px; color: #909399; margin-top: 2px; }
</style>
