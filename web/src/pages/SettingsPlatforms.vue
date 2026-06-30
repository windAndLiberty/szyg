<template>
  <div class="settings-platforms-page">
    <!-- ═══ Header ═══ -->
    <div class="page-header">
      <h2>平台账号与安全</h2>
    </div>

    <!-- ═══ 安全评分卡片区域 ═══ -->
    <el-row :gutter="20" class="safety-cards-row">
      <el-col :span="8" v-for="card in safetyCards" :key="card.key">
        <div class="safety-card" :class="`safety-${card.status}`">
          <div class="safety-card-body">
            <div class="safety-chart">
              <el-progress
                v-if="card.key !== 'isolation'"
                type="circle"
                :percentage="card.value"
                :color="card.color"
                :stroke-width="10"
                :width="90"
                :show-text="false"
              />
              <div v-else class="isolation-icon" :style="{ color: card.color }">
                <el-icon :size="40">
                  <Lock v-if="card.value === 'good'" />
                  <Warning v-else-if="card.value === 'warning'" />
                  <CircleClose v-else />
                </el-icon>
              </div>
              <div v-if="card.key !== 'isolation'" class="score-overlay">{{ card.value }}</div>
            </div>
            <div class="safety-info">
              <div class="safety-score" :style="{ color: card.color }">
                {{ card.key === 'isolation' ? card.valueText : card.value }}
              </div>
              <div class="safety-label">{{ card.label }}</div>
              <div class="safety-status" :style="{ color: card.color }">
                {{ card.statusText }}
              </div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- ═══ 账号卡片列表 ═══ -->
    <div class="section-header">
      <h3>已绑定平台</h3>
      <span class="section-meta">已登录 {{ loggedInCount }} / {{ platforms.length }} 个平台</span>
    </div>

    <el-row :gutter="16" class="platform-cards-row">
      <el-col :span="8" v-for="p in platforms" :key="p.id">
        <el-card
          :class="['platform-card', p.isLogin ? 'logged-in' : 'logged-out']"
          shadow="hover"
        >
          <!-- 平台图标区域（渐变背景） -->
          <div class="platform-icon-area" :style="{ background: platformGradients[p.id] }">
            <span class="platform-big-icon">{{ p.icon }}</span>
            <div class="platform-icon-overlay">
              <div class="platform-avatar">
                {{ p.account ? p.account.slice(0, 1) : '?' }}
              </div>
              <div class="platform-name-overlay">{{ p.name }}</div>
            </div>
          </div>

          <!-- 卡片内容 -->
          <div class="platform-card-body">
            <div class="platform-meta">
              <div class="meta-top">
                <span class="platform-nickname">{{ p.account || '未登录' }}</span>
                <el-tag
                  :type="p.isLogin ? 'success' : p.safetyScore === 0 ? 'info' : 'danger'"
                  size="small"
                  effect="dark"
                >
                  {{ p.isLogin ? '已登录' : '未登录' }}
                </el-tag>
              </div>
              <div class="meta-time" v-if="p.lastActive">
                <el-icon :size="12"><Clock /></el-icon>
                <span>最后活跃: {{ p.lastActive }}</span>
              </div>
              <div class="meta-time" v-else>
                <span>— 暂无活跃记录 —</span>
              </div>
            </div>

            <!-- 安全评分 -->
            <div class="safety-bar-wrap" v-if="p.isLogin">
              <div class="safety-bar-label">
                <span>安全评分</span>
                <span class="safety-bar-score" :style="{ color: scoreColor(p.safetyScore) }">
                  {{ p.safetyScore }}
                </span>
              </div>
              <el-progress
                :percentage="p.safetyScore"
                :color="scoreColor(p.safetyScore)"
                :stroke-width="6"
                :show-text="false"
                class="safety-bar"
              />
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="platform-actions">
            <template v-if="!p.isLogin">
              <el-button type="primary" size="small" @click="handleBind(p)">
                <el-icon :size="12"><Plus /></el-icon>绑定新账号
              </el-button>
              <el-button size="small" @click="handleScanLogin(p)">
                <el-icon :size="12"><FullScreen /></el-icon>扫码登录
              </el-button>
            </template>
            <template v-else>
              <el-button type="danger" size="small" plain @click="handleUnbind(p)">
                <el-icon :size="12"><Delete /></el-icon>解绑
              </el-button>
              <el-button type="success" size="small" plain @click="handleRefresh(p)">
                <el-icon :size="12"><Refresh /></el-icon>Session 刷新
              </el-button>
            </template>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import {
  Lock,
  Warning,
  CircleClose,
  Clock,
  Plus,
  FullScreen,
  Delete,
  Refresh,
} from '@element-plus/icons-vue'

/* ═══════════════════════════════════════════════════════════════════
   API Data
   ═══════════════════════════════════════════════════════════════════ */
const platforms = ref([])

