<template>
  <div class="skills-market">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2>技能市场</h2>
        <p class="subtitle">浏览、安装和管理 AI 员工技能包</p>
      </div>
    </div>

    <!-- 搜索 + 筛选栏 -->
    <div class="filter-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索技能名称或描述..."
        prefix-icon="Search"
        clearable
        class="filter-input"
      />
      <el-select v-model="categoryFilter" placeholder="全部分类" class="filter-select" clearable>
        <el-option label="全部分类" value="" />
        <el-option label="内容创作" value="content" />
        <el-option label="获客转化" value="acquisition" />
        <el-option label="办公工具" value="office" />
        <el-option label="数据分析" value="data" />
        <el-option label="平台运营" value="platform" />
      </el-select>
      <el-select v-model="sortBy" placeholder="排序" class="filter-select">
        <el-option label="最热" value="hot" />
        <el-option label="最新" value="new" />
        <el-option label="评分最高" value="rating" />
      </el-select>
      <span class="result-count">共 {{ filteredSkills.length }} 个技能</span>
    </div>

    <!-- 子标签 -->
    <el-tabs v-model="activeTab" class="skills-tabs">
      <!-- 子标签 1：技能市场 -->
      <el-tab-pane label="技能市场" name="market">
        <el-row v-if="filteredSkills.length" :gutter="16">
          <el-col
            v-for="skill in filteredSkills"
            :key="skill.id"
            :xs="24"
            :sm="12"
            :md="8"
            :lg="6"
            class="skill-col"
          >
            <el-card class="skill-card" shadow="never" @click="openDetail(skill)">
              <div class="card-body">
                <div class="card-icon">{{ skill.icon }}</div>
                <div class="card-name">{{ skill.name }}</div>
                <div class="card-desc">{{ skill.description }}</div>
                <div class="card-meta">
                  <span class="card-rating">
                    <el-rate
                      :model-value="skill.rating"
                      disabled
                      :colors="['#fbbf24', '#fbbf24', '#fbbf24']"
                      void-color="#d1d5db"
                    />
                    <span class="rating-text">{{ skill.rating }}</span>
                  </span>
                  <el-tag size="small" effect="plain" :type="TRUST_COLORS[skill.trust_level] || 'info'">
                    {{ TRUST_LABELS[skill.trust_level] || skill.trust_level }}
                  </el-tag>
                </div>
                <div class="card-author">👤 {{ skill.author }}</div>
                <div class="card-tags">
                  <el-tag
                    v-for="tag in skill.tags"
                    :key="tag"
                    size="small"
                    :class="['compat-tag', tagClass(tag)]"
                    effect="plain"
                  >
                    {{ tag }}
                  </el-tag>
                </div>
              </div>
              <div class="card-action">
                <el-button type="primary" size="small" @click.stop="installSkill(skill)">
                  安装
                </el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
        <el-empty v-else description="没有找到匹配的技能" />
      </el-tab-pane>

      <!-- 子标签 2：已安装管理 -->
      <el-tab-pane label="已安装管理" name="installed">
        <div class="installed-header">
          <el-button type="primary" @click="showLocalInstall = true">
            <el-icon><Upload /></el-icon> 安装本地技能
          </el-button>
        </div>
        <el-table
          :data="installedSkills"
          class="installed-table"
          stripe
          style="width: 100%"
        >
          <el-table-column prop="name" label="技能名称" min-width="140" />
          <el-table-column prop="version" label="版本" width="90" />
          <el-table-column prop="installTime" label="安装时间" width="120" />
          <el-table-column label="适用员工" min-width="160">
            <template #default="{ row }">
              <el-tag
                v-for="e in row.applicableEmployees"
                :key="e"
                size="small"
                class="employee-tag"
                effect="plain"
              >
                {{ e }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status === 'active' ? '已启用' : '已停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <el-button
                v-if="row.hasUpdate"
                type="primary"
                size="small"
                text
                @click="updateSkill(row)"
              >
                更新
              </el-button>
              <el-button type="primary" size="small" text @click="configSkill(row)">
                <el-icon><Setting /></el-icon> 配置
              </el-button>
              <el-button type="danger" size="small" text @click="uninstallSkill(row)">
                <el-icon><Delete /></el-icon> 卸载
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 发布技能区域 -->
    <div class="publish-section">
      <el-button type="primary" size="large" @click="showPublish = true">
        <el-icon><Plus /></el-icon> 发布技能
      </el-button>
      <p class="publish-hint">将你的自定义技能分享给团队或社区</p>
    </div>

    <!-- 技能详情 Drawer -->
    <el-drawer
      v-model="detailVisible"
      :title="detailSkill?.name || '技能详情'"
      size="560px"
      class="skill-drawer"
    >
      <div v-if="detailSkill" class="detail-content">
        <!-- L0：基础信息（始终显示） -->
        <div class="detail-l0">
          <div class="detail-header-row">
            <span class="detail-icon">{{ detailSkill.icon }}</span>
            <div class="detail-header-info">
              <h3 class="detail-title">{{ detailSkill.name }}</h3>
              <div class="detail-meta-row">
                <el-tag size="small" :type="(TRUST_COLORS[detailSkill.trust_level] || 'info')">
                  {{ TRUST_LABELS[detailSkill.trust_level] || detailSkill.trust_level }}
                </el-tag>
                <span class="detail-author">来源: {{ detailSkill.source }}</span>
              </div>
              <div class="detail-tags">
                <el-tag
                  v-for="tag in detailSkill.tags"
                  :key="tag"
                  size="small"
                  :class="['compat-tag', tagClass(tag)]"
                  effect="plain"
                >
                  {{ tag }}
                </el-tag>
              </div>
            </div>
          </div>
          <p class="detail-desc">{{ detailSkill.description }}</p>
          <el-button type="primary" class="install-btn" @click="installSkill(detailSkill)">
            安装此技能
          </el-button>
        </div>

        <!-- SKILL.md 预览 -->
        <el-collapse v-model="detailLevels" class="detail-collapse" v-if="detailSkill.skill_md_preview">
          <el-collapse-item name="L1">
            <template #title>
              <span class="collapse-title">SKILL.md 预览</span>
            </template>
            <div class="detail-l1">
              <pre class="code-block">{{ detailSkill.skill_md_preview }}</pre>
              <p v-if="detailSkill.skill_md_full_lines > 80" class="truncate-hint">
                已截断，显示前 80 行（共 {{ detailSkill.skill_md_full_lines }} 行）
              </p>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-drawer>

    <!-- 发布技能 Dialog -->
    <el-dialog v-model="showPublish" title="发布技能" width="560px" class="publish-dialog">
      <el-form :model="publishForm" label-position="top">
        <el-form-item label="技能名称" required>
          <el-input v-model="publishForm.name" placeholder="输入技能名称，如：营销文案生成" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="publishForm.description"
            type="textarea"
            :rows="3"
            placeholder="技能的功能描述"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="publishForm.category" placeholder="选择分类" style="width: 100%">
            <el-option label="内容创作" value="content" />
            <el-option label="获客转化" value="acquisition" />
            <el-option label="办公工具" value="office" />
            <el-option label="数据分析" value="data" />
            <el-option label="平台运营" value="platform" />
          </el-select>
        </el-form-item>
        <el-form-item label="兼容性">
          <el-select
            v-model="publishForm.compatibility"
            multiple
            placeholder="选择适用员工类型"
            style="width: 100%"
          >
            <el-option label="内容专员" value="内容专员" />
            <el-option label="获客专员" value="获客专员" />
            <el-option label="转化专员" value="转化专员" />
            <el-option label="运营专员" value="运营专员" />
          </el-select>
        </el-form-item>
        <el-form-item label="SKILL.md">
          <el-upload
            drag
            action=""
            :auto-upload="false"
            accept=".md"
            :limit="1"
            @change="handlePublishFile"
          >
            <el-icon class="upload-icon"><Upload /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">请上传 SKILL.md 文件</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="引用文件（可选）">
          <el-upload action="" :auto-upload="false" accept="*/*" multiple>
            <el-button type="primary" text>选择文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPublish = false">取消</el-button>
        <el-button type="primary" @click="submitPublish">提交审核</el-button>
      </template>
    </el-dialog>

    <!-- 安装本地技能 Dialog -->
    <el-dialog v-model="showLocalInstall" title="安装本地技能" width="480px">
      <el-upload
        drag
        action=""
        :auto-upload="false"
        accept=".md"
        :limit="1"
        @change="handleLocalInstall"
      >
        <el-icon class="upload-icon"><Upload /></el-icon>
        <div class="el-upload__text">拖拽 SKILL.md 文件到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 .md 格式的 SKILL.md 文件</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showLocalInstall = false">取消</el-button>
        <el-button type="primary" @click="confirmLocalInstall">安装</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Upload, Delete, Setting } from '@element-plus/icons-vue'
