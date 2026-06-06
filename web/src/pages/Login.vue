<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>{{ systemName }}</h1>
        <p>{{ systemDesc }}</p>
      </div>
      <el-form :model="form" :rules="rules" ref="formRef" size="large">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.remember">记住密码</el-checkbox>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" class="login-btn" @click="handleLogin">
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footer">
        <span>{{ copyright }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const systemName = ref('智能矩阵运营系统')
const systemDesc = ref('一站式AI工具平台')
const copyright = ref('© 2024 szyg')

const form = reactive({ username: '', password: '', remember: true })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/oem/config/default')
    if (data.name) systemName.value = data.name
    if (data.copyright) copyright.value = data.copyright
  } catch (_) {}

  const saved = localStorage.getItem('saved_credentials')
  if (saved) {
    const creds = JSON.parse(saved)
    form.username = creds.username
    form.password = creds.password
    form.remember = true
  }
})

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const { data } = await axios.post('/api/auth/login', {
      username: form.username,
      password: form.password,
    })
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    if (form.remember) {
      localStorage.setItem('saved_credentials', JSON.stringify({
        username: form.username, password: form.password
      }))
    } else {
      localStorage.removeItem('saved_credentials')
    }
    router.push('/dashboard')
  } catch (e) {
    const msg = e.response?.status === 401 ? '用户名或密码错误' : '服务器连接失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1f25 0%, #2c3e50 100%);
}
html.dark .login-container {
  background: linear-gradient(135deg, #0d1117 0%, #1a1a2e 50%, #16213e 100%);
}

.login-card {
  width: 420px;
  padding: 40px;
  background: rgba(255,255,255,0.95);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  transition: background 0.3s ease;
}
html.dark .login-card {
  background: rgba(30,30,30,0.95);
  box-shadow: 0 8px 32px rgba(0,0,0,0.6);
  border: 1px solid var(--border-color);
}

.login-header { text-align: center; margin-bottom: 30px; }
.login-header h1 {
  font-size: 24px;
  color: #303133;
  margin: 0 0 8px;
  transition: color 0.3s ease;
}
html.dark .login-header h1 { color: #e0e0e0; }

.login-header p {
  color: #909399;
  margin: 0;
  transition: color 0.3s ease;
}
html.dark .login-header p { color: #a0a0a0; }

.login-btn { width: 100%; }
.login-footer {
  text-align: center;
  margin-top: 20px;
  color: #c0c4cc;
  font-size: 12px;
  transition: color 0.3s ease;
}
html.dark .login-footer { color: #666; }
</style>
