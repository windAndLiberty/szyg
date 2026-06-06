<template>
    <el-card>
      <template #header><h3>AI 图像生成</h3></template>
      <el-form :model="form" label-width="80px">
        <el-form-item label="提示词">
          <el-input v-model="form.prompt" type="textarea" :rows="3" placeholder="描述你想生成的图像..." />
        </el-form-item>
        <el-form-item label="风格">
          <el-select v-model="form.style" placeholder="选择风格">
            <el-option v-for="s in styles" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="generating" @click="generate">生成图像</el-button>
        </el-form-item>
      </el-form>
      <el-image v-if="imageUrl" :src="imageUrl" fit="contain" class="gen-image" />
    </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const form = reactive({ prompt: '', style: '' })
const styles = ref([])
const generating = ref(false)
const imageUrl = ref('')

onMounted(async () => {
  try { const { data } = await axios.get('/api/image/styles'); styles.value = data } catch (_) {}
})

async function generate() {
  generating.value = true
  try {
    const { data } = await axios.post('/api/image/generate', { prompt: form.prompt, style: form.style })
    imageUrl.value = data.image_url || data.image_paths?.[0]
  } catch (e) { ElMessage.error('生成失败') }
  finally { generating.value = false }
}
</script>

<style scoped>
.gen-image { margin-top: 20px; max-width: 100%; max-height: 500px; }
</style>
