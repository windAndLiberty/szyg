<template>
    <el-card>
      <template #header><h3>AI 视频创作</h3></template>
      <p class="desc">LLM脚本 + 语音合成 + 视频合成 — 全流程视频制作</p>
      <el-steps :active="step" finish-status="success" simple>
        <el-step title="脚本生成" /><el-step title="语音合成" /><el-step title="视频合成" /><el-step title="完成" />
      </el-steps>
      <div class="video-control">
        <el-form :model="form" inline>
          <el-form-item label="主题"><el-input v-model="form.theme" placeholder="视频主题" /></el-form-item>
          <el-form-item label="时长(秒)"><el-input-number v-model="form.duration" :min="10" :max="300" /></el-form-item>
          <el-form-item><el-button type="primary" @click="startPipeline">开始创作</el-button></el-form-item>
        </el-form>
      </div>
      <div v-if="output" class="output">输出: {{ output }}</div>
    </el-card>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const form = reactive({ theme: '', duration: 60 })
const step = ref(0)
const output = ref('')

function startPipeline() {
  ElMessage.info('视频创作管道启动中...')
  output.value = '正在处理...'
}
</script>

<style scoped>
.desc { color: #909399; margin-bottom: 20px; }
.video-control { margin-top: 20px; }
.output { margin-top: 20px; color: #67c23a; }
</style>
