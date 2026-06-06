<template>
  <el-card>
    <template #header><h3>AI 视频创作</h3></template>
    <p class="desc">本地 FFmpeg 渲染 — 输入主题自动生成幻灯片视频</p>
    <el-steps :active="step" finish-status="success" simple>
      <el-step title="编写脚本" /><el-step title="渲染视频" /><el-step title="完成" />
    </el-steps>
    <div class="video-control">
      <el-form :model="form" inline @submit.prevent>
        <el-form-item label="主题">
          <el-input v-model="form.theme" placeholder="输入视频主题，分号分隔多页" style="width:400px" />
        </el-form-item>
        <el-form-item label="时长(秒)">
          <el-input-number v-model="form.duration" :min="3" :max="120" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="generating" @click="startPipeline">开始创作</el-button>
        </el-form-item>
      </el-form>
    </div>
    <div v-if="result" class="result">
      <video v-if="result.url" :src="result.url" controls style="max-width:100%;max-height:400px;border-radius:8px" />
      <p class="info">主题: {{ result.theme }} | 时长: {{ result.duration }}s</p>
    </div>
    <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
  </el-card>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const form = reactive({ theme: 'szyg 智能矩阵;AI 赋能创作;本地视频生成', duration: 10 })
const step = ref(0)
const generating = ref(false)
const result = ref(null)
const errorMsg = ref('')

async function startPipeline() {
  if (!form.theme.trim()) return ElMessage.warning('请输入主题')
  generating.value = true
  errorMsg.value = ''
  result.value = null

  try {
    step.value = 1
    ElMessage.info('正在渲染视频...')
    const { data } = await axios.post('/api/video/create', {
      theme: form.theme,
      duration: form.duration,
    })
    step.value = 2
    result.value = data
    ElMessage.success(`视频生成完成: ${data.filename}`)
  } catch (e) {
    step.value = 0
    errorMsg.value = e.response?.data?.detail || e.message || '生成失败'
    ElMessage.error(errorMsg.value)
  } finally {
    generating.value = false
  }
}
</script>

<style scoped>
.desc { color: #909399; margin-bottom: 20px; }
.video-control { margin-top: 20px; }
.result { margin-top: 20px; }
.info { color: #67c23a; margin-top: 8px; font-size: 13px; }
.error { color: #f56c6c; margin-top: 16px; }
</style>
