<template>
  <div class="settings-system-page">
    <!-- Page Header -->
    <div class="page-header">
      <h2 class="page-title">系统配置</h2>
      <p class="page-subtitle">企业全局系统与 API 配置</p>
    </div>

    <el-form
      :model="form"
      label-width="140px"
      class="system-form"
      @submit.prevent
    >
      <!-- API 配置 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Connection /></el-icon>
            <span>API 配置</span>
          </div>
        </template>

        <el-form-item label="LLM API 端点">
          <el-input
            v-model="form.apiEndpoint"
            placeholder="https://ark.cn-beijing.volces.com/api/v3"
          />
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="form.apiKey"
            type="password"
            show-password
            placeholder="输入 API Key"
          />
        </el-form-item>

        <el-form-item label="默认模型">
          <el-select v-model="form.defaultModel" placeholder="选择模型" style="width: 100%">
            <el-option
              v-for="m in modelOptions"
              :key="m"
              :label="m"
              :value="m"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="超时时间 (秒)">
          <el-input-number v-model="form.timeout" :min="5" :max="300" :step="5" />
        </el-form-item>
      </el-card>

      <!-- 模型参数 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><SetUp /></el-icon>
            <span>模型参数</span>
          </div>
        </template>

        <el-form-item label="温度 (Temperature)">
          <div class="slider-row">
            <el-slider v-model="form.temperature" :min="0" :max="2" :step="0.1" style="flex: 1" />
            <span class="slider-value">{{ form.temperature }}</span>
          </div>
        </el-form-item>

        <el-form-item label="最大 Token">
          <el-input-number v-model="form.maxTokens" :min="256" :max="8192" :step="256" />
        </el-form-item>

        <el-form-item label="Top P">
          <div class="slider-row">
            <el-slider v-model="form.topP" :min="0" :max="1" :step="0.05" style="flex: 1" />
            <span class="slider-value">{{ form.topP }}</span>
          </div>
        </el-form-item>

        <el-form-item label="重试次数">
          <el-input-number v-model="form.retries" :min="0" :max="10" />
        </el-form-item>
      </el-card>

      <!-- 平台配置 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Platform /></el-icon>
            <span>平台配置</span>
          </div>
        </template>

        <el-form-item label="默认发布平台">
          <el-checkbox-group v-model="form.platforms">
            <el-checkbox label="douyin">抖音</el-checkbox>
            <el-checkbox label="xiaohongshu">小红书</el-checkbox>
            <el-checkbox label="bilibili">B 站</el-checkbox>
            <el-checkbox label="kuaishou">快手</el-checkbox>
            <el-checkbox label="wechat">微信</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="评论策略">
          <el-radio-group v-model="form.commentStrategy">
            <el-radio-button label="cautious">谨慎</el-radio-button>
            <el-radio-button label="balanced">均衡</el-radio-button>
            <el-radio-button label="fast">快速</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="并发限制">
          <el-input-number v-model="form.concurrencyLimit" :min="1" :max="50" />
        </el-form-item>
      </el-card>

      <!-- 安全设置 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Lock /></el-icon>
            <span>安全设置</span>
          </div>
        </template>

        <el-form-item label="违禁词检测">
          <el-switch v-model="form.enableBadWordCheck" />
        </el-form-item>

        <el-form-item label="DeAI 预处理">
          <el-switch v-model="form.enableDeAiPreprocess" />
        </el-form-item>

        <el-form-item label="自动备份间隔">
          <el-select v-model="form.backupInterval" placeholder="选择备份频率" style="width: 200px">
            <el-option label="每小时" value="hourly" />
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="关闭" value="off" />
          </el-select>
        </el-form-item>
      </el-card>

      <!-- 向量嵌入配置 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Collection /></el-icon>
            <span>向量嵌入配置</span>
          </div>
        </template>

        <el-form-item label="嵌入模型端点">
          <el-input
            v-model="form.embeddingEndpoint"
            placeholder="https://ark.cn-beijing.volces.com/api/v3/embeddings"
          />
        </el-form-item>

        <el-form-item label="嵌入模型 ID">
          <el-input
            v-model="form.embeddingModel"
            placeholder="doubao-embedding"
          />
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="form.embeddingApiKey"
            type="password"
            show-password
            placeholder="输入向量嵌入 API Key"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="向量维度">
              <el-input-number v-model="form.dimensions" :min="128" :max="4096" :step="128" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="批次大小">
              <el-input-number v-model="form.batchSize" :min="1" :max="64" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="索引类型">
          <el-radio-group v-model="form.indexType">
            <el-radio-button label="vector">纯向量</el-radio-button>
            <el-radio-button label="fts5">FTS5 全文</el-radio-button>
            <el-radio-button label="hybrid">混合检索</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="相似度阈值">
          <div class="slider-row">
            <el-slider v-model="form.similarityThreshold" :min="0" :max="1" :step="0.05" style="flex: 1" />
            <span class="slider-value">{{ form.similarityThreshold.toFixed(2) }}</span>
          </div>
        </el-form-item>

        <el-form-item label="最大检索结果数">
          <el-input-number v-model="form.maxResults" :min="1" :max="20" />
        </el-form-item>
      </el-card>

      <!-- RAG 配置 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><DocumentCopy /></el-icon>
            <span>RAG 配置</span>
          </div>
        </template>

        <el-form-item label="启用 RAG 增强">
          <el-switch v-model="form.ragEnabled" />
        </el-form-item>

        <el-form-item label="上下文窗口大小">
          <el-input-number v-model="form.contextWindow" :min="1" :max="10" />
        </el-form-item>

        <el-form-item label="重排序启用">
          <el-switch v-model="form.rerankEnabled" />
        </el-form-item>
      </el-card>

      <!-- 知识库同步 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><RefreshRight /></el-icon>
            <span>知识库同步</span>
          </div>
        </template>

        <el-form-item>
          <el-button type="primary" @click="reindex" :loading="kbStats.indexing">
            <el-icon><RefreshRight /></el-icon> 立即重新索引
          </el-button>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="上次索引时间">
              <span class="readonly-text">{{ kbStats.lastIndexed }}</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="索引文档数">
              <span class="readonly-text">{{ kbStats.docCount }} 篇</span>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="索引状态">
          <el-tag :type="kbStatusType(kbStats.kbStatus)" size="small">
            {{ kbStatusText(kbStats.kbStatus) }}
          </el-tag>
        </el-form-item>
      </el-card>

      <!-- Actions -->
      <div class="form-actions">
        <el-button type="primary" size="large" @click="saveConfig">
          <el-icon><Check /></el-icon> 保存配置
        </el-button>
        <el-button size="large" @click="resetDefault">
          <el-icon><RefreshLeft /></el-icon> 恢复默认
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import {
  Connection, SetUp, Platform, Lock, Check, RefreshLeft, Collection, DocumentCopy, RefreshRight
} from '@element-plus/icons-vue'

