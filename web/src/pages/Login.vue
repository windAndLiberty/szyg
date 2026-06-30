<template>
  <div class="login-page">
    <TechBackground />

    <!-- Ambient orbs -->
    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>

    <!-- Main card -->
    <div class="login-card" :class="{ 'card-visible': mounted }">
      <!-- Brand -->
      <div class="brand">
        <AiMascot />
        <h1 class="brand-name">
          <span class="shimmer-text">{{ systemName }}</span>
        </h1>
        <p class="brand-desc">{{ systemDesc }}</p>
      </div>

      <!-- Form -->
      <el-form :model="form" :rules="rules" ref="formRef" size="large" class="login-form">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名 / 企业账号"
            :prefix-icon="User"
            class="tech-input"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="登录密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
            class="tech-input"
          />
        </el-form-item>

        <div class="form-options">
          <el-checkbox v-model="form.remember" class="remember-check">
            <span class="remember-label">记住密码</span>
          </el-checkbox>
          <a class="forgot-link" @click="onForgot">忘记密码?</a>
        </div>

        <el-form-item class="submit-item">
          <el-button
            type="primary"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            <span class="btn-content">
              <span v-if="!loading" class="btn-icon">→</span>
              <span>{{ loading ? '安全校验中…' : '进入系统' }}</span>
            </span>
          </el-button>
        </el-form-item>
      </el-form>

      <!-- Trust badges -->
      <div class="trust-bar">
        <div class="trust-item">
          <span class="trust-dot green"></span>
          <span class="trust-text">SSL 加密传输</span>
        </div>
        <div class="trust-divider"></div>
        <div class="trust-item">
          <span class="trust-dot blue"></span>
          <span class="trust-text">企业级隔离</span>
        </div>
        <div class="trust-divider"></div>
        <div class="trust-item">
          <span class="trust-dot cyan"></span>
          <span class="trust-text">SOC2 合规</span>
        </div>
      </div>
    </div>

    <!-- Footer info -->
    <div class="login-footer" :class="{ 'footer-visible': mounted }">
      <span class="version">v2.4.0 Enterprise</span>
      <span class="footer-divider">·</span>
      <span class="copyright">{{ copyright }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import axios from 'axios'
import TechBackground from '../components/TechBackground.vue'
import AiMascot from '../components/AiMascot.vue'

const router = useRouter()
const route = useRoute()
const formRef = ref(null)
const loading = ref(false)
const mounted = ref(false)

const systemName = ref('智能矩阵运营系统')
const systemDesc = ref('企业级 AI 中台 · 安全可信 · 实时协同')
const copyright = ref('© 2024 szyg')

const form = reactive({ username: '', password: '', remember: true })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(async () => {
  // Staggered entrance
  setTimeout(() => { mounted.value = true }, 50)

  // Dev mode: auto-fill credentials from URL query
  if (route.query.dev === '1' && route.query.username) {
    form.username = route.query.username
    form.password = route.query.password || ''
    form.remember = true
  }

  try {
    const { data } = await axios.get('/api/oem/config/default')
    if (data.name) systemName.value = data.name
    if (data.copyright) copyright.value = data.copyright
  } catch (_) {}

  const saved = localStorage.getItem('saved_credentials')
  if (saved && !form.username) {
    const creds = JSON.parse(saved)
    form.username = creds.username
    form.password = creds.password
    form.remember = true
  }
})

function onForgot() {
  ElMessage.info('请联系管理员重置密码')
}

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
    router.push('/chat')
  } catch (e) {
    const msg = e.response?.status === 401 ? '用户名或密码错误' : '服务器连接失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ── Page Layout ── */
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--bg-canvas);
  z-index: 1;
}

/* ── Ambient Orbs ── */
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  z-index: 0;
  opacity: 0;
  animation: orbFadeIn 1.2s var(--ease-out-expo) 0.4s forwards;
}
.orb-1 {
  width: 500px; height: 500px;
  top: -10%; left: -5%;
  background: var(--orb-1);
  animation: orbFloat 12s ease-in-out infinite, orbFadeIn 1.2s var(--ease-out-expo) 0.4s forwards;
}
.orb-2 {
  width: 400px; height: 400px;
  bottom: -5%; right: -5%;
  background: var(--orb-2);
  animation: orbFloat 14s ease-in-out infinite 2s, orbFadeIn 1.2s var(--ease-out-expo) 0.6s forwards;
}
.orb-3 {
  width: 300px; height: 300px;
  top: 40%; left: 60%;
  background: var(--orb-3);
  animation: orbFloat 10s ease-in-out infinite 1s, orbFadeIn 1.2s var(--ease-out-expo) 0.8s forwards;
}

@keyframes orbFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes orbFloat {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(2%, -3%); }
  66% { transform: translate(-1%, 2%); }
}

/* ── Login Card ── */
.login-card {
  position: relative;
  z-index: 2;
  width: 420px;
  max-width: 92vw;
  padding: 44px 40px 36px;
  background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-xl);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    0 0 0 1px rgba(255, 255, 255, 0.03) inset,
    0 0 80px rgba(34, 211, 238, 0.04);
  opacity: 0;
  transform: translateY(24px) scale(0.97);
  transition: opacity 0.7s var(--ease-out-expo), transform 0.7s var(--ease-out-expo);
}

