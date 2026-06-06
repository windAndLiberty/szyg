<template>
    <div class="agents-page">
      <div class="agents-header">
        <h2>🤖 AI智能体广场</h2>
        <p class="subtitle">系统提示词层级体系：基础层 → 领域层 → 任务层，按需选用AI专家</p>
      </div>

      <!-- Tier Info -->
      <el-row :gutter="16" class="tier-row">
        <el-col :span="8" v-for="t in tiers" :key="t.key">
          <el-card :class="['tier-card', t.key]" shadow="hover" @click="activeTier = t.key">
            <div class="tier-icon">{{ t.key === 'base' ? '🧱' : t.key === 'domain' ? '🏗️' : '🎯' }}</div>
            <div class="tier-name">{{ t.label.split('—')[0] }}</div>
            <div class="tier-desc">{{ t.label.split('—')[1] || '' }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Filter Bar -->
      <div class="filter-bar">
        <el-input v-model="search" placeholder="搜索智能体..." prefix-icon="Search" clearable class="filter-search" @input="filterAgents" />
        <el-select v-model="activeTier" placeholder="提示词层级" clearable @change="filterAgents">
          <el-option v-for="t in tiers" :key="t.key" :label="t.label.split('—')[0]" :value="t.key" />
        </el-select>
        <el-select v-model="activeCat" placeholder="全部分类" clearable @change="filterAgents">
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
        <span class="result-count">共 {{ filteredAgents.length }} 个智能体</span>
      </div>

      <!-- Agent Grid -->
      <div class="agent-grid" v-loading="loading">
        <div class="agent-card" v-for="agent in filteredAgents" :key="agent.id" @click="openAgent(agent)">
          <div class="agent-avatar">{{ agent.avatar }}</div>
          <div class="agent-body">
            <div class="agent-name">{{ agent.name }}</div>
            <el-tag :type="tierType(agent.tier)" size="small" effect="plain">{{ tierLabel(agent.tier) }}</el-tag>
            <div class="agent-desc">{{ agent.description }}</div>
            <div class="agent-meta">
              <el-rate :model-value="agent.rating" disabled show-score text-color="#ff9900" size="small" />
              <span class="usage">{{ agent.usage_count }} 次使用</span>
            </div>
            <div class="agent-tags">
              <el-tag size="small" v-for="t in agent.tags?.slice(0,3)" :key="t" class="tag">{{ t }}</el-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- Agent Detail Dialog -->
      <el-dialog v-model="dialogVisible" :title="selected?.name" width="700px">
        <template v-if="selected">
          <div class="detail-avatar">{{ selected.avatar }}</div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="层级">{{ tierLabel(selected.tier) }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ selected.category }}</el-descriptions-item>
            <el-descriptions-item label="推荐模型">{{ selected.model_preference || '默认' }}</el-descriptions-item>
            <el-descriptions-item label="温度">{{ selected.temperature }}</el-descriptions-item>
            <el-descriptions-item label="标签" :span="2">
              <el-tag size="small" v-for="t in selected.tags" :key="t" class="detail-tag">{{ t }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">{{ selected.description }}</el-descriptions-item>
          </el-descriptions>
          <div class="prompt-section">
            <h4>📋 系统提示词</h4>
            <div class="prompt-box">{{ selected.system_prompt }}</div>
          </div>
          <div style="margin-top: 16px; text-align: right;">
            <el-button type="primary" @click="useAgent(selected)">使用此智能体 → 开始对话</el-button>
          </div>
        </template>
      </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const allAgents = ref([])
const filteredAgents = ref([])
const tiers = ref([])
const categories = ref([])
const activeTier = ref('')
const activeCat = ref('')
const search = ref('')
const loading = ref(false)
const dialogVisible = ref(false)
const selected = ref(null)

onMounted(async () => {
  loading.value = true
  try {
    const [aRes, tRes, cRes] = await Promise.all([
      axios.get('/api/agents/list'),
      axios.get('/api/agents/tiers'),
      axios.get('/api/agents/categories'),
    ])
    allAgents.value = aRes.data
    filteredAgents.value = aRes.data
    tiers.value = tRes.data
    categories.value = cRes.data
  } catch (_) {}
  loading.value = false
})

function filterAgents() {
  let agents = allAgents.value
  if (activeTier.value) agents = agents.filter(a => a.tier === activeTier.value)
  if (activeCat.value) agents = agents.filter(a => a.category === activeCat.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    agents = agents.filter(a => a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q) || a.tags?.some(t => t.toLowerCase().includes(q)))
  }
  agents.sort((a,b) => (b.rating||0) - (a.rating||0))
  filteredAgents.value = agents
}

function openAgent(agent) {
  selected.value = agent
  dialogVisible.value = true
}

function useAgent(agent) {
  dialogVisible.value = false
  router.push({ path: '/chat', query: { agent: agent.id } })
}

function tierType(t) { return { base: '', domain: 'success', task: 'warning' }[t] || '' }
function tierLabel(t) { return { base: '基础层', domain: '领域层', task: '任务层' }[t] || t }
</script>

<style scoped>
.agents-page { max-width: 1400px; margin: 0 auto; }
.agents-header { text-align: center; margin-bottom: 24px; }
.agents-header h2 { font-size: 28px; margin: 0 0 8px; }
.subtitle { color: #909399; margin: 0; font-size: 14px; }
.tier-row { margin-bottom: 24px; }
.tier-card { text-align: center; cursor: pointer; border-radius: 12px; transition: .3s; }
.tier-card:hover { transform: translateY(-4px); }
.tier-card.base { border-top: 3px solid #409eff; }
.tier-card.domain { border-top: 3px solid #67c23a; }
.tier-card.task { border-top: 3px solid #e6a23c; }
.tier-icon { font-size: 36px; margin-bottom: 8px; }
.tier-name { font-weight: bold; font-size: 16px; }
.tier-desc { font-size: 12px; color: #909399; margin-top: 4px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 20px; align-items: center; }
.filter-search { flex: 1; max-width: 300px; }
.result-count { color: #909399; font-size: 13px; }
.agent-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
.agent-card { display: flex; gap: 16px; background: #fff; border-radius: 12px; padding: 20px; cursor: pointer; border: 1px solid #ebeef5; transition: .3s; }
.agent-card:hover { transform: translateY(-4px); box-shadow: 0 8px 25px rgba(0,0,0,0.1); border-color: #409eff; }
.agent-avatar { font-size: 48px; flex-shrink: 0; }
.agent-body { flex: 1; min-width: 0; }
.agent-name { font-weight: 700; font-size: 16px; margin-bottom: 6px; }
.agent-desc { font-size: 13px; color: #606266; margin: 8px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.agent-meta { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
.usage { font-size: 12px; color: #c0c4cc; }
.agent-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.tag { font-size: 11px; }
.prompt-section { margin-top: 20px; }
.prompt-section h4 { margin: 0 0 8px; }
.prompt-box { background: #f5f7fa; border: 1px solid #e4e7ed; border-radius: 8px; padding: 16px; font-size: 13px; line-height: 1.8; white-space: pre-wrap; max-height: 200px; overflow-y: auto; }
.detail-avatar { font-size: 60px; text-align: center; margin-bottom: 16px; }
.detail-tag { margin: 2px; }
</style>