// Model options
const modelOptions = [
  'doubao-seed-2-0-pro-260215',
  'doubao-seed-2-0-lite-260428',
  'doubao-seed-2-0-mini-260428',
  'doubao-seed-2-0-code-preview-260215',
  'doubao-seed-1-6-251015',
  'doubao-seed-1-6-flash-250828',
  'doubao-seed-1-6-vision-250815',
  'doubao-1-5-pro-32k-250115',
  'doubao-1-5-lite-32k-250115',
  'doubao-1-5-vision-pro-32k-250115',
  'deepseek-v4-flash-260425',
]

// ── Load persisted config from localStorage ──
const STORAGE_KEY = 'szyg_system_config'
function loadPersistedConfig() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

const defaultForm = {
  apiEndpoint: 'https://ark.cn-beijing.volces.com/api/v3',
  apiKey: '',
  defaultModel: 'doubao-seed-2-0-pro-260215',
  timeout: 30,
  temperature: 0.7,
  maxTokens: 4096,
  topP: 0.9,
  retries: 3,
  platforms: ['douyin', 'xiaohongshu', 'bilibili'],
  commentStrategy: 'balanced',
  concurrencyLimit: 10,
  enableBadWordCheck: true,
  enableDeAiPreprocess: false,
  backupInterval: 'daily',
  // 向量嵌入配置
  embeddingEndpoint: 'https://ark.cn-beijing.volces.com/api/v3/embeddings',
  embeddingModel: 'doubao-embedding',
  embeddingApiKey: '',
  dimensions: 1024,
  batchSize: 16,
  indexType: 'hybrid',
  similarityThreshold: 0.75,
  maxResults: 5,
  // RAG 配置
  ragEnabled: true,
  contextWindow: 3,
  rerankEnabled: false,
}

