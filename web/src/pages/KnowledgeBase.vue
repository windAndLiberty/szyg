<template>
  <div class="page-placeholder">
    <h2 class="page-title">知识管理</h2>
    <div class="kb-layout">
      <div class="kb-main">
        <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
          <el-tab-pane label="知识列表" name="list">
            <el-table v-loading="loading" :data="documents" stripe>
              <el-table-column prop="filename" label="文件名" min-width="200" />
              <el-table-column prop="source" label="来源" width="120" />
              <el-table-column prop="chunks" label="分块数" width="90" />
              <el-table-column label="状态" width="140">
                <template #default="{ row }">
                  <el-tag v-if="row.status === 'ready'" type="success" size="small">已完成</el-tag>
                  <el-tag v-else-if="row.status === 'processing'" type="warning" size="small">处理中</el-tag>
                  <el-tag v-else type="danger" size="small">失败</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="ingestedAt" label="摄入时间" width="170" />
              <el-table-column label="操作" width="100">
                <template #default="{ row }">
                  <el-button size="small" type="danger" plain @click="deleteDocument(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="文档摄入" name="ingest">
            <el-upload
              drag
              :auto-upload="false"
              :on-change="onFileChange"
              :limit="1"
              accept=".txt,.md,.json,.pdf,.docx"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">拖拽文件到此处或<em>点击上传</em></div>
              <template #tip>
                <div class="el-upload__tip">支持 txt / md / json / pdf / docx 格式</div>
              </template>
            </el-upload>
            <div v-if="uploadProgress > 0 && uploadProgress < 100" style="margin-top: 12px">
              <el-progress :percentage="uploadProgress" />
            </div>
            <el-button type="primary" @click="ingestDocument" :loading="ingesting" :disabled="!selectedFile" style="margin-top: 16px">开始摄入</el-button>
          </el-tab-pane>
          <el-tab-pane label="知识搜索" name="search">
            <el-input v-model="searchQuery" placeholder="输入搜索关键词" @keydown.enter="searchKnowledge">
              <template #append><el-button @click="searchKnowledge">搜索</el-button></template>
            </el-input>
            <div class="search-results">
              <el-card v-for="r in searchResults" :key="r.id || r.content" shadow="hover" class="result-card">
                <div class="result-content">{{ r.content }}</div>
                <div class="result-meta">来源: {{ r.source }} | 相似度: {{ formatScore(r.score) }}</div>
              </el-card>
              <el-empty v-if="!searchResults.length && searched" description="无搜索结果" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      <div class="kb-sidebar">
        <div class="stats-title">知识库统计</div>
        <div class="stats-item"><span>总文档数</span><span class="stats-value">{{ stats.totalDocs }}</span></div>
        <div class="stats-item"><span>总分块数</span><span class="stats-value">{{ stats.totalChunks }}</span></div>
        <div class="stats-item"><span>最近更新</span><span class="stats-value">{{ stats.lastUpdate }}</span></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const activeTab = ref('list')
const documents = ref([])
const loading = ref(false)
const searchQuery = ref('')
const searchResults = ref([])
const searched = ref(false)
const ingesting = ref(false)
const selectedFile = ref(null)
const uploadProgress = ref(0)
const stats = ref({ totalDocs: 0, totalChunks: 0, lastUpdate: '—' })
const pollIntervals = ref([])

function onFileChange(file) {
  selectedFile.value = file.raw
  uploadProgress.value = 0
}

function formatScore(score) {
  if (score === undefined || score === null) return '—'
  const num = Number(score)
  if (Number.isNaN(num)) return score
  return num.toFixed(2)
}

async function loadDocuments() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/knowledge/documents')
    documents.value = data.items || []
  } catch (e) {
    ElMessage.error('加载文档失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const { data } = await axios.get('/api/knowledge/stats')
    stats.value = {
      totalDocs: data.totalDocs || 0,
      totalChunks: data.totalChunks || 0,
      lastUpdate: data.lastUpdate || '—',
    }
  } catch (e) {
    ElMessage.error('加载统计失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function ingestDocument() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  ingesting.value = true
  uploadProgress.value = 0
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const { data } = await axios.post('/api/knowledge/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total) {
          uploadProgress.value = Math.round((e.loaded / e.total) * 100)
        }
      },
    })
    ElMessage.success('文档上传成功，正在解析...')
    if (data.taskId) {
      pollTask(data.taskId)
    } else {
      await loadDocuments()
      await loadStats()
    }
    selectedFile.value = null
  } catch (e) {
    ElMessage.error('摄入失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    ingesting.value = false
  }
}

function pollTask(taskId) {
  const interval = setInterval(async () => {
    try {
      const { data } = await axios.get(`/api/knowledge/tasks/${taskId}`)
      if (data.status === 'ready' || data.status === 'failed') {
        clearInterval(interval)
        pollIntervals.value = pollIntervals.value.filter(i => i !== interval)
        if (data.status === 'ready') {
          ElMessage.success('文档解析完成')
        } else {
          ElMessage.error('文档解析失败')
        }
        await loadDocuments()
        await loadStats()
      }
    } catch (e) {
      clearInterval(interval)
      pollIntervals.value = pollIntervals.value.filter(i => i !== interval)
    }
  }, 2000)
  pollIntervals.value.push(interval)
}

async function deleteDocument(row) {
  try {
    await ElMessageBox.confirm('确定删除该文档及其所有知识分块？', '确认删除', { type: 'warning' })
    await axios.delete(`/api/knowledge/documents/${row.id}`)
    ElMessage.success('已删除')
    await loadDocuments()
    await loadStats()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

async function searchKnowledge() {
  const q = searchQuery.value.trim()
  if (!q) return
  searched.value = true
  searchResults.value = []
  try {
    const { data } = await axios.get('/api/knowledge/search', { params: { q, top_k: 10 } })
    searchResults.value = data.results || []
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadDocuments()
  loadStats()
})

onUnmounted(() => {
  pollIntervals.value.forEach(clearInterval)
  pollIntervals.value = []
})
</script>

<style scoped>
.page-placeholder { padding: 0; }
.page-title { margin: 0 0 16px; font-size: 18px; }
.kb-layout { display: flex; gap: 16px; }
.kb-main { flex: 1; }
.studio-tabs { border-radius: 8px; }
.kb-sidebar { width: 220px; flex-shrink: 0; }
.stats-title { font-size: 13px; font-weight: 600; margin-bottom: 12px; }
.stats-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color); font-size: 13px; }
.stats-value { font-weight: 600; color: var(--accent); }
.search-results { margin-top: 16px; display: flex; flex-direction: column; gap: 12px; }
.result-card { cursor: pointer; }
.result-content { font-size: 13px; line-height: 1.6; margin-bottom: 8px; }
.result-meta { font-size: 11px; color: var(--text-tertiary); }
</style>