import axios from 'axios'
import { getErrorMessage } from '@/api'

// ═══════════════════════════════════════════════════════════════
// 状态
// ═══════════════════════════════════════════════════════════════
const searchQuery = ref('')
const categoryFilter = ref('')
const sortBy = ref('hot')
const activeTab = ref('market')

const detailVisible = ref(false)
const detailSkill = ref(null)
const detailLevels = ref([])

const showPublish = ref(false)
const showLocalInstall = ref(false)
const localFile = ref(null)

const publishForm = ref({
  name: '',
  description: '',
  category: '',
  compatibility: [],
})

// ═══════════════════════════════════════════════════════════════
// API 数据 — 真实技能市场
// ═══════════════════════════════════════════════════════════════
const baseSkills = ref([])
const installedSkills = ref([])

const TRUST_LABELS = { builtin: '内置', trusted: '可信', community: '社区' }
const TRUST_COLORS = { builtin: 'success', trusted: 'warning', community: 'info' }
const SOURCE_ICONS = { 'hermes-index': '📋', 'github': '🐙', 'skillssh': '🔧', 'lobehub': '🎨', 'clawhub': '🦞', 'claude-marketplace': '🤖', 'well-known': '⭐', 'url': '🔗' }

async function loadSkills() {
  try {
    const [{ data: marketData }, { data: installedData }] = await Promise.all([
      axios.get('/api/skills/market', { params: { page_size: 50 } }),
      axios.get('/api/skills/installed'),
    ])
    const items = marketData.items || []
    baseSkills.value = items.map(m => ({
      ...m,
      id: m.identifier || m.name,
      icon: SOURCE_ICONS[m.source] || '📦',
      downloads: null,
      rating: m.trust_level === 'builtin' ? 5.0 : m.trust_level === 'trusted' ? 4.5 : 4.0,
      author: m.source || 'community',
    }))
    const instItems = installedData.items || []
    installedSkills.value = instItems.map(i => ({
      id: i.identifier || i.name,
      name: i.name,
      version: i.version || '—',
      installTime: i.installed_at ? i.installed_at.slice(0, 10) : '',
      applicableEmployees: [],
      status: 'active',
      hasUpdate: false,
    }))
  } catch (e) {
    ElMessage.error('加载技能失败: ' + getErrorMessage(e))
  }
}

