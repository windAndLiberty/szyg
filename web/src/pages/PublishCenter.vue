<template>
  <div class="page-container">
    <h2 class="page-title">多平台发布</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <el-tab-pane label="发布队列" name="queue">
        <div class="kanban-row">
          <div class="kanban-col" v-for="col in queueCols" :key="col.status">
            <div class="kanban-header">{{ col.label }} ({{ col.items.length }})</div>
            <div class="kanban-items">
              <el-card v-for="item in col.items" :key="item.id" shadow="hover" class="kanban-item">
                <div class="item-title">{{ item.title }}</div>
                <div class="item-meta">
                  <el-tag size="small" v-for="p in item.platforms" :key="p">{{ p }}</el-tag>
                </div>
              </el-card>
              <el-empty v-if="!col.items.length" :image-size="60" description="暂无" />
            </div>
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane label="定时计划" name="schedule">
        <el-empty description="定时发布计划日历视图" />
      </el-tab-pane>
      <el-tab-pane label="发布历史" name="history">
        <el-table :data="historyData" stripe>
          <el-table-column prop="title" label="标题" min-width="200" />
          <el-table-column prop="platform" label="平台" width="100" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="time" label="发布时间" width="160" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="账号管理" name="accounts">
        <div class="tab-content">
          <el-table :data="sauPlatforms" stripe>
            <el-table-column prop="platform" label="平台" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ platformLabel(row.platform) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="视频" width="60">
              <template #default="{ row }">
                <el-icon v-if="row.video_support" color="#22c55e"><Check /></el-icon>
                <el-icon v-else color="#999"><Close /></el-icon>
              </template>
            </el-table-column>
            <el-table-column label="图文" width="60">
              <template #default="{ row }">
                <el-icon v-if="row.note_support" color="#22c55e"><Check /></el-icon>
                <el-icon v-else color="#999"><Close /></el-icon>
              </template>
            </el-table-column>
            <el-table-column label="登录状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.has_cookie ? 'success' : 'info'" size="small">
                  {{ row.has_cookie ? '已登录' : '未登录' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="account_file" label="Cookie文件" min-width="200" show-overflow-tooltip />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="sauLogin(row.platform)">登录</el-button>
                <el-button size="small" plain @click="sauCheckLogin(row.platform)">检查</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
      <el-tab-pane label="快速发布" name="quick">
        <div class="tab-content">
          <el-form :model="quickForm" label-width="80px" style="max-width: 600px">
            <el-form-item label="平台">
              <el-select v-model="quickForm.platform" style="width: 200px">
                <el-option label="抖音" value="douyin" />
                <el-option label="小红书" value="xhs" />
                <el-option label="快手" value="kuaishou" />
                <el-option label="视频号" value="tencent" />
                <el-option label="YouTube" value="youtube" />
              </el-select>
            </el-form-item>
            <el-form-item label="类型">
              <el-radio-group v-model="quickForm.type">
                <el-radio value="video">视频</el-radio>
                <el-radio value="note">图文</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="标题">
              <el-input v-model="quickForm.title" placeholder="请输入标题" />
            </el-form-item>
            <el-form-item v-if="quickForm.type === 'video'" label="视频文件">
              <el-input v-model="quickForm.filePath" placeholder="本地视频文件路径，如 D:\videos\demo.mp4" />
            </el-form-item>
            <el-form-item v-else label="图片文件">
              <el-input v-model="quickForm.imagePaths" type="textarea" :rows="2" placeholder="逗号分隔的图片路径" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="quickForm.desc" type="textarea" :rows="3" placeholder="描述/正文" />
            </el-form-item>
            <el-form-item label="标签">
              <el-input v-model="quickForm.tags" placeholder="逗号分隔" />
            </el-form-item>
            <el-form-item label="定时">
              <el-date-picker v-model="quickForm.schedule" type="datetime" placeholder="不选则立即发布" format="YYYY-MM-DD HH:mm" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="quickLoading" @click="quickPublish">立即发布</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'
import axios from 'axios'

const activeTab = ref('queue')
const queueCols = ref([
  { status: 'pending', label: '待审核', items: [] },
  { status: 'approved', label: '待发布', items: [] },
  { status: 'publishing', label: '发布中', items: [] },
  { status: 'published', label: '已发布', items: [] },
  { status: 'failed', label: '失败', items: [] },
])
const historyData = ref([])
const sauPlatforms = ref([])
const quickLoading = ref(false)
const quickForm = ref({
  platform: 'douyin',
  type: 'video',
  title: '',
  filePath: '',
  imagePaths: '',
  desc: '',
  tags: '',
  schedule: null,
})

function platformLabel(p) {
  return { douyin: '抖音', xhs: '小红书', kuaishou: '快手', tencent: '视频号', youtube: 'YouTube' }[p] || p
}

async function loadSauPlatforms() {
  try {
    const { data } = await axios.get('/api/sau/platforms')
    sauPlatforms.value = data.platforms || []
  } catch {
    // API not ready
  }
}

async function sauLogin(platform) {
  try {
    ElMessage.info(`正在打开 ${platformLabel(platform)} 登录窗口...`)
    const { data } = await axios.post(`/api/sau/login/${platform}`)
    if (data.success) {
      ElMessage.success(`${platformLabel(platform)} 登录成功`)
      loadSauPlatforms()
    } else {
      ElMessage.warning(data.message || '登录失败')
    }
  } catch (e) {
    ElMessage.error('登录请求失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function sauCheckLogin(platform) {
  try {
    const { data } = await axios.get(`/api/sau/check-login/${platform}`)
    if (data.logged_in) {
      ElMessage.success(`${platformLabel(platform)} 已登录`)
    } else {
      ElMessage.warning(`${platformLabel(platform)} 未登录: ${data.message || ''}`)
    }
    loadSauPlatforms()
  } catch (e) {
    ElMessage.error('检查失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function quickPublish() {
  if (!quickForm.value.title) { ElMessage.warning('请输入标题'); return }
  if (quickForm.value.type === 'video' && !quickForm.value.filePath) { ElMessage.warning('请输入视频文件路径'); return }
  if (quickForm.value.type === 'note' && !quickForm.value.imagePaths) { ElMessage.warning('请输入图片路径'); return }

  quickLoading.value = true
  try {
    const schedule = quickForm.value.schedule
      ? quickForm.value.schedule.toISOString().slice(0, 16).replace('T', ' ')
      : null
    const tags = quickForm.value.tags.split(',').map(t => t.trim()).filter(Boolean)

    if (quickForm.value.type === 'video') {
      const { data } = await axios.post('/api/sau/upload-video', {
        platform: quickForm.value.platform,
        file_path: quickForm.value.filePath,
        title: quickForm.value.title,
        desc: quickForm.value.desc,
        tags,
        schedule,
      })
      if (data.success) {
        ElMessage.success(`${platformLabel(quickForm.value.platform)} 视频发布成功`)
      } else {
        ElMessage.error(data.message || '发布失败')
      }
    } else {
      const imagePaths = quickForm.value.imagePaths.split(',').map(p => p.trim()).filter(Boolean)
      const { data } = await axios.post('/api/sau/upload-note', {
        platform: quickForm.value.platform,
        image_paths: imagePaths,
        title: quickForm.value.title,
        note: quickForm.value.desc,
        tags,
        schedule,
      })
      if (data.success) {
        ElMessage.success(`${platformLabel(quickForm.value.platform)} 图文发布成功`)
      } else {
        ElMessage.error(data.message || '发布失败')
      }
    }
  } catch (e) {
    ElMessage.error('发布请求失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    quickLoading.value = false
  }
}

onMounted(() => {
  loadSauPlatforms()
})
</script>

<style scoped>
.page-container { padding: 24px; }
.page-title { margin: 0 0 20px; font-size: 18px; }
.studio-tabs { border-radius: 8px; }
.tab-content { padding: 16px 0; }
.kanban-row { display: flex; gap: 12px; padding: 16px; overflow-x: auto; }
.kanban-col { min-width: 200px; flex: 1; }
.kanban-header { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text-secondary); }
.kanban-items { display: flex; flex-direction: column; gap: 8px; }
.kanban-item { cursor: pointer; }
.item-title { font-size: 13px; margin-bottom: 6px; }
.item-meta { display: flex; gap: 4px; flex-wrap: wrap; }
</style>
