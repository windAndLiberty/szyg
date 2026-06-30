<template>
  <div class="page-placeholder">
    <h2 class="page-title">数字人</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <el-tab-pane label="形象管理" name="avatar">
        <div class="placeholder-content">
          <el-upload drag :auto-upload="false" accept="video/*">
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">上传人物形象视频进行克隆</div>
          </el-upload>
          <el-empty description="暂无已克隆形象" />
        </div>
      </el-tab-pane>
      <el-tab-pane label="音色管理" name="voice">
        <div class="placeholder-content">
          <el-upload drag :auto-upload="false" accept="audio/*">
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">上传MP3音频进行声音克隆</div>
          </el-upload>
          <el-empty description="暂无已克隆音色" />
        </div>
      </el-tab-pane>
      <el-tab-pane label="视频合成" name="synthesis">
        <div class="placeholder-content">
          <el-form label-width="100px" class="param-form">
            <el-form-item label="选择形象"><el-select placeholder="选择已克隆形象" /></el-form-item>
            <el-form-item label="选择音色"><el-select placeholder="选择已克隆音色" /></el-form-item>
            <el-form-item label="合成文案"><el-input type="textarea" :rows="4" placeholder="输入文案内容" /></el-form-item>
            <el-form-item label="合成模式">
              <el-radio-group>
                <el-radio value="single">1+1模式（一个形象+一个文案）</el-radio>
                <el-radio value="mixed">混合模式（多形象×多文案）</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item><el-button type="primary">开始合成</el-button></el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
      <el-tab-pane label="作品列表" name="works">
        <el-empty description="暂无合成作品" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
const activeTab = ref('avatar')
</script>

<style scoped>
.page-placeholder { padding: 0; }
.page-title { margin: 0 0 16px; font-size: 18px; }
.studio-tabs { border-radius: 8px; }
.placeholder-content { padding: 24px; max-width: 600px; }
.param-form { margin-top: 20px; }
</style>
