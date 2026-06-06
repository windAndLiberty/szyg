<template>
    <div class="tools-page">
      <div class="tools-header">
        <el-input v-model="search" placeholder="搜索工具..." prefix-icon="Search" class="search-input" clearable />
        <el-select v-model="category" placeholder="全部分类" clearable>
          <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
        </el-select>
      </div>
      <el-row :gutter="16">
        <el-col :span="6" v-for="tool in filteredTools" :key="tool.id">
          <el-card shadow="hover" class="tool-card">
            <div class="tool-icon">
              <el-icon :size="48"><component :is="tool.icon || 'Box'" /></el-icon>
            </div>
            <div class="tool-title">{{ tool.title }}</div>
            <div class="tool-desc">{{ tool.desc }}</div>
            <div class="tool-meta">
              <el-tag size="small" :type="tool.is_yun ? '' : 'warning'">
                {{ tool.is_yun ? '云端' : '本地' }}
              </el-tag>
              <span class="version">v{{ tool.version }}</span>
            </div>
            <el-button size="small" type="primary" class="tool-btn" @click="openTool(tool)">
              立即启动
            </el-button>
          </el-card>
        </el-col>
      </el-row>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const allTools = ref([])
const categories = ref([])
const search = ref('')
const category = ref('')

const filteredTools = computed(() => {
  let tools = allTools.value
  if (category.value) tools = tools.filter(t => t.category === category.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    tools = tools.filter(t => t.title.toLowerCase().includes(q) || t.desc.toLowerCase().includes(q))
  }
  return tools
})

onMounted(async () => {
  try {
    const [tRes, cRes] = await Promise.all([
      axios.get('/api/tools/catalog'),
      axios.get('/api/tools/categories'),
    ])
    allTools.value = tRes.data
    categories.value = cRes.data
  } catch (_) {}
})

function openTool(tool) {
  if (tool.windows_canshu) {
    try {
      const args = JSON.parse(`[${tool.windows_canshu}]`)
      router.push(args[0] || '/chat')
    } catch { router.push('/chat') }
  }
}
</script>

<style scoped>
.tools-header { display: flex; gap: 12px; margin-bottom: 20px; }
.search-input { width: 300px; }
.tool-card { text-align: center; margin-bottom: 16px; cursor: pointer; }
.tool-card:hover { transform: translateY(-4px); transition: .3s; }
.tool-icon { margin: 12px 0; color: #409eff; }
.tool-title { font-weight: bold; margin: 8px 0; font-size: 16px; }
.tool-desc { font-size: 12px; color: #909399; margin-bottom: 8px; }
.tool-meta { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 10px; }
.version { font-size: 12px; color: #c0c4cc; }
.tool-btn { width: 100%; }
</style>