onMounted(() => {
  loadSkills()
})

// 过滤 + 排序（computed）
const filteredSkills = computed(() => {
  let list = [...(baseSkills.value || [])]

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(
      s =>
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
    )
  }

  if (categoryFilter.value) {
    list = list.filter(s =>
      s.tags?.some(t => t.toLowerCase().includes(categoryFilter.value.toLowerCase()))
    )
  }

  if (sortBy.value === 'hot') {
    list.sort((a, b) => (TRUST_ORDER[a.trust_level] ?? 3) - (TRUST_ORDER[b.trust_level] ?? 3))
  } else if (sortBy.value === 'rating') {
    list.sort((a, b) => (b.rating || 0) - (a.rating || 0))
  }

  return list
})

// ═══════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════
const tagClassMap = {
  '内容专员': 'tag-cyan',
  '获客专员': 'tag-purple',
  '转化专员': 'tag-green',
  '运营专员': 'tag-blue',
}

const TRUST_ORDER = { builtin: 0, trusted: 1, community: 2 }

function tagClass(tag) {
  return tagClassMap[tag] || ''
}

// ═══════════════════════════════════════════════════════════════
// Actions
// ═══════════════════════════════════════════════════════════════
async function openDetail(skill) {
  detailSkill.value = skill
  detailLevels.value = []
  detailVisible.value = true
  // Fetch full detail including SKILL.md preview from API
  if (skill.identifier) {
    try {
      const { data } = await axios.get(`/api/skills/market/${encodeURIComponent(skill.identifier)}`)
      detailSkill.value = {
        ...skill,
        ...data,
        icon: skill.icon,  // keep the source icon
      }
    } catch (_) {
      // Use marketplace data as-is if detail fetch fails
    }
  }
}

