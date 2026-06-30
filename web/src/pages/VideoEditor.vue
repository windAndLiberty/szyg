<template>
  <div class="page-placeholder">
    <h2 class="page-title">视频剪辑</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <el-tab-pane label="裁剪拼接" name="cut">
        <div class="placeholder-content">
          <el-upload drag :auto-upload="false" :on-change="onFileChange" accept="video/*">
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽视频到此处或<em>点击上传</em></div>
          </el-upload>
          <el-form :model="cutForm" label-width="100px" class="param-form" v-if="selectedFile">
            <el-form-item label="开始时间">
              <el-input v-model="cutForm.start" placeholder="00:00:00" />
            </el-form-item>
            <el-form-item label="结束时间">
              <el-input v-model="cutForm.end" placeholder="00:00:30" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="executeCut">执行裁剪</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
      <el-tab-pane label="变速" name="speed">
        <div class="placeholder-content">
          <el-form :model="speedForm" label-width="100px" class="param-form">
            <el-form-item label="变速倍率">
              <el-slider v-model="speedForm.speed" :min="0.25" :max="4" :step="0.25" show-input />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="executeSpeed">执行变速</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
      <el-tab-pane label="标题叠加" name="title">
        <div class="placeholder-content">
          <el-form :model="titleForm" label-width="100px" class="param-form">
            <el-form-item label="标题文字">
              <el-input v-model="titleForm.text" placeholder="输入标题文字" />
            </el-form-item>
            <el-form-item label="字体">
              <el-select v-model="titleForm.font" placeholder="选择字体">
                <el-option label="默认黑体" value="simhei" />
                <el-option label="宋体" value="simsun" />
                <el-option label="微软雅黑" value="msyh" />
              </el-select>
            </el-form-item>
            <el-form-item label="位置">
              <el-select v-model="titleForm.position">
                <el-option label="顶部" value="top" />
                <el-option label="中间" value="center" />
                <el-option label="底部" value="bottom" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="executeTitle">添加标题</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
      <el-tab-pane label="音频处理" name="audio">
        <div class="placeholder-content">
          <el-form :model="audioForm" label-width="100px" class="param-form">
            <el-form-item label="操作类型">
              <el-radio-group v-model="audioForm.mode">
                <el-radio value="replace">替换音频</el-radio>
                <el-radio value="mix">混音</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="音频文件">
              <el-upload :auto-upload="false" :on-change="onAudioChange" accept="audio/*">
                <el-button>选择音频</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item label="音量" v-if="audioForm.mode === 'mix'">
              <el-slider v-model="audioForm.volume" :min="0" :max="100" :step="5" show-input />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="executeAudio">执行</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
      <el-tab-pane label="封面提取" name="frame">
        <div class="placeholder-content">
          <el-form :model="frameForm" label-width="100px" class="param-form">
            <el-form-item label="时间点">
              <el-input v-model="frameForm.time" placeholder="00:00:05" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="executeFrame">提取封面</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('cut')
const selectedFile = ref(null)
const cutForm = ref({ start: '', end: '' })
const speedForm = ref({ speed: 1 })
const titleForm = ref({ text: '', font: 'simhei', position: 'bottom' })
const audioForm = ref({ mode: 'replace', volume: 50 })
const frameForm = ref({ time: '' })

function onFileChange(file) { selectedFile.value = file.raw }
function onAudioChange() {}

async function callVideoAPI(endpoint, params) {
  try {
    const formData = new FormData()
    if (selectedFile.value) formData.append('video', selectedFile.value)
    Object.entries(params).forEach(([k, v]) => formData.append(k, v))
    const { data } = await axios.post(`/api/video/${endpoint}`, formData)
    ElMessage.success('操作成功')
    return data
  } catch (e) {
    ElMessage.error(`操作失败: ${e.response?.data?.detail || e.message}`)
  }
}

function executeCut() { callVideoAPI('cut', cutForm.value) }
function executeSpeed() { callVideoAPI('speed', speedForm.value) }
function executeTitle() { callVideoAPI('add-title', titleForm.value) }
function executeAudio() { callVideoAPI(audioForm.value.mode === 'replace' ? 'replace-audio' : 'mix-audio', audioForm.value) }
function executeFrame() { callVideoAPI('extract-frame', frameForm.value) }
</script>

<style scoped>
.page-placeholder { padding: 0; }
.page-title { margin: 0 0 16px; font-size: 18px; }
.studio-tabs { border-radius: 8px; }
.placeholder-content { padding: 24px; max-width: 600px; }
.param-form { margin-top: 20px; }
</style>
