<template>
  <div class="page-container">
    <h2 class="page-title">长期记忆</h2>
    <div class="memory-layout">
      <div class="memory-main">
        <div class="filter-bar">
          <el-input v-model="searchQuery" placeholder="搜索记忆条目" clearable @keydown.enter="searchMemory">
            <template #append><el-button @click="searchMemory">搜索</el-button></template>
          </el-input>
          <el-select v-model="filterType" placeholder="类型" clearable style="width:120px" @change="onFilterChange">
            <el-option label="全部" value="" />
            <el-option label="对话" value="conversation" />
            <el-option label="客户" value="customer" />
            <el-option label="任务" value="task" />
            <el-option label="知识" value="knowledge" />
          </el-select>
        </div>
        <el-table v-loading="loading" :data="memories" stripe style="margin-top:16px">
          <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ typeLabel(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="170" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" type="danger" plain @click="deleteMemory(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!memories.length && !loading" description="暂无记忆条目" />
        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[20, 50, 100]"
            layout="total, sizes, prev, pager, next"
            @change="loadMemories"
          />
        </div>
      </div>
      <div class="memory-sidebar">
        <div class="stats-title">记忆统计</div>
        <div class="stats-item"><span>总条目数</span><span class="stats-value">{{ stats.total }}</span></div>
        <div class="stats-item"><span>对话记忆</span><span class="stats-value">{{ stats.conversation }}</span></div>
        <div class="stats-item"><span>客户记忆</span><span class="stats-value">{{ stats.customer }}</span></div>
        <div class="stats-item"><span>任务记忆</span><span class="stats-value">{{ stats.task }}</span></div>
        <div class="stats-item"><span>知识记忆</span><span class="stats-value">{{ stats.knowledge }}</span></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const searchQuery = ref('')
const filterType = ref('')
const memories = ref([])
const stats = ref({ total: 0, conversation: 0, customer: 0, task: 0, knowledge: 0 })
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

function typeLabel(t) {
  return { conversation: '对话', customer: '客户', task: '任务', knowledge: '知识' }[t] || t
}

function updateStats(data) {
  if (data.stats) {
    stats.value = data.stats
  } else {
    stats.value = {
      total: data.total || 0,
      conversation: 0,
      customer: 0,
      task: 0,
      knowledge: 0,
    }
  }
}

async function loadMemories() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/memory/list', {
      params: {
        type: filterType.value || undefined,
        limit: pageSize.value,
        offset: (page.value - 1) * pageSize.value,
      },
    })
    memories.value = data.items || []
    total.value = data.total || data.items?.length || 0
    updateStats(data)
  } catch (e) {
    ElMessage.error('加载记忆失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function searchMemory() {
  const q = searchQuery.value.trim()
  if (!q) {
    page.value = 1
    loadMemories()
    return
  }
  loading.value = true
  try {
    const { data } = await axios.get('/api/memory/search', { params: { q, limit: 100 } })
    memories.value = data.items || []
    total.value = data.items?.length || 0
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function deleteMemory(row) {
  try {
    await ElMessageBox.confirm('确定删除这条记忆？', '确认删除', { type: 'warning' })
    await axios.delete(`/api/memory/${row.id}`)
    ElMessage.success('已删除')
    await loadMemories()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

function onFilterChange() {
  page.value = 1
  loadMemories()
}

watch(pageSize, () => {
  page.value = 1
  loadMemories()
})

onMounted(() => loadMemories())
</script>

<style scoped>
.page-container { padding: 24px; }
.page-title { margin: 0 0 20px; font-size: 18px; }
.memory-layout { display: flex; gap: 16px; }
.memory-main { flex: 1; }
.memory-sidebar { width: 220px; flex-shrink: 0; }
.filter-bar { display: flex; gap: 12px; }
.stats-title { font-size: 13px; font-weight: 600; margin-bottom: 12px; }
.stats-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color); font-size: 13px; }
.stats-value { font-weight: 600; color: var(--accent); }
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