async function installSkill(skill) {
  if (installedSkills.value.find(s => s.name === skill.name)) {
    ElMessage.warning(`「${skill.name}」已安装`)
    return
  }
  try {
    const { data } = await axios.post('/api/skills/install', {
      identifier: skill.identifier,
      category: skill.tags?.[0] || '',
    })
    ElMessage.success(`「${data.skill_name || skill.name}」安装成功`)
    await loadSkills()
  } catch (e) {
    ElMessage.error('安装失败: ' + getErrorMessage(e))
  }
}

function updateSkill(row) {
  ElMessage.info(`更新「${row.name}」—— 功能开发中`)
}

function configSkill(row) {
  ElMessage.info(`配置「${row.name}」—— 功能开发中`)
}

async function uninstallSkill(row) {
  try {
    await axios.delete(`/api/skills/installed/${encodeURIComponent(row.name)}`)
    ElMessage.success(`「${row.name}」已卸载`)
    await loadSkills()
  } catch (e) {
    ElMessage.error('卸载失败: ' + getErrorMessage(e))
  }
}

async function toggleInstalledStatus(row) {
  try {
    ElMessage.info(`切换「${row.name}」状态 —— 功能开发中`)
  } catch (e) {
    ElMessage.error('操作失败: ' + getErrorMessage(e))
  }
}

async function submitPublish() {
  if (!publishForm.value.name.trim()) {
    ElMessage.warning('请输入技能名称')
    return
  }
  try {
    await axios.post('/api/agents/create', {
      name: publishForm.value.name,
      description: publishForm.value.description,
      category: publishForm.value.category,
      tags: publishForm.value.compatibility,
    })
    ElMessage.success('技能已提交审核')
    showPublish.value = false
    publishForm.value = { name: '', description: '', category: '', compatibility: [] }
    await loadSkills()
  } catch (e) {
    ElMessage.error('提交失败: ' + getErrorMessage(e))
  }
}

function handlePublishFile() {
  // 上传文件处理
}

function handleLocalInstall(file) {
  localFile.value = file
}

async function confirmLocalInstall() {
  if (!localFile.value) {
    ElMessage.warning('请先上传 SKILL.md 文件')
    return
  }
  try {
    await axios.post('/api/agents/create', {
      name: localFile.value.name || '本地技能',
      description: '本地安装的技能',
      category: 'local',
      tags: [],
    })
    ElMessage.success('本地技能安装成功')
    showLocalInstall.value = false
    localFile.value = null
    await loadSkills()
  } catch (e) {
    ElMessage.error('安装失败: ' + getErrorMessage(e))
  }
}
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════════
   Layout
   ═══════════════════════════════════════════════════════════════ */
.skills-market {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--text-primary);
}
.subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}

/* Filter Bar */
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.filter-input {
  flex: 1;
  min-width: 200px;
  max-width: 320px;
}
.filter-select {
  width: 140px;
}
.result-count {
  margin-left: auto;
  font-size: 13px;
  color: var(--text-tertiary);
}

/* Tabs */
.skills-tabs {
  margin-bottom: 8px;
}

/* ═══════════════════════════════════════════════════════════════
   Skill Cards
   ═══════════════════════════════════════════════════════════════ */
.skill-col {
  margin-bottom: 16px;
}

.skill-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.3s var(--ease-out-expo);
  height: 100%;
}
.skill-card:hover {
  transform: translateY(-4px);
  border-color: var(--accent-primary);
  box-shadow: var(--accent-glow);
}

.skill-card :deep(.el-card__body) {
  padding: 20px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-icon {
  font-size: 40px;
  margin-bottom: 10px;
  text-align: center;
}
.card-name {
  font-weight: 700;
  font-size: 15px;
  color: var(--text-primary);
  margin-bottom: 8px;
  text-align: center;
  line-height: 1.4;
}
.card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 12px;
}
.card-rating {
  display: flex;
  align-items: center;
  gap: 4px;
}
.rating-text {
  color: #fbbf24;
  font-weight: 600;
  font-size: 12px;
}
.card-downloads {
  color: var(--text-tertiary);
}
.card-author {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}
.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.card-action {
  margin-top: auto;
  padding-top: 12px;
  text-align: center;
}