const form = reactive({ ...defaultForm, ...loadPersistedConfig() })

// ── 知识库状态（从真实 API 加载） ──
const kbStats = reactive({
  lastIndexed: '—',
  docCount: 0,
  kbStatus: 'loading',
  indexing: false,
})

async function loadKbStats() {
  try {
    const { data } = await axios.get('/api/data/knowledge_docs/list')
    const docs = data?.data || data || []
    kbStats.docCount = Array.isArray(docs) ? docs.length : 0
    // Find latest updated_at
    let latest = null
    if (Array.isArray(docs)) {
      for (const d of docs) {
        const t = d.updated_at || d.created_at
        if (t && (!latest || t > latest)) latest = t
      }
    }
    kbStats.lastIndexed = latest || '—'
    kbStats.kbStatus = 'ready'
  } catch {
    kbStats.kbStatus = 'error'
  }
}

onMounted(() => {
  loadKbStats()
})

function saveConfig() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      apiEndpoint: form.apiEndpoint,
      apiKey: form.apiKey,
      defaultModel: form.defaultModel,
      timeout: form.timeout,
      temperature: form.temperature,
      maxTokens: form.maxTokens,
      topP: form.topP,
      retries: form.retries,
      platforms: form.platforms,
      commentStrategy: form.commentStrategy,
      concurrencyLimit: form.concurrencyLimit,
      enableBadWordCheck: form.enableBadWordCheck,
      enableDeAiPreprocess: form.enableDeAiPreprocess,
      backupInterval: form.backupInterval,
      embeddingEndpoint: form.embeddingEndpoint,
      embeddingModel: form.embeddingModel,
      embeddingApiKey: form.embeddingApiKey,
      dimensions: form.dimensions,
      batchSize: form.batchSize,
      indexType: form.indexType,
      similarityThreshold: form.similarityThreshold,
      maxResults: form.maxResults,
      ragEnabled: form.ragEnabled,
      contextWindow: form.contextWindow,
      rerankEnabled: form.rerankEnabled,
    }))
    ElMessage.success('配置已保存到本地')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.message || '未知错误'))
  }
}

function resetDefault() {
  Object.assign(form, defaultForm)
  ElMessage.info('已恢复默认配置')
}

async function reindex() {
  kbStats.indexing = true
  kbStats.kbStatus = 'indexing'
  try {
    // Reindex all knowledge docs
    const { data } = await axios.get('/api/data/knowledge_docs/list')
    const docs = data?.data || data || []
    if (Array.isArray(docs) && docs.length > 0) {
      for (const doc of docs) {
        try { await axios.put(`/api/data/knowledge_docs/${doc.id}/reindex`) } catch {}
      }
    }
    kbStats.kbStatus = 'ready'
    kbStats.lastIndexed = new Date().toISOString().replace('T', ' ').slice(0, 16)
    ElMessage.success(`已重新索引 ${docs.length} 篇文档`)
  } catch (e) {
    kbStats.kbStatus = 'error'
    ElMessage.error('重新索引失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    kbStats.indexing = false
  }
}

function kbStatusType(status) {
  const map = { ready: 'success', indexing: 'warning', error: 'danger', loading: 'info' }
  return map[status] || 'info'
}

function kbStatusText(status) {
  const map = { ready: '就绪', indexing: '索引中', error: '错误', loading: '加载中' }
  return map[status] || status
}
</script>

<style scoped>
.settings-system-page {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.system-form :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-weight: 500;
}

.config-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}
.config-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--table-header-bg);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 15px;
}
.card-header .el-icon {
  color: var(--accent-primary);
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-right: 12px;
}
.slider-value {
  min-width: 40px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
  font-weight: 600;
}

.form-actions {
  display: flex;
  gap: 12px;
  padding: 8px 0 24px;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: var(--input-bg) !important;
}
:deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--input-border) inset;
}
:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--input-border-hover) inset;
}
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--input-focus) inset !important;
}

.readonly-text {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}
</style>