.login-card.card-visible {
  opacity: 1;
  transform: translateY(0) scale(1);
}

/* Subtle top light line */
.login-card::before {
  content: '';
  position: absolute;
  top: 0; left: 10%; right: 10%; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(34, 211, 238, 0.3), transparent);
  border-radius: 1px;
}

/* ── Brand ── */
.brand {
  text-align: center;
  margin-bottom: 28px;
}



.brand-name {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 8px;
  letter-spacing: 0.5px;
}

.shimmer-text {
  background: linear-gradient(
    90deg,
    var(--text-primary) 0%,
    var(--cyan-400) 25%,
    var(--blue-500) 50%,
    var(--cyan-400) 75%,
    var(--text-primary) 100%
  );
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: shimmer 5s linear infinite;
}

@keyframes shimmer {
  0% { background-position: 200% center; }
  100% { background-position: -200% center; }
}

.brand-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
  letter-spacing: 1px;
}

/* ── Form ── */
.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.tech-input :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.03) !important;
  border: 1px solid rgba(255, 255, 255, 0.06) !important;
  box-shadow: none !important;
  border-radius: var(--radius-md) !important;
  padding: 4px 14px;
  transition: all var(--duration-normal) var(--ease-out-expo);
}
.tech-input :deep(.el-input__wrapper:hover) {
  background: rgba(255, 255, 255, 0.05) !important;
  border-color: rgba(255, 255, 255, 0.1) !important;
}
.tech-input :deep(.el-input__wrapper.is-focus) {
  background: rgba(255, 255, 255, 0.04) !important;
  border-color: var(--accent-primary) !important;
  box-shadow: 0 0 0 3px rgba(34, 211, 238, 0.08), 0 0 20px rgba(34, 211, 238, 0.06) !important;
}
.tech-input :deep(.el-input__inner) {
  height: 44px;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.3px;
}
.tech-input :deep(.el-input__icon) {
  color: var(--text-tertiary);
  font-size: 16px;
}

/* Options row */
.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: -4px 0 20px;
}

.remember-check :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background: var(--accent-primary) !important;
  border-color: var(--accent-primary) !important;
}
.remember-check :deep(.el-checkbox__inner) {
  background: rgba(255,255,255,0.05);
  border-color: rgba(255,255,255,0.1);
}
.remember-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.forgot-link {
  font-size: 13px;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: color var(--duration-fast) ease;
}
.forgot-link:hover {
  color: var(--accent-primary);
}

/* Submit button */
.submit-item { margin-bottom: 0 !important; }

.login-btn {
  width: 100%;
  height: 48px !important;
  font-size: 15px !important;
  border-radius: var(--radius-md) !important;
}
.login-btn :deep(.el-button__content) {
  font-weight: 600;
  letter-spacing: 0.5px;
}

.btn-content {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  position: relative;
  z-index: 1;
}
.btn-icon {
  font-size: 18px;
  transition: transform var(--duration-fast) var(--ease-out-expo);
}
.login-btn:hover .btn-icon {
  transform: translateX(3px);
}

/* ── Trust Bar ── */
.trust-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.trust-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.trust-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  position: relative;
}
.trust-dot::after {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  opacity: 0.4;
  animation: trustPulse 2.5s ease-in-out infinite;
}
.trust-dot.green { background: var(--emerald-500); box-shadow: 0 0 6px var(--emerald-500); }
.trust-dot.green::after { background: var(--emerald-500); }
.trust-dot.blue { background: var(--blue-500); box-shadow: 0 0 6px var(--blue-500); }
.trust-dot.blue::after { background: var(--blue-500); animation-delay: 0.8s; }
.trust-dot.cyan { background: var(--cyan-500); box-shadow: 0 0 6px var(--cyan-500); }
.trust-dot.cyan::after { background: var(--cyan-500); animation-delay: 1.6s; }

@keyframes trustPulse {
  0%, 100% { transform: scale(1); opacity: 0.4; }
  50% { transform: scale(1.8); opacity: 0; }
}

.trust-text {
  font-size: 11px;
  color: var(--text-tertiary);
  letter-spacing: 0.3px;
}

.trust-divider {
  width: 3px; height: 3px;
  border-radius: 50%;
  background: var(--text-muted);
  opacity: 0.4;
}

/* ── Footer ── */
.login-footer {
  position: absolute;
  bottom: 24px;
  left: 0; right: 0;
  text-align: center;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 0.6s var(--ease-out-expo) 0.5s, transform 0.6s var(--ease-out-expo) 0.5s;
}
.login-footer.footer-visible {
  opacity: 1;
  transform: translateY(0);
}

.version {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'Inter', monospace;
  font-variant-numeric: tabular-nums;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.04);
}

.footer-divider {
  color: var(--text-muted);
  font-size: 11px;
  opacity: 0.5;
}

.copyright {
  font-size: 11px;
  color: var(--text-muted);
}

/* ── Responsive ── */
@media (max-width: 480px) {
  .login-card {
    padding: 32px 24px 28px;
    width: 100%;
  }
  .brand-name { font-size: 20px; }
  .trust-bar {
    flex-wrap: wrap;
    gap: 8px 12px;
  }
}
</style>
