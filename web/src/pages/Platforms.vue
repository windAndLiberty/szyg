<template>
  <div class="platforms-page">
    <div class="pub-header">
      <h2>📡 平台管理中心</h2>
      <div class="header-actions">
        <el-button type="primary" @click="refreshAll" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新状态
        </el-button>
        <el-button @click="healthCheck" :loading="healthLoading">
          <el-icon><Check /></el-icon>健康检查
        </el-button>
      </div>
    </div>

    <!-- Platform Cards -->
    <el-row :gutter="16" class="platform-cards">
      <el-col :span="8" v-for="p in platforms" :key="p.id">
        <el-card :class="['platform-card', p.login?.is_logged_in ? 'logged-in' : 'logged-out']" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="platform-icon">{{ platformIcon(p.id) }}</span>
              <span class="platform-name">{{ platformLabel(p.id) }}</span>
              <el-tag :type="p.login?.is_logged_in ? 'success' : 'info'" size="small" effect="dark">
                {{ p.login?.is_logged_in ? '已登录' : '未登录' }}
              </el-tag>
            </div>
          </template>

          <div class="platform-body">
            <div class="platform-info" v-if="p.login?.is_logged_in">
              <div class="info-row">
                <span class="label">账号:</span>
                <span class="value">{{ p.login.account_name || '未知' }}</span>
              </div>
              <div class="info-row" v-if="p.session?.cookie_expiry">
                <span class="label">有效期:</span>
                <span class="value">{{ formatDate(p.session.cookie_expiry) }}</span>
              </div>
              <div class="info-row">
                <span class="label">Cookies:</span>
                <span class="value">{{ p.session?.cookie_count || 0 }} 个</span>
              </div>
              <div class="info-row">
                <span class="label">适配器:</span>
                <span class="value">{{ p.adapter }}</span>
              </div>
            </div>
            <div class="platform-info" v-else>
              <p class="not-logged-in">尚未登录，请点击下方按钮进行扫码登录</p>
            </div>
          </div>

          <div class="platform-actions">
            <el-button
              v-if="!p.login?.is_logged_in"
              type="primary"
              size="small"
              @click="triggerLogin(p.id)"
              :loading="loginLoading[p.id]"
            >
              扫码登录
            </el-button>
            <el-button
              v-else
              type="warning"
              size="small"
              @click="triggerLogout(p.id)"
              :loading="logoutLoading[p.id]"
            >
              退出登录
            </el-button>
            <el-button size="small" @click="viewPlatformDetail(p.id)">
              详情
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Publish History -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>📋 发布历史</span>
      </template>
      <el-table :data="publishLogs" stripe v-loading="logsLoading" empty-text="暂无发布记录">
        <el-table-column label="时间" width="170">
          <template #default="{row}">{{ row.published_at?.slice(0, 16) || '—' }}</template>
        </el-table-column>
        <el-table-column label="平台" width="100">
          <template #default="{row}">
            <el-tag size="small" effect="plain">{{ platformLabel(row.platform) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="内容ID" width="100">
          <template #default="{row}">{{ row.content_id }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{row}">
            <el-tag :type="logStatusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="帖子ID / 错误" min-width="200">
          <template #default="{row}">
            <span v-if="row.platform_post_id">
              <a v-if="row.platform_post_url" :href="row.platform_post_url" target="_blank" class="post-link">
                {{ row.platform_post_id }}
              </a>
              <span v-else>{{ row.platform_post_id }}</span>
            </span>
            <span v-else-if="row.error_msg" class="error-msg">{{ row.error_msg }}</span>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog v-model="showDetail" :title="detailTitle" width="500px">
      <div v-if="detailPlatform">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="平台">{{ platformLabel(detailPlatform.platform) }}</el-descriptions-item>
          <el-descriptions-item label="适配器">{{ detailPlatform.adapter }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detailPlatform.state }}</el-descriptions-item>
          <el-descriptions-item label="已登录">{{ detailPlatform.login?.is_logged_in ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="账号">{{ detailPlatform.login?.account_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="Cookie有效期">{{ detailPlatform.session?.cookie_expiry ? formatDate(detailPlatform.session.cookie_expiry) : '—' }}</el-descriptions-item>
          <el-descriptions-item label="Cookie数量">{{ detailPlatform.session?.cookie_count || 0 }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Check } from '@element-plus/icons-vue'

const platforms = ref([])
const publishLogs = ref([])
const loading = ref(false)
const healthLoading = ref(false)
const logsLoading = ref(false)
const loginLoading = reactive({})
const logoutLoading = reactive({})
const showDetail = ref(false)
const detailPlatform = ref(null)
const detailTitle = ref('')

const platformLabels = {
  douyin: '抖音',
  xhs: '小红书',
  wechat_mp: '微信',
  wecom: '企业微信',
  kuaishou: '快手',
  bilibili: 'B站',
  weibo: '微博',
}

const platformIcons = {
  douyin: '🎵',
  xhs: '📕',
  wechat_mp: '💬',
  wecom: '🏢',
  kuaishou: '⚡',
  bilibili: '📺',
  weibo: '📰',
}

function platformLabel(id) {
  return platformLabels[id] || id
}

function platformIcon(id) {
  return platformIcons[id] || '📡'
}

function logStatusType(status) {
  return { success: 'success', failed: 'danger', skipped: 'warning', pending: 'info' }[status] || 'info'
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso.slice(0, 16)
  }
}

async function refreshAll() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/platforms')
    platforms.value = (data.platforms || []).map(p => ({
      ...p,
      login: p.login || { is_logged_in: false },
      session: p.session || { has_session: false, cookie_count: 0 },
    }))
  } catch (e) {
    ElMessage.error('加载平台列表失败')
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const { data } = await axios.get('/api/platforms/logs/all', { params: { limit: 30 } })
    publishLogs.value = Array.isArray(data) ? data : []
  } catch {
    publishLogs.value = []
  } finally {
    logsLoading.value = false
  }
}

async function triggerLogin(platform) {
  loginLoading[platform] = true
  try {
    const { data } = await axios.post(`/api/platforms/${platform}/login`)
    if (data.is_logged_in) {
      ElMessage.success(`[${platformLabel(platform)}] 登录成功!`)
    } else {
      ElMessage.info(`[${platformLabel(platform)}] 请在桌面端扫码登录 (5分钟超时)`)
    }
    await refreshAll()
  } catch (e) {
    ElMessage.error(`[${platformLabel(platform)}] 登录失败: ${e.response?.data?.detail || e.message}`)
  } finally {
    loginLoading[platform] = false
  }
}

async function triggerLogout(platform) {
  try {
    await ElMessageBox.confirm(`确认清除 ${platformLabel(platform)} 登录态？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  logoutLoading[platform] = true
  try {
    await axios.delete(`/api/publisher/platforms/${platform}/sessions`)
    ElMessage.success(`[${platformLabel(platform)}] 登录态已清除`)
    await refreshAll()
  } catch (e) {
    ElMessage.error(`清除失败: ${e.message}`)
  } finally {
    logoutLoading[platform] = false
  }
}

async function healthCheck() {
  healthLoading.value = true
  try {
    const { data } = await axios.get('/api/platforms/health/all')
    let msg = Object.entries(data).map(([k, v]) => {
      const name = platformLabel(k)
      const status = v.is_logged_in ? '✓ 已登录' : '✗ 未登录'
      return `${name}: ${status}`
    }).join('\n')
    ElMessage.success('健康检查完成，查看控制台')
    console.log('Platform Health:', data)
  } catch (e) {
    ElMessage.error('健康检查失败')
  } finally {
    healthLoading.value = false
  }
}

async function viewPlatformDetail(platform) {
  try {
    const { data } = await axios.get(`/api/platforms/${platform}`)
    detailPlatform.value = data
    detailTitle.value = `${platformLabel(platform)} 详情`
    showDetail.value = true
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

onMounted(async () => {
  await refreshAll()
  await loadLogs()
})
</script>

<style scoped>
.platforms-page {
  padding: 0;
}

.platform-cards {
  margin-top: 16px;
}

.platform-card {
  min-height: 220px;
  transition: all 0.3s;
}

.platform-card.logged-in {
  border-left: 4px solid var(--el-color-success);
}

.platform-card.logged-out {
  border-left: 4px solid var(--el-color-info);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-icon {
  font-size: 20px;
}

.platform-name {
  font-weight: 600;
  flex: 1;
}

.platform-body {
  min-height: 100px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}

.info-row .label {
  color: var(--el-text-color-secondary);
}

.info-row .value {
  font-weight: 500;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.not-logged-in {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-align: center;
  padding: 20px 0;
}

.platform-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.post-link {
  color: var(--el-color-primary);
  text-decoration: none;
}

.post-link:hover {
  text-decoration: underline;
}

.error-msg {
  color: var(--el-color-danger);
  font-size: 12px;
}

.pub-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.pub-header h2 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}
</style>
