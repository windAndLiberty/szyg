<template>
  <div class="content-studio-page">
    <h2 class="page-title">内容工作室</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <!-- ═══════════════════════════════════════════════════════════════
           Tab 1 — 内容生产
           ═══════════════════════════════════════════════════════════════ -->
      <el-tab-pane label="内容生产" name="produce">
        <div class="tab-content produce-tab">
          <!-- 1. 模板卡片选择器 -->
          <div class="template-section">
            <div class="section-title">选择模板</div>
            <div class="template-scroll">
              <div
                v-for="t in templates"
                :key="t.id"
                class="template-card"
                :class="{ selected: selectedTemplate === t.id }"
                @click="selectedTemplate = t.id"
              >
                <div class="template-icon">
                  <el-icon :size="28"><component :is="t.icon" /></el-icon>
                </div>
                <div class="template-name">{{ t.name }}</div>
                <div class="template-desc">{{ t.desc }}</div>
              </div>
            </div>
          </div>

          <!-- 2. 生产向导 + 右侧参数面板 -->
          <el-row :gutter="20" class="produce-main">
            <el-col :span="16">
              <div class="wizard-section">
                <el-steps :active="stepIndex" finish-status="success" simple>
                  <el-step title="选题" />
                  <el-step title="脚本" />
                  <el-step title="生成" />
                  <el-step title="预览" />
                </el-steps>

                <div class="step-content">
                  <!-- 步骤1: 选题 -->
                  <div v-if="stepIndex === 0" class="step-panel">
                    <el-input
                      v-model="topicForm.theme"
                      placeholder="输入内容主题..."
                      size="large"
                      clearable
                    />
                    <el-button
                      type="primary"
                      class="ai-btn"
                      @click="aiRecommendTopic"
                    >
                      <el-icon><MagicStick /></el-icon> AI 推荐选题
                    </el-button>
                    <div v-if="topicForm.recommended.length" class="recommend-list">
                      <div class="recommend-title">AI 推荐选题：</div>
                      <el-tag
                        v-for="(r, i) in topicForm.recommended"
                        :key="i"
                        class="recommend-tag"
                        @click="topicForm.theme = r"
                      >
                        {{ r }}
                      </el-tag>
                    </div>
                  </div>

                  <!-- 步骤2: 脚本 -->
                  <div v-if="stepIndex === 1" class="step-panel">
                    <el-input
                      v-model="scriptForm.content"
                      type="textarea"
                      :rows="8"
                      placeholder="在此编辑脚本内容..."
                    />
                    <el-button
                      type="primary"
                      class="ai-btn"
                      @click="aiGenerateScript"
                    >
                      <el-icon><MagicStick /></el-icon> AI 生成脚本
                    </el-button>
                  </div>

                  <!-- 步骤3: 生成 -->
                  <div v-if="stepIndex === 2" class="step-panel">
                    <el-form label-position="top">
                      <el-form-item label="输出格式">
                        <el-radio-group v-model="generateForm.format">
                          <el-radio-button label="图文">图文</el-radio-button>
                          <el-radio-button label="视频">视频</el-radio-button>
                          <el-radio-button label="音频">音频</el-radio-button>
                        </el-radio-group>
                      </el-form-item>
                      <el-form-item label="参数配置">
                        <el-row :gutter="12">
                          <el-col :span="12">
                            <el-input
                              v-model.number="generateForm.duration"
                              placeholder="时长（秒）"
                            >
                              <template #append>秒</template>
                            </el-input>
                          </el-col>
                          <el-col :span="12">
                            <el-input
                              v-model.number="generateForm.wordLimit"
                              placeholder="字数限制"
                            >
                              <template #append>字</template>
                            </el-input>
                          </el-col>
                        </el-row>
                      </el-form-item>
                    </el-form>
                    <el-button
                      type="primary"
                      class="ai-btn"
                      @click="stepIndex = 3"
                    >
                      <el-icon><VideoPlay /></el-icon> 开始生成
                    </el-button>
                  </div>

                  <!-- 步骤4: 预览 -->
                  <div v-if="stepIndex === 3" class="step-panel">
                    <div v-if="generating" class="generating-area">
                      <el-progress
                        :percentage="generateProgress"
                        :stroke-width="16"
                        striped
                        :status="generateProgress === 100 ? 'success' : ''"
                      />
                      <div class="generating-text">
                        <el-icon class="is-loading"><Loading /></el-icon>
                        {{ generateProgress < 100 ? '正在生成内容...' : '生成完成！' }}
                      </div>
                    </div>
                    <div v-else class="preview-area">
                      <div class="preview-placeholder">
                        <el-icon :size="48"><Picture /></el-icon>
                        <div>生成结果预览区</div>
                        <div class="preview-desc">点击「开始生成」后在此预览内容</div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 向导导航按钮 -->
                <div class="step-nav">
                  <el-button
                    :disabled="stepIndex === 0"
                    @click="stepIndex--"
                  >上一步</el-button>
                  <el-button
                    v-if="stepIndex < 3"
                    type="primary"
                    @click="stepIndex++"
                  >下一步</el-button>
                </div>
              </div>
            </el-col>

            <!-- 右侧参数配置面板 -->
            <el-col :span="8">
              <div class="params-panel">
                <div class="panel-title">参数配置</div>
                <el-form label-position="top">
                  <el-form-item label="目标平台">
                    <el-checkbox-group v-model="paramsForm.platforms">
                      <el-checkbox label="douyin">抖音</el-checkbox>
                      <el-checkbox label="xhs">小红书</el-checkbox>
                      <el-checkbox label="bilibili">B站</el-checkbox>
                      <el-checkbox label="kuaishou">快手</el-checkbox>
                      <el-checkbox label="wechat">微信</el-checkbox>
                    </el-checkbox-group>
                  </el-form-item>
                  <el-form-item label="内容风格">
                    <el-select v-model="paramsForm.style" placeholder="选择风格">
                      <el-option label="专业严谨" value="professional" />
                      <el-option label="轻松活泼" value="casual" />
                      <el-option label="幽默搞笑" value="humorous" />
                      <el-option label="情感共鸣" value="emotional" />
                      <el-option label="知识科普" value="educational" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="时长">
                    <el-slider v-model="paramsForm.duration" :max="300" show-input />
                  </el-form-item>
                  <el-form-item label="字数限制">
                    <el-slider v-model="paramsForm.wordLimit" :max="2000" show-input />
                  </el-form-item>
                </el-form>
              </div>
            </el-col>
          </el-row>

          <!-- 底部操作栏 -->
          <div class="bottom-action-bar">
            <el-button
              type="primary"
              size="large"
              class="generate-main-btn"
              :loading="generating"
              @click="startGenerate"
            >
              <el-icon v-if="!generating"><VideoPlay /></el-icon>
              {{ generating ? '生成中...' : '开始生成' }}
            </el-button>
            <div v-if="generating" class="progress-info">
              <el-progress
                :percentage="generateProgress"
                :stroke-width="8"
                style="width: 200px"
              />
              <span class="progress-text">{{ generateProgress }}%</span>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ═══════════════════════════════════════════════════════════════
           Tab 2 — 发布管理
           ═══════════════════════════════════════════════════════════════ -->
      <el-tab-pane label="发布管理" name="publish">
        <div class="tab-content publish-tab">
          <!-- 筛选栏 -->
          <div class="filter-bar">
            <el-select v-model="publishFilter.status" placeholder="状态" clearable>
              <el-option label="全部" value="" />
              <el-option label="草稿" value="draft" />
              <el-option label="待审核" value="reviewing" />
              <el-option label="已排期" value="scheduled" />
              <el-option label="已发布" value="published" />
              <el-option label="已驳回" value="rejected" />
            </el-select>
            <el-select v-model="publishFilter.platform" placeholder="平台" clearable>
              <el-option label="全部" value="" />
              <el-option label="抖音" value="douyin" />
              <el-option label="小红书" value="xhs" />
              <el-option label="B站" value="bilibili" />
              <el-option label="快手" value="kuaishou" />
              <el-option label="微信" value="wechat" />
            </el-select>
            <el-input
              v-model="publishFilter.search"
              placeholder="按内容标题搜索"
              clearable
              style="width: 240px"
            />
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon> 新建内容
            </el-button>
          </div>

          <!-- 内容列表 -->
          <el-table
            :data="filteredPublishList"
            stripe
            class="publish-table"
            @row-click="handleRowExpand"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-detail">
                  <el-descriptions :column="2" border>
                    <el-descriptions-item label="ID">{{ row.id }}</el-descriptions-item>
                    <el-descriptions-item label="创建时间">{{ row.createdAt }}</el-descriptions-item>
                    <el-descriptions-item label="平台">{{ platformLabels(row.platforms) }}</el-descriptions-item>
                    <el-descriptions-item label="状态">{{ statusLabel(row.status) }}</el-descriptions-item>
                    <el-descriptions-item label="排期时间">{{ row.scheduledAt || '未排期' }}</el-descriptions-item>
                    <el-descriptions-item label="内容摘要">{{ row.summary || '暂无摘要' }}</el-descriptions-item>
                  </el-descriptions>
                  <div class="expand-actions">
                    <el-tag
                      v-for="(step, i) in statusFlow(row.status)"
                      :key="i"
                      :type="step.type"
                      class="flow-tag"
                    >
                      {{ step.label }}
                    </el-tag>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="标题" min-width="200">
              <template #default="{ row }">
                <span class="title-text">{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column label="平台" width="180">
              <template #default="{ row }">
                <el-tag
                  v-for="p in row.platforms"
                  :key="p"
                  size="small"
                  class="platform-tag"
                >
                  {{ platformMap[p] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="排期时间" width="160">
              <template #default="{ row }">
                {{ row.scheduledAt || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click.stop="editContent(row)">编辑</el-button>
                <el-button
                  v-if="row.status === 'draft'"
                  link
                  type="success"
                  @click.stop="submitReview(row)"
                >提交审核</el-button>
                <el-button
                  v-if="row.status === 'reviewing'"
                  link
                  type="warning"
                  @click.stop="approveContent(row)"
                >通过</el-button>
                <el-button
                  v-if="row.status === 'scheduled'"
                  link
                  type="primary"
                  @click.stop="publishNow(row)"
                >立即发布</el-button>
                <el-button
                  v-if="row.status === 'published'"
                  link
                  type="info"
                  @click.stop="unpublish(row)"
                >下架</el-button>
                <el-button link type="danger" @click.stop="deleteContent(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="publishPage"
            :page-size="10"
            :total="filteredPublishList.length"
            layout="prev, pager, next"
            class="pagination-bar"
          />
        </div>
      </el-tab-pane>

      <!-- ═══════════════════════════════════════════════════════════════
           Tab 3 — 素材库
           ═══════════════════════════════════════════════════════════════ -->
      <el-tab-pane label="素材库" name="assets">
        <div class="tab-content assets-tab">
          <!-- 子标签切换 -->
          <el-radio-group v-model="assetSubTab" class="asset-sub-tabs">
            <el-radio-button label="materials">我的素材</el-radio-button>
            <el-radio-button label="templates">预设模板</el-radio-button>
          </el-radio-group>

          <!-- 我的素材 -->
          <template v-if="assetSubTab === 'materials'">
            <!-- 拖拽上传区域 -->
            <div
              class="upload-drop-zone"
              :class="{ dragging: isDragging }"
              @dragenter.prevent="isDragging = true"
              @dragleave.prevent="isDragging = false"
              @dragover.prevent
              @drop.prevent="handleDrop"
              @click="triggerFileInput"
            >
              <el-icon :size="40"><Upload /></el-icon>
              <div class="upload-text">拖拽文件到此处或点击上传</div>
              <div class="upload-hint">支持图片、视频、文档、音频</div>
              <input
                ref="fileInputRef"
                type="file"
                multiple
                accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.txt"
                style="display: none"
                @change="handleFileSelect"
              />
            </div>

            <!-- 筛选区 -->
            <div class="asset-filter-bar">
              <el-select v-model="materialFilter.type" placeholder="类型" clearable>
                <el-option label="全部" value="" />
                <el-option label="图片" value="image" />
                <el-option label="视频" value="video" />
                <el-option label="文档" value="document" />
                <el-option label="音频" value="audio" />
              </el-select>
              <el-select v-model="materialFilter.platform" placeholder="平台" clearable>
                <el-option label="全部" value="" />
                <el-option label="抖音" value="douyin" />
                <el-option label="小红书" value="xhs" />
                <el-option label="B站" value="bilibili" />
                <el-option label="快手" value="kuaishou" />
                <el-option label="微信" value="wechat" />
                <el-option label="通用" value="all" />
              </el-select>
              <el-input
                v-model="materialFilter.tagSearch"
                placeholder="按标签搜索"
                clearable
                style="width: 200px"
              />
            </div>

            <!-- 素材卡片网格 -->
            <el-row :gutter="16" class="material-grid">
              <el-col
                v-for="m in filteredMaterials"
                :key="m.id"
                :xs="12"
                :sm="8"
                :md="6"
                :lg="4"
              >
                <div class="material-card">
                  <div class="material-thumb" :style="thumbStyle(m.type)">
                    <el-icon :size="32"><component :is="fileIcon(m.type)" /></el-icon>
                    <div class="material-type-label">{{ typeLabel(m.type) }}</div>
                  </div>
                  <div class="material-info">
                    <div class="material-name" :title="m.name">{{ m.name }}</div>
                    <div class="material-tags">
                      <el-tag
                        v-for="tag in m.tags"
                        :key="tag"
                        size="small"
                        class="material-tag"
                      >
                        {{ tag }}
                      </el-tag>
                    </div>
                    <div class="material-meta">
                      <span>{{ platformMap[m.platform] || '通用' }}</span>
                      <span>{{ m.createdAt }}</span>
                    </div>
                  </div>
                  <div class="material-actions">
                    <el-button link type="primary" @click="previewMaterial(m)">
                      <el-icon><View /></el-icon>
                    </el-button>
                    <el-button link type="danger" @click="deleteMaterial(m)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                    <el-button link type="success" @click="useMaterial(m)">
                      <el-icon><Check /></el-icon>
                    </el-button>
                  </div>
                </div>
              </el-col>
            </el-row>
          </template>

          <!-- 预设模板 -->
          <template v-else>
            <el-row :gutter="16" class="preset-grid">
              <el-col
                v-for="t in presetTemplates"
                :key="t.id"
                :xs="12"
                :sm="8"
                :md="6"
                :lg="6"
              >
                <el-card class="preset-card" shadow="hover">
                  <div class="preset-cover" :style="coverStyle(t.color)">
                    <el-icon :size="36"><component :is="t.icon" /></el-icon>
                  </div>
                  <div class="preset-name">{{ t.name }}</div>
                  <div class="preset-scene">{{ t.scene }}</div>
                  <el-button type="primary" text @click="usePreset(t)">使用模板</el-button>
                </el-card>
              </el-col>
            </el-row>
          </template>
        </div>
      </el-tab-pane>

      <!-- ═══════════════════════════════════════════════════════════════
           Tab 4 — 链接仿写
           ═══════════════════════════════════════════════════════════════ -->
      <el-tab-pane label="链接仿写" name="rewrite">
        <div class="tab-content rewrite-tab">
          <el-row :gutter="20">
            <el-col :span="12">
              <div class="rewrite-section">
                <div class="section-title">输入视频链接</div>
                <el-input
                  v-model="rewriteForm.url"
                  placeholder="粘贴抖音/小红书/B站/快手视频链接..."
                  size="large"
                  clearable
                />
                <el-button
                  type="primary"
                  class="ai-btn"
                  :loading="rewriteLoading"
                  @click="analyzeVideo"
                  style="margin-top: 12px"
                >
                  <el-icon><VideoPlay /></el-icon> 解析视频并仿写
                </el-button>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="rewrite-section">
                <div class="section-title">仿写结果</div>
                <div v-if="rewriteLoading" class="rewrite-loading">
                  <el-icon class="is-loading"><Loading /></el-icon>
                  正在解析视频内容并生成仿写文案...
                </div>
                <div v-else-if="rewriteResult" class="rewrite-result">
                  <div class="result-block">
                    <div class="result-label">原始文案（ASR识别）</div>
                    <div class="result-text original">{{ rewriteResult.original }}</div>
                  </div>
                  <div class="result-block">
                    <div class="result-label">仿写文案</div>
                    <div class="result-text rewritten">{{ rewriteResult.rewritten }}</div>
                  </div>
                  <el-button type="primary" plain @click="useRewrittenResult">使用此文案</el-button>
                </div>
                <el-empty v-else :image-size="60" description="输入链接后点击解析" />
              </div>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建内容对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建内容" width="600px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="createForm.title" placeholder="输入内容标题" />
        </el-form-item>
        <el-form-item label="平台">
          <el-checkbox-group v-model="createForm.platforms">
            <el-checkbox label="douyin">抖音</el-checkbox>
            <el-checkbox label="xhs">小红书</el-checkbox>
            <el-checkbox label="bilibili">B站</el-checkbox>
            <el-checkbox label="kuaishou">快手</el-checkbox>
            <el-checkbox label="wechat">微信</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="排期时间">
          <el-date-picker
            v-model="createForm.scheduledAt"
            type="datetime"
            placeholder="选择发布时间"
          />
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="createForm.content"
            type="textarea"
            :rows="4"
            placeholder="输入内容正文"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCreate">保存草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import {
  Microphone, Goods, Reading, Film, Collection,
  MagicStick, VideoPlay, Picture, Loading, Plus,
  Upload, View, Delete, Check, Document, Headset, VideoCamera
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

// ═══════════════════════════════════════════════════════════════════
// 全局状态
// ═══════════════════════════════════════════════════════════════════
const activeTab = ref('produce')

// ═══════════════════════════════════════════════════════════════════
// Tab 1 — 内容生产
// ═══════════════════════════════════════════════════════════════════
const templates = [
  { id: 1, name: '口播', desc: '真人出镜讲解', icon: 'Microphone' },
  { id: 2, name: '产品展示', desc: '产品卖点展示', icon: 'Goods' },
  { id: 3, name: '知识科普', desc: '知识干货分享', icon: 'Reading' },
  { id: 4, name: '剧情', desc: '短剧/情景演绎', icon: 'Film' },
  { id: 5, name: '图文集', desc: '多图轮播展示', icon: 'Collection' },
]
const selectedTemplate = ref(1)
const stepIndex = ref(0)

const topicForm = reactive({
  theme: '',
  recommended: []
})
const scriptForm = reactive({ content: '' })
const generateForm = reactive({ format: '图文', duration: 60, wordLimit: 500 })
const paramsForm = reactive({
  platforms: ['douyin'],
  style: 'casual',
  duration: 60,
  wordLimit: 500
})

const generating = ref(false)
const generateProgress = ref(0)
let progressTimer = null

function aiRecommendTopic() {
  if (!topicForm.theme.trim()) {
    ElMessage.info('请先输入主题方向')
    return
  }
  topicForm.recommended = [
    `${topicForm.theme}入门指南`,
    `${topicForm.theme}避坑大全`,
    `2026年${topicForm.theme}趋势`,
    `${topicForm.theme} vs 传统方案`,
  ]
  ElMessage.success('AI 已推荐 4 个选题方向')
}

function aiGenerateScript() {
  if (!topicForm.theme && !scriptForm.content) {
    ElMessage.info('请先输入主题或脚本大纲')
    return
  }
  const theme = topicForm.theme || '相关内容'
  scriptForm.content = `【开场】大家好！今天我们来聊聊「${theme}」。\n\n` +
    `【正文】首先，${theme} 的核心优势在于...\n` +
    `其次，在实际应用中，我们需要注意以下几点：\n` +
    `1. 明确目标受众\n` +
    `2. 选择合适的表达方式\n` +
    `3. 持续优化内容质量\n\n` +
    `【结尾】以上就是关于 ${theme} 的全部内容，觉得有帮助的话记得点赞收藏！`
  ElMessage.success('AI 脚本已生成')
}

function startGenerate() {
  if (generating.value) return
  generating.value = true
  generateProgress.value = 0
  stepIndex.value = 3
  progressTimer = setInterval(() => {
    generateProgress.value += Math.floor(Math.random() * 15) + 5
    if (generateProgress.value >= 100) {
      generateProgress.value = 100
      clearInterval(progressTimer)
      setTimeout(() => {
        generating.value = false
        ElMessage.success('内容生成完成！')
      }, 600)
    }
  }, 400)
}

// ═══════════════════════════════════════════════════════════════════
// Tab 4 — 链接仿写
// ═══════════════════════════════════════════════════════════════════
const rewriteForm = reactive({ url: '' })
const rewriteLoading = ref(false)
const rewriteResult = ref(null)

async function analyzeVideo() {
  if (!rewriteForm.url.trim()) {
    ElMessage.warning('请输入视频链接')
    return
  }
  rewriteLoading.value = true
  rewriteResult.value = null
  try {
    const { data } = await axios.post('/api/acquisition/search', {
      keyword: rewriteForm.url.trim(),
      platforms: ['douyin', 'xhs', 'bilibili', 'kuaishou'],
      limit: 1,
    })
    const video = data.videos?.[0]
    const originalText = video?.description || video?.title || '（未能提取视频文案）'
    const { data: aiData } = await axios.post('/api/publisher/ai-generate', {
      type: 'rewrite',
      content: originalText,
      instruction: '仿写以上文案，保持结构和节奏，替换具体内容为护肤产品相关',
    })
    rewriteResult.value = {
      original: originalText,
      rewritten: aiData.content || aiData.text || '（仿写失败，请重试）',
    }
    ElMessage.success('视频解析并仿写完成')
  } catch (e) {
    ElMessage.error('解析失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    rewriteLoading.value = false
  }
}

function useRewrittenResult() {
  if (rewriteResult.value?.rewritten) {
    scriptForm.content = rewriteResult.value.rewritten
    activeTab.value = 'produce'
    stepIndex.value = 1
    ElMessage.success('已填入脚本编辑区')
  }
}

// ═══════════════════════════════════════════════════════════════════
// Tab 2 — 发布管理
// ═══════════════════════════════════════════════════════════════════
const publishFilter = reactive({ status: '', platform: '', search: '' })
const publishPage = ref(1)
const showCreateDialog = ref(false)
const createForm = reactive({ title: '', platforms: [], scheduledAt: null, content: '' })

const platformMap = {
  douyin: '抖音', xhs: '小红书', bilibili: 'B站', kuaishou: '快手', wechat: '微信', all: '通用'
}
const statusMap = {
  draft: '草稿', reviewing: '待审核', scheduled: '已排期', published: '已发布', rejected: '已驳回'
}
const statusTypeMap = {
  draft: 'info', reviewing: 'warning', scheduled: 'primary', published: 'success', rejected: 'danger'
}

const publishList = ref([])

async function loadContents() {
  try {
    const { data } = await axios.get('/api/publisher/contents')
    const arr = Array.isArray(data) ? data : (data.data || [])
    publishList.value = arr.map(c => ({
      ...c,
      platforms: (c.platforms || []).map(p => typeof p === 'string' ? p : p.value),
      status: c.status === 'pending' ? 'reviewing' : c.status,
    }))
  } catch (e) {
    ElMessage.error('加载内容列表失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadContents()
})

const filteredPublishList = computed(() => {
  return publishList.value.filter(item => {
    if (publishFilter.status && item.status !== publishFilter.status) return false
    if (publishFilter.platform && !item.platforms.includes(publishFilter.platform)) return false
    if (publishFilter.search && !item.title.includes(publishFilter.search)) return false
    return true
  })
})

function statusLabel(s) { return statusMap[s] || s }
function statusType(s) { return statusTypeMap[s] || 'info' }
function platformLabels(arr) { return arr.map(p => platformMap[p]).join('、') }

function statusFlow(status) {
  const flow = [
    { label: '草稿', type: 'info' },
    { label: '提交', type: 'info' },
    { label: '审核中', type: 'warning' },
    { label: '通过/驳回', type: 'info' },
    { label: '排期', type: 'primary' },
    { label: '发布', type: 'success' },
  ]
  const idx = { draft: 0, reviewing: 2, scheduled: 4, published: 5, rejected: 3 }[status]
  return flow.map((f, i) => ({ ...f, type: i <= idx ? 'success' : 'info' }))
}

function handleRowExpand() { /* row click expand handled by el-table */ }

async function editContent(row) { ElMessage.info(`编辑「${row.title}」`) }
async function submitReview(row) {
  try {
    await axios.post(`/api/publisher/contents/${row.id}/submit`)
    row.status = 'reviewing'
    ElMessage.success('已提交审核')
  } catch (e) {
    ElMessage.error('提交失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function approveContent(row) {
  try {
    await axios.post(`/api/publisher/contents/${row.id}/approve`)
    row.status = 'scheduled'
    ElMessage.success('审核通过')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function publishNow(row) {
  try {
    await axios.post(`/api/publisher/contents/${row.id}/publish`)
    row.status = 'published'
    ElMessage.success('已发布')
  } catch (e) {
    ElMessage.error('发布失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function unpublish(row) {
  try {
    await axios.put(`/api/publisher/contents/${row.id}`, null, { params: { body: '' } })
    row.status = 'draft'
    ElMessage.info('已下架')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}
async function deleteContent(row) {
  try {
    await ElMessageBox.confirm(`确认删除「${row.title}」？`, '删除确认', { type: 'warning' })
    await axios.delete(`/api/publisher/contents/${row.id}`)
    publishList.value = publishList.value.filter(p => p.id !== row.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}
async function saveCreate() {
  try {
    const { data } = await axios.post('/api/publisher/contents', null, {
      params: {
        title: createForm.title || '未命名内容',
        body: createForm.content || '',
        platforms: (createForm.platforms.length ? createForm.platforms : ['douyin']).join(','),
      }
    })
    publishList.value.unshift(data)
    showCreateDialog.value = false
    ElMessage.success('草稿已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
  }
}
function formatDate(d) {
  const dt = new Date(d)
  const pad = n => String(n).padStart(2, '0')
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())} ${pad(dt.getHours())}:${pad(dt.getMinutes())}`
}

// ═══════════════════════════════════════════════════════════════════
// Tab 3 — 素材库
// ═══════════════════════════════════════════════════════════════════
const assetSubTab = ref('materials')
const isDragging = ref(false)
const fileInputRef = ref(null)

const materialFilter = reactive({ type: '', platform: '', tagSearch: '' })

const materials = ref([])

async function loadMaterials() {
  try {
    const { data } = await axios.get('/api/publisher/materials')
    materials.value = data.materials || []
  } catch (e) {
    ElMessage.error('加载素材失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadContents()
  loadMaterials()
})

const filteredMaterials = computed(() => {
  return materials.value.filter(m => {
    if (materialFilter.type && m.type !== materialFilter.type) return false
    if (materialFilter.platform && m.platform !== materialFilter.platform) return false
    if (materialFilter.tagSearch && !m.tags.some(t => t.includes(materialFilter.tagSearch))) return false
    return true
  })
})

const typeColorMap = { image: '#22c55e', video: '#7c3aed', audio: '#f59e0b', document: '#4f46e5' }
const typeLabelMap = { image: '图片', video: '视频', audio: '音频', document: '文档' }
const typeIconMap = { image: 'Picture', video: 'VideoCamera', audio: 'Headset', document: 'Document' }

function typeLabel(t) { return typeLabelMap[t] || t }
function fileIcon(t) { return typeIconMap[t] || 'Document' }
function thumbStyle(t) { return { background: `linear-gradient(135deg, ${typeColorMap[t]}22, ${typeColorMap[t]}44)`, color: typeColorMap[t] } }

function triggerFileInput() { fileInputRef.value?.click() }
async function handleDrop(e) {
  isDragging.value = false
  const files = Array.from(e.dataTransfer.files)
  await Promise.all(files.map(file => addMaterial(file.name)))
  ElMessage.success(`已上传 ${files.length} 个文件`)
}
async function handleFileSelect(e) {
  const files = Array.from(e.target.files)
  await Promise.all(files.map(file => addMaterial(file.name)))
  ElMessage.success(`已上传 ${files.length} 个文件`)
  e.target.value = ''
}
async function addMaterial(name) {
  const ext = name.split('.').pop()?.toLowerCase() || ''
  const typeMap = { jpg: 'image', png: 'image', jpeg: 'image', gif: 'image', mp4: 'video', mov: 'video', mp3: 'audio', wav: 'audio', pdf: 'document', doc: 'document', docx: 'document', txt: 'document' }
  const type = typeMap[ext] || 'document'
  try {
    const { data } = await axios.post('/api/publisher/materials', { name, type, tags: ['新上传'], platform: 'all' })
    materials.value.unshift(data)
  } catch (e) {
    ElMessage.error(`「${name}」上传失败: ` + (e.response?.data?.detail || e.message))
  }
}
function previewMaterial(m) { ElMessage.info(`预览「${m.name}」`) }
async function deleteMaterial(m) {
  try {
    await ElMessageBox.confirm(`确认删除「${m.name}」？`, '删除确认', { type: 'warning' })
    await axios.delete(`/api/publisher/materials/${m.id}`)
    materials.value = materials.value.filter(x => x.id !== m.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}
function useMaterial(m) { ElMessage.success(`已使用「${m.name}」`) }

const presetTemplates = [
  { id: 1, name: '口播模板', scene: '适用于产品讲解、知识分享', icon: 'Microphone', color: '#4f46e5' },
  { id: 2, name: '产品展示', scene: '适用于新品发布、功能介绍', icon: 'Goods', color: '#22c55e' },
  { id: 3, name: '知识科普', scene: '适用于行业知识、教程讲解', icon: 'Reading', color: '#7c3aed' },
  { id: 4, name: '剧情短剧', scene: '适用于品牌故事、情景演绎', icon: 'Film', color: '#f59e0b' },
  { id: 5, name: '图文轮播', scene: '适用于多图展示、对比展示', icon: 'Collection', color: '#ec4899' },
  { id: 6, name: '直播预告', scene: '适用于直播预热、活动预告', icon: 'VideoCamera', color: '#0d9488' },
  { id: 7, name: '用户见证', scene: '适用于客户案例、好评展示', icon: 'Document', color: '#14b8a6' },
  { id: 8, name: '节日营销', scene: '适用于节日活动、促销推广', icon: 'Picture', color: '#f43f5e' },
]
function coverStyle(color) { return { background: `linear-gradient(135deg, ${color}22, ${color}55)`, color } }
function usePreset(t) { ElMessage.success(`已应用「${t.name}」模板`) }
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════════════
   Page Layout
   ═══════════════════════════════════════════════════════════════════ */
.content-studio-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.page-title {
  margin: 0 0 20px;
  font-size: 18px;
  color: var(--text-primary);
  font-weight: 600;
}
.studio-tabs :deep(.el-tabs__content) {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-top: none;
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  padding: 0;
}
.studio-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.tab-content {
  padding: 20px;
}

/* ═══════════════════════════════════════════════════════════════════
   Tab 1 — 内容生产
   ═══════════════════════════════════════════════════════════════════ */
.produce-tab { display: flex; flex-direction: column; gap: 20px; }

/* 模板卡片选择器 */
.template-section { }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}
.template-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
}
.template-card {
  flex: 0 0 160px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
}
.template-card:hover {
  border-color: var(--border-active);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.template-card.selected {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 2px var(--accent-primary), var(--accent-glow);
}
.template-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: var(--accent-light);
  color: var(--accent-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
}
.template-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.template-desc {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* 生产向导 */
.produce-main { margin-top: 4px; }
.wizard-section {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: 20px;
}
.step-content { margin: 20px 0; min-height: 260px; }
.step-panel { display: flex; flex-direction: column; gap: 12px; }
.ai-btn { align-self: flex-start; }
.recommend-list { margin-top: 8px; }
.recommend-title {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}
.recommend-tag { margin: 0 8px 8px 0; cursor: pointer; }
.recommend-tag:hover { color: var(--accent-primary); border-color: var(--accent-primary); }

.generating-area { display: flex; flex-direction: column; gap: 12px; align-items: center; padding: 40px 0; }
.generating-text { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; }

.preview-area { padding: 40px 0; }
.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-tertiary);
  padding: 48px;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
}
.preview-desc { font-size: 12px; }

.step-nav { display: flex; gap: 12px; justify-content: flex-end; }

/* 右侧参数面板 */
.params-panel {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: 20px;
  height: 100%;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

/* 底部操作栏 */
.bottom-action-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  margin-top: 4px;
}
.generate-main-btn {
  min-width: 140px;
}
.progress-info { display: flex; align-items: center; gap: 12px; }
.progress-text { font-size: 13px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }

/* ═══════════════════════════════════════════════════════════════════
   Tab 2 — 发布管理
   ═══════════════════════════════════════════════════════════════════ */
.publish-tab { }
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.publish-table :deep(th) { background: var(--table-header-bg); color: var(--text-primary); font-weight: 600; }
.publish-table :deep(tr:hover) { background: var(--hover-bg) !important; }
.platform-tag { margin: 0 4px 4px 0; }
.title-text { font-weight: 500; color: var(--text-primary); }
.expand-detail { padding: 12px 24px; background: var(--bg-canvas); border-radius: var(--radius-md); }
.expand-actions { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.flow-tag { }
.pagination-bar { margin-top: 16px; justify-content: flex-end; }

/* ═══════════════════════════════════════════════════════════════════
   Tab 3 — 素材库
   ═══════════════════════════════════════════════════════════════════ */
.assets-tab { }
.asset-sub-tabs { margin-bottom: 16px; }

/* 上传区域 */
.upload-drop-zone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: var(--glass-bg);
  margin-bottom: 16px;
}
.upload-drop-zone:hover, .upload-drop-zone.dragging {
  border-color: var(--accent-primary);
  background: var(--accent-light);
  box-shadow: var(--accent-glow-sm);
}
.upload-text { margin-top: 12px; font-size: 14px; color: var(--text-primary); font-weight: 500; }
.upload-hint { margin-top: 4px; font-size: 12px; color: var(--text-tertiary); }

/* 筛选栏 */
.asset-filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

/* 素材卡片 */
.material-grid { }
.material-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: all 0.25s ease;
  position: relative;
  margin-bottom: 16px;
}
.material-card:hover {
  border-color: var(--border-active);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.material-card:hover .material-actions { opacity: 1; }
.material-thumb {
  height: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.25s ease;
}
.material-type-label {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.8;
}
.material-info { padding: 12px; }
.material-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.material-tags { margin-bottom: 8px; }
.material-tag { margin: 0 4px 4px 0; }
.material-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-tertiary);
}
.material-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.25s ease;
  background: var(--bg-overlay);
  border-radius: var(--radius-sm);
  padding: 2px 4px;
}

/* 预设模板 */
.preset-grid { }
.preset-card { text-align: center; padding: 16px; transition: all 0.25s ease; }
.preset-card:hover { border-color: var(--accent-primary); box-shadow: var(--accent-glow); }
.preset-cover {
  height: 120px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}
.preset-name { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
.preset-scene { font-size: 12px; color: var(--text-tertiary); margin-bottom: 12px; }

/* ═══════════════════════════════════════════════════════════════════
   Tab 4 — 链接仿写
   ═══════════════════════════════════════════════════════════════════ */
.rewrite-tab { padding: 24px; }
.rewrite-section { display: flex; flex-direction: column; gap: 12px; }
.rewrite-loading { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); padding: 24px; }
.rewrite-result { display: flex; flex-direction: column; gap: 16px; }
.result-block { background: var(--bg-main); border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; }
.result-label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); margin-bottom: 8px; }
.result-text { font-size: 13px; line-height: 1.7; color: var(--text-primary); }
.result-text.original { color: var(--text-secondary); }
.result-text.rewritten { color: var(--text-primary); }

/* ═══════════════════════════════════════════════════════════════════
   Responsive
   ═══════════════════════════════════════════════════════════════════ */
@media (max-width: 1279px) {
  .produce-main :deep(.el-col-16) { max-width: 100%; flex: 0 0 100%; }
  .produce-main :deep(.el-col-8) { max-width: 100%; flex: 0 0 100%; margin-top: 16px; }
  .template-card { flex: 0 0 140px; }
  .filter-bar { gap: 8px; }
}

@media (max-width: 768px) {
  .content-studio-page { padding: 12px; }
  .template-card { flex: 0 0 120px; padding: 12px; }
  .bottom-action-bar { flex-direction: column; align-items: stretch; }
  .upload-drop-zone { padding: 32px 16px; }
}
</style>