async function loadPlatforms() {
  try {
    const { data } = await axios.get('/api/platforms')
    const rawPlatforms = data.platforms || []
    platforms.value = rawPlatforms.map(p => ({
      ...p,
      isLogin: p.session?.has_session || false,
      account: p.session?.has_session ? '已登录' : null,
      lastActive: p.session?.last_active || null,
      safetyScore: computeSafetyScore(p.session?.has_session, p.meta?.risk_level),
    }))
  } catch (e) {
    ElMessage.error('加载平台数据失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadPlatforms()
})

const platformGradients = {
  douyin: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
  xhs: 'linear-gradient(135deg, #ff2442 0%, #ff6b6b 100%)',
  bilibili: 'linear-gradient(135deg, #00a1d6 0%, #23ade5 100%)',
  kuaishou: 'linear-gradient(135deg, #ff6600 0%, #ff9900 100%)',
  wechat_mp: 'linear-gradient(135deg, #07c160 0%, #2ae088 100%)',
  wechat: 'linear-gradient(135deg, #07c160 0%, #2ae088 100%)',
}

/* ═══════════════════════════════════════════════════════════════════
   Safety Score Helpers
   ═══════════════════════════════════════════════════════════════════ */
function scoreColor(score) {
  if (score >= 80) return 'var(--green-500)'
  if (score >= 50) return 'var(--amber-500)'
  return 'var(--rose-500)'
}

function scoreStatus(score) {
  if (score >= 80) return '优秀'
  if (score >= 50) return '良好'
  return '需关注'
}

function scoreStatusKey(score) {
  if (score >= 80) return 'good'
  if (score >= 50) return 'warning'
  return 'danger'
}

const RISK_SAFETY_BASE = { high: 60, medium: 75, low: 90, 'n/a': 80 }
function computeSafetyScore(hasSession, riskLevel) {
  if (!hasSession) return 0
  return RISK_SAFETY_BASE[riskLevel] || 80
}

/* ═══════════════════════════════════════════════════════════════════
   Safety Cards — computed from real platform data
   ═══════════════════════════════════════════════════════════════════ */
const loggedInCount = computed(() => platforms.value.filter(p => p.isLogin).length)
const totalPlatforms = computed(() => platforms.value.length)

const platformHealthScore = computed(() => {
  if (!totalPlatforms.value) return 0
  return Math.round((loggedInCount.value / totalPlatforms.value) * 100)
})

const fingerprintScore = computed(() => {
  // 基于平台风控等级计算：低风险平台=高分，高风险平台需要更多指纹对抗
  if (!totalPlatforms.value) return 0
  const riskWeights = { high: 65, medium: 80, low: 95, 'n/a': 85 }
  const total = platforms.value.reduce((sum, p) => {
    const risk = p.meta?.risk_level || 'n/a'
    return sum + (riskWeights[risk] || 85)
  }, 0)
  return Math.round(total / totalPlatforms.value)
})

const isolationStatus = computed(() => {
  if (!totalPlatforms.value) return 'danger'
  const validSessions = platforms.value.filter(p => p.session?.has_session).length
  if (validSessions === 0) return 'danger'
  if (validSessions < totalPlatforms.value) return 'warning'
  return 'good'
})

const safetyCards = computed(() => {
  const fpScore = fingerprintScore.value
  const phScore = platformHealthScore.value
  const isoStatus = isolationStatus.value
  const fpColor = scoreColor(fpScore)
  const phColor = scoreColor(phScore)

  const isoMap = {
    good: { color: 'var(--green-500)', text: '良好', valueText: '已隔离' },
    warning: { color: 'var(--amber-500)', text: '警告', valueText: '需注意' },
    danger: { color: 'var(--rose-500)', text: '危险', valueText: '未隔离' },
  }
  const iso = isoMap[isoStatus]

  return [
    {
      key: 'fingerprint',
      label: '指纹健康度',
      value: fpScore,
      color: fpColor,
      statusText: scoreStatus(fpScore),
      status: scoreStatusKey(fpScore),
    },
    {
      key: 'isolation',
      label: '环境隔离状态',
      value: isoStatus,
      valueText: iso.valueText,
      color: iso.color,
      statusText: iso.text,
      status: isoStatus,
    },
    {
      key: 'platformHealth',
      label: '平台账号健康度',
      value: phScore,
      color: phColor,
      statusText: scoreStatus(phScore),
      status: scoreStatusKey(phScore),
    },
  ]
})

/* ═══════════════════════════════════════════════════════════════════
   Action Handlers
   ═══════════════════════════════════════════════════════════════════ */
async function handleBind(p) {
  try {
    await axios.post(`/api/platforms/${p.id}/login`)
    p.isLogin = true
    p.account = '已登录'
    p.lastActive = new Date().toLocaleString('zh-CN', { hour12: false })
    p.safetyScore = computeSafetyScore(true, p.meta?.risk_level)
    ElMessage.success(`${p.name} 登录已触发，请在浏览器窗口中完成扫码`)
  } catch (e) {
    ElMessage.error('绑定失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function handleScanLogin(p) {
  ElMessage.info(`请在弹出的浏览器窗口中完成 ${p.name} 扫码登录`)
  await handleBind(p)
}

async function handleUnbind(p) {
  try {
    await ElMessageBox.confirm(
      `确定解绑 ${p.name} 账号「${p.account}」？解绑后将无法发布内容到该平台。`,
      '确认解绑',
      { confirmButtonText: '确认解绑', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.delete(`/api/platforms/${p.id}/sessions`)
    p.isLogin = false
    p.account = null
    p.lastActive = null
    p.safetyScore = 0
    ElMessage.success(`已解绑 ${p.name} 账号`)
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('解绑失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

async function handleRefresh(p) {
  try {
    await axios.post(`/api/platforms/${p.id}/login`)
    p.lastActive = new Date().toLocaleString('zh-CN', { hour12: false })
    ElMessage.success(`[${p.name}] Session 已刷新`)
  } catch (e) {
    ElMessage.error('刷新失败: ' + (e.response?.data?.detail || e.message))
  }
}
</script>

<style scoped>
.settings-platforms-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header h2 {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: var(--text-primary);
  font-weight: 600;
}

/* ═══════════════════════════════════════════════════════════════════
   Safety Score Cards
   ═══════════════════════════════════════════════════════════════════ */
.safety-cards-row {
  margin-bottom: 28px;
}

.safety-card {
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  transition: transform var(--duration-fast) ease, box-shadow var(--duration-fast) ease;
  border: 1px solid var(--border-subtle);
  backdrop-filter: blur(8px);
}

.safety-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.safety-card.safety-good {
  background: var(--green-500-10);
}

.safety-card.safety-warning {
  background: var(--amber-400-10);
}

.safety-card.safety-danger {
  background: var(--rose-500-10);
}

.safety-card-body {
  display: flex;
  align-items: center;
  gap: 16px;
}

.safety-chart {
  position: relative;
  width: 90px;
  height: 90px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.isolation-icon {
  width: 90px;
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--card-bg);
  border: 2px solid currentColor;
}

.safety-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.safety-score {
  font-size: 48px;
  font-weight: 700;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.safety-label {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}

.safety-status {
  font-size: 13px;
  font-weight: 600;
}

/* ═══════════════════════════════════════════════════════════════════
   Section Header
   ═══════════════════════════════════════════════════════════════════ */
.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 600;
}

.section-meta {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ═══════════════════════════════════════════════════════════════════
   Platform Cards
   ═══════════════════════════════════════════════════════════════════ */
.platform-cards-row {
  margin-top: 0;
}

.platform-card {
  border-radius: var(--radius-lg);
  transition: transform var(--duration-normal) var(--ease-out-expo),
              box-shadow var(--duration-normal) var(--ease-out-expo);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}

.platform-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg), var(--accent-glow-sm);
}

.platform-card :deep(.el-card__body) {
  padding: 0;
}

/* Logged-in / Logged-out border accent */
.platform-card.logged-in {
  border-top: 3px solid var(--green-500);
}

.platform-card.logged-out {
  border-top: 3px solid var(--border-default);
}

/* Platform icon area with gradient */
.platform-icon-area {
  position: relative;
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.platform-big-icon {
  font-size: 64px;
  opacity: 0.35;
  filter: grayscale(0.3);
  user-select: none;
}

.platform-icon-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  background: linear-gradient(to top, rgba(0,0,0,0.55), transparent);
}

.platform-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--card-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  border: 2px solid rgba(255,255,255,0.3);
  flex-shrink: 0;
}

.platform-name-overlay {
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

/* Card body */
.platform-card-body {
  padding: 16px;
}

.platform-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.meta-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.platform-nickname {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-time {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* Safety bar */
.safety-bar-wrap {
  padding: 8px 0;
  border-top: 1px solid var(--border-subtle);
  margin-top: 4px;
}

.safety-bar-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.safety-bar-score {
  font-weight: 700;
  font-size: 13px;
}

.safety-bar :deep(.el-progress-bar__outer) {
  background: var(--border-subtle);
  border-radius: 3px;
}

/* Actions */
.platform-actions {
  display: flex;
  gap: 8px;
  padding: 0 16px 16px;
}

.platform-actions .el-button {
  flex: 1;
  justify-content: center;
}

/* ═══════════════════════════════════════════════════════════════════
   Responsive
   ═══════════════════════════════════════════════════════════════════ */
@media (max-width: 992px) {
  .safety-card {
    margin-bottom: 12px;
  }
}

@media (max-width: 768px) {
  .settings-platforms-page {
    padding: 16px;
  }
  .safety-card-body {
    flex-direction: column;
    text-align: center;
  }
  .safety-score {
    font-size: 36px;
  }
}
</style>
