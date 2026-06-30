<template>
  <div class="settings-brand-page">
    <!-- Page Header -->
    <div class="page-header">
      <h2 class="page-title">
        品牌配置
        <el-tag size="small" type="warning" effect="light">Admin</el-tag>
      </h2>
      <p class="page-subtitle">OEM 品牌自定义与主题设置</p>
    </div>

    <el-form :model="form" label-width="120px" class="brand-form">
      <!-- 基本信息 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><InfoFilled /></el-icon>
            <span>基本信息</span>
          </div>
        </template>

        <el-form-item label="品牌名称">
          <el-input v-model="form.brandName" placeholder="输入品牌名称" />
        </el-form-item>

        <el-form-item label="品牌 Logo">
          <div class="logo-uploader">
            <div class="logo-preview">
              <img v-if="form.logoUrl" :src="form.logoUrl" alt="Logo" />
              <div v-else class="logo-placeholder">
                <el-icon :size="32"><Picture /></el-icon>
                <span>Logo 占位</span>
              </div>
            </div>
            <div class="logo-actions">
              <el-upload
                action="#"
                :auto-upload="false"
                :show-file-list="false"
                :on-change="handleLogoChange"
                accept="image/*"
              >
                <el-button type="primary" plain>
                  <el-icon><Upload /></el-icon> 上传 Logo
                </el-button>
              </el-upload>
              <span class="upload-hint">支持 JPG、PNG、SVG，建议尺寸 256×256</span>
            </div>
          </div>
        </el-form-item>
      </el-card>

      <!-- 主题与配色 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Brush /></el-icon>
            <span>主题与配色</span>
          </div>
        </template>

        <el-form-item label="主题选择">
          <div class="theme-options">
            <div
              v-for="theme in themes"
              :key="theme.value"
              :class="['theme-card', { active: form.theme === theme.value }]"
              @click="form.theme = theme.value"
            >
              <div class="theme-preview" :style="{ background: theme.preview }">
                <el-icon v-if="form.theme === theme.value" class="check-icon"><Check /></el-icon>
              </div>
              <div class="theme-name">{{ theme.label }}</div>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="主色调">
          <el-color-picker v-model="form.primaryColor" show-alpha />
          <span class="color-value">{{ form.primaryColor }}</span>
        </el-form-item>

        <el-form-item label="辅色调">
          <el-color-picker v-model="form.secondaryColor" show-alpha />
          <span class="color-value">{{ form.secondaryColor }}</span>
        </el-form-item>
      </el-card>

      <!-- 版权与法律 -->
      <el-card class="config-card" shadow="never">
        <template #header>
          <div class="card-header">
            <el-icon><Document /></el-icon>
            <span>版权与法律</span>
          </div>
        </template>

        <el-form-item label="版权信息">
          <el-input v-model="form.copyright" placeholder="© 2026 szyg. All rights reserved." />
        </el-form-item>

        <el-form-item label="免责声明">
          <el-input
            v-model="form.disclaimer"
            type="textarea"
            :rows="4"
            placeholder="输入免责声明内容..."
          />
        </el-form-item>

        <el-form-item label="支持链接">
          <el-input v-model="form.supportUrl" placeholder="https://support.example.com" />
        </el-form-item>
      </el-card>

      <!-- Actions -->
      <div class="form-actions">
        <el-button type="primary" size="large" @click="saveBrand">
          <el-icon><Check /></el-icon> 保存品牌配置
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
  InfoFilled, Brush, Document, Check, Picture, Upload
} from '@element-plus/icons-vue'

const themes = [
  { label: '深色', value: 'dark', preview: 'linear-gradient(135deg, #0B0F19, #11182E)' },
  { label: '浅色', value: 'light', preview: 'linear-gradient(135deg, #f4f7f2, #ffffff)' },
  { label: '跟随系统', value: 'system', preview: 'linear-gradient(135deg, #0B0F19 50%, #f4f7f2 50%)' },
]

const form = reactive({
  brandName: 'szyg',
  logoUrl: '',
  theme: 'system',
  primaryColor: '#4f46e5',
  secondaryColor: '#4338ca',
  copyright: '© 2026 szyg. All rights reserved.',
  disclaimer: '本系统生成的内容仅供参考，请人工复核后使用。',
  supportUrl: 'https://support.szyg.ai',
})

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/oem/config/default')
    form.brandName = data.name || form.brandName
    form.logoUrl = data.logo_url || form.logoUrl
    form.theme = data.theme || form.theme
    form.copyright = data.copyright || form.copyright
    form.disclaimer = data.disclaimer || form.disclaimer
    form.supportUrl = data.support_url || form.supportUrl
  } catch (_) {
    // 使用默认值
  }
})

function handleLogoChange(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    form.logoUrl = e.target.result
    ElMessage.success('Logo 预览已加载')
  }
  reader.readAsDataURL(file.raw)
}

async function saveBrand() {
  try {
    await axios.post('/api/oem/config', {
      name: form.brandName,
      logo_url: form.logoUrl,
      theme: form.theme,
      copyright: form.copyright,
      disclaimer: form.disclaimer,
      support_url: form.supportUrl,
    })
    ElMessage.success('品牌配置已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}
</script>

<style scoped>
.settings-brand-page {
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
  display: flex;
  align-items: center;
  gap: 8px;
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.brand-form :deep(.el-form-item__label) {
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

/* Logo Uploader */
.logo-uploader {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}
.logo-preview {
  width: 100px;
  height: 100px;
  border-radius: var(--radius-md);
  border: 2px dashed var(--border-color);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--bg-canvas);
  transition: border-color 0.2s;
}
.logo-preview:hover {
  border-color: var(--accent-primary);
}
.logo-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 8px;
}
.logo-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
}
.logo-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.upload-hint {
  font-size: 12px;
  color: var(--text-muted);
}

/* Theme Options */
.theme-options {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.theme-card {
  width: 120px;
  cursor: pointer;
  border-radius: var(--radius-md);
  border: 2px solid var(--border-color);
  overflow: hidden;
  transition: border-color 0.2s, transform 0.2s;
  background: var(--card-bg);
}
.theme-card:hover {
  border-color: var(--border-active);
  transform: translateY(-2px);
}
.theme-card.active {
  border-color: var(--accent-primary);
  box-shadow: var(--accent-glow-sm);
}
.theme-preview {
  height: 64px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}
.check-icon {
  color: var(--accent-primary);
  font-weight: bold;
  font-size: 20px;
  background: var(--card-bg);
  border-radius: 50%;
  padding: 2px;
}
.theme-name {
  text-align: center;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

/* Color */
.color-value {
  margin-left: 10px;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 13px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* Actions */
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
</style>
