<template>
    <el-card>
      <template #header><h3>OEM 品牌管理</h3></template>
      <el-form :model="form" label-width="100px">
        <el-form-item label="系统名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="Logo URL"><el-input v-model="form.logo_url" /></el-form-item>
        <el-form-item label="版权信息"><el-input v-model="form.copyright" type="textarea" /></el-form-item>
        <el-form-item label="免责声明"><el-input v-model="form.disclaimer" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="主题皮肤">
          <el-radio-group v-model="form.theme">
            <el-radio-button v-for="t in themes" :key="t.value" :value="t.value">{{ t.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save">保存配置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const themes = [
  { label: '经典蓝', value: 'default' },
  { label: '暗夜', value: 'dark' },
  { label: '自然绿', value: 'green' },
  { label: '日落橙', value: 'sunset' },
  { label: '星空', value: 'starry' },
]
const form = reactive({
  name: 'szyg', logo_url: '', copyright: '© 2024', disclaimer: '', theme: 'default',
})

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/oem/config/default')
    Object.assign(form, data)
  } catch (_) {}
})

async function save() {
  try {
    await axios.post('/api/oem/config', form)
    ElMessage.success('配置已保存')
  } catch (_) { ElMessage.error('保存失败') }
}
</script>
