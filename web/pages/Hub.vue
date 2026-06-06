<template>
    <div class="hub-page">
      <div class="hub-header">
        <h2>🔗 AI工具聚合导航平台</h2>
        <p class="subtitle">精选200+ AI工具，按分类浏览，快速找到你需要的AI能力</p>
      </div>

      <!-- Category Tabs -->
      <div class="category-tabs">
        <el-radio-group v-model="activeCat" size="large" @change="filterTools">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="cat in categories" :key="cat.key" :value="cat.key">
            {{ cat.label }} <el-badge :value="cat.count" :max="99" />
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- Search -->
      <div class="hub-search">
        <el-input v-model="search" placeholder="搜索AI工具..." prefix-icon="Search" clearable class="search-input" @input="filterTools" />
        <el-checkbox v-model="hotOnly" @change="filterTools">仅热门</el-checkbox>
        <el-checkbox v-model="newOnly" @change="filterTools">最新上线</el-checkbox>
        <span class="result-count">共 {{ filteredTools.length }} 个工具</span>
      </div>

      <!-- Tool Grid -->
      <div class="tool-grid" v-loading="loading">
        <div class="tool-card" v-for="tool in filteredTools" :key="tool.id" @click="openTool(tool.url)">
          <div class="tool-icon">{{ tool.icon }}</div>
          <div class="tool-name">{{ tool.name }}</div>
          <div class="tool-desc">{{ tool.desc }}</div>
          <div class="tool-footer">
            <el-tag size="small" v-for="t in tool.tags?.slice(0,2)" :key="t" class="tag">{{ t }}</el-tag>
            <el-tag v-if="tool.is_hot" type="danger" size="small" effect="dark">🔥热门</el-tag>
            <el-tag v-if="tool.is_new" type="success" size="small" effect="dark">🆕新品</el-tag>
            <el-tag v-if="!tool.is_free" type="warning" size="small">💰付费</el-tag>
          </div>
        </div>
      </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const allTools = ref([])
const filteredTools = ref([])
const categories = ref([])
const activeCat = ref('')
const search = ref('')
const hotOnly = ref(false)
const newOnly = ref(false)
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const [tRes, cRes] = await Promise.all([
      axios.get('/api/hub/list'),
      axios.get('/api/hub/categories'),
    ])
    allTools.value = tRes.data
    filteredTools.value = tRes.data
    categories.value = cRes.data
  } catch (_) {}
  loading.value = false
})

function filterTools() {
  let tools = allTools.value
  if (activeCat.value) tools = tools.filter(t => t.category === activeCat.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    tools = tools.filter(t => t.name.toLowerCase().includes(q) || t.desc.toLowerCase().includes(q))
  }
  if (hotOnly.value) tools = tools.filter(t => t.is_hot)
  if (newOnly.value) tools = tools.filter(t => t.is_new)
  filteredTools.value = tools
}

function openTool(url) { window.open(url, '_blank') }
</script>

<style scoped>
.hub-page { max-width: 1400px; margin: 0 auto; }
.hub-header { text-align: center; margin-bottom: 24px; }
.hub-header h2 { font-size: 28px; color: #303133; margin: 0 0 8px; }
.subtitle { color: #909399; margin: 0; }
.category-tabs { margin-bottom: 20px; display: flex; justify-content: center; flex-wrap: wrap; gap: 8px; }
.hub-search { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.search-input { flex: 1; max-width: 400px; }
.result-count { color: #909399; font-size: 13px; }
.tool-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.tool-card { background: #fff; border-radius: 12px; padding: 20px; cursor: pointer; border: 1px solid #ebeef5; transition: all .3s; }
.tool-card:hover { transform: translateY(-4px); box-shadow: 0 8px 25px rgba(0,0,0,0.1); border-color: #409eff; }
.tool-icon { font-size: 40px; text-align: center; margin-bottom: 12px; }
.tool-name { font-weight: 700; font-size: 16px; margin-bottom: 8px; text-align: center; }
.tool-desc { font-size: 13px; color: #909399; margin-bottom: 12px; text-align: center; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.tool-footer { display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; }
.tag { font-size: 11px; }
</style>