/* ═══════════════════════════════════════════════════════════════
   Compatibility Tags (Light)
   ═══════════════════════════════════════════════════════════════ */
.compat-tag {
  font-size: 11px;
}

.tag-cyan {
  color: #0891b2 !important;
  background: rgba(8, 145, 178, 0.1) !important;
  border-color: rgba(8, 145, 178, 0.2) !important;
}
.tag-purple {
  color: #7c3aed !important;
  background: rgba(124, 58, 237, 0.1) !important;
  border-color: rgba(124, 58, 237, 0.2) !important;
}
.tag-green {
  color: #16a34a !important;
  background: rgba(22, 163, 74, 0.1) !important;
  border-color: rgba(22, 163, 74, 0.2) !important;
}
.tag-blue {
  color: #2563eb !important;
  background: rgba(37, 99, 235, 0.1) !important;
  border-color: rgba(37, 99, 235, 0.2) !important;
}

/* ═══════════════════════════════════════════════════════════════
   Compatibility Tags (Dark)
   ═══════════════════════════════════════════════════════════════ */
:global(html.dark) .tag-cyan {
  color: var(--accent) !important;
  background: var(--accent-soft) !important;
  border-color: var(--border-active) !important;
}
:global(html.dark) .tag-purple {
  color: var(--indigo-400, #a5b4fc) !important;
  background: rgba(129, 140, 248, 0.1) !important;
  border-color: rgba(129, 140, 248, 0.2) !important;
}
:global(html.dark) .tag-green {
  color: #22c55e !important;
  background: rgba(34, 197, 94, 0.1) !important;
  border-color: rgba(34, 197, 94, 0.2) !important;
}
:global(html.dark) .tag-blue {
  color: #48e0ff !important;
  background: rgba(72, 224, 255, 0.1) !important;
  border-color: rgba(72, 224, 255, 0.2) !important;
}

/* ═══════════════════════════════════════════════════════════════
   Installed Management
   ═══════════════════════════════════════════════════════════════ */
.installed-header {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-end;
}
.installed-table {
  background: var(--card-bg);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  overflow: hidden;
}
.employee-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}

/* ═══════════════════════════════════════════════════════════════
   Publish Section
   ═══════════════════════════════════════════════════════════════ */
.publish-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 0;
  border-top: 1px solid var(--border-color);
  margin-top: 20px;
}
.publish-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ═══════════════════════════════════════════════════════════════
   Detail Drawer
   ═══════════════════════════════════════════════════════════════ */
.skill-drawer :deep(.el-drawer__body) {
  background: var(--glass-bg, var(--card-bg));
  padding: 24px;
  overflow-y: auto;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* L0 */
.detail-l0 {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}
.detail-header-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 12px;
}
.detail-icon {
  font-size: 48px;
  flex-shrink: 0;
}
.detail-header-info {
  flex: 1;
  min-width: 0;
}
.detail-title {
  margin: 0 0 8px;
  font-size: 18px;
  color: var(--text-primary);
}
.detail-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}
.detail-rating {
  display: flex;
  align-items: center;
  gap: 4px;
}
.rating-number {
  color: #fbbf24;
  font-weight: 600;
}
.detail-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.category-tag {
  color: var(--text-tertiary) !important;
  background: transparent !important;
}
.detail-desc {
  margin: 12px 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-secondary);
}
.install-btn {
  margin-top: 8px;
}

/* Collapse L1 / L2 */
.detail-collapse {
  border: none;
}
.collapse-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.detail-l1 {
  padding: 8px 0;
}
.section-title {
  margin: 16px 0 8px;
  font-size: 14px;
  color: var(--text-primary);
}
.section-title:first-child {
  margin-top: 0;
}
.feature-list {
  margin: 0;
  padding-left: 20px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.8;
}
.example-box {
  background: var(--hover-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 16px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
}
.code-block {
  background: var(--hover-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 16px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
}
.params-table {
  background: transparent;
}

/* Upload icon */
.upload-icon {
  font-size: 28px;
  color: var(--text-tertiary);
}

/* Responsive */
@media (max-width: 768px) {
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-input,
  .filter-select {
    max-width: 100%;
    width: 100%;
  }
  .result-count {
    margin-left: 0;
  }
}
</style>
