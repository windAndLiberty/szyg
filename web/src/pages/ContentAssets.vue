<template>
  <div class="content-assets-page">
    <!-- 顶部区域 -->
    <div class="page-header">
      <div class="title-section">
        <h1 class="page-title">内容资产</h1>
        <p class="page-subtitle">历史内容沉淀与效果追踪</p>
      </div>
      <div class="filter-section">
        <el-input
          v-model="searchQuery"
          placeholder="按标题搜索"
          clearable
          class="search-input"
          :prefix-icon="Search"
        />
        <el-select
          v-model="filterPlatforms"
          multiple
          collapse-tags
          placeholder="平台"
          class="filter-item"
        >
          <el-option label="抖音" value="douyin" />
          <el-option label="小红书" value="xhs" />
          <el-option label="快手" value="kuaishou" />
          <el-option label="B站" value="bilibili" />
          <el-option label="视频号" value="videochannel" />
        </el-select>
        <el-date-picker
          v-model="filterDateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          class="filter-item"
          value-format="YYYY-MM-DD"
        />
        <el-select v-model="filterContentType" placeholder="内容类型" clearable class="filter-item">
          <el-option label="图文" value="image_text" />
          <el-option label="视频" value="video" />
          <el-option label="音频" value="audio" />
          <el-option label="文档" value="doc" />
        </el-select>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="border-card" class="content-tabs">
      <!-- 子标签 1 — 成片库 -->
      <el-tab-pane label="成片库" name="videos">
        <el-row :gutter="16" class="card-grid">
          <el-col
            v-for="item in filteredVideos"
            :key="item.id"
            :xs="24"
            :sm="12"
            :md="12"
            :lg="6"
            :xl="6"
          >
            <div class="content-card" @click="openVideoDetail(item)">
              <div class="thumbnail" :class="`type-${item.type}`">
                <el-icon class="type-icon"><VideoCamera /></el-icon>
              </div>
              <div class="card-body">
                <h4 class="card-title">{{ item.title }}</h4>
                <div class="card-tags">
                  <el-tag
                    v-for="p in item.platforms"
                    :key="p"
                    size="small"
                    class="platform-tag"
                  >
                    {{ platformMap[p] || p }}
                  </el-tag>
                </div>
                <div class="card-meta">
                  <span class="meta-date">{{ item.createdAt }}</span>
                </div>
                <div class="card-stats">
                  <span><el-icon><View /></el-icon> {{ formatNumber(item.views) }}</span>
                  <span><el-icon><Star /></el-icon> {{ formatNumber(item.likes) }}</span>
                  <span><el-icon><ChatDotRound /></el-icon> {{ formatNumber(item.comments) }}</span>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 子标签 2 — 文案库 -->
      <el-tab-pane label="文案库" name="copy">
        <el-table
          :data="filteredCopy"
          stripe
          style="width: 100%"
          class="assets-table"
          @row-click="row => openCopyDetail(row)"
        >
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column label="内容摘要" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.content?.slice(0, 50) }}...
            </template>
          </el-table-column>
          <el-table-column label="适用平台" min-width="120">
            <template #default="{ row }">
              <el-tag
                v-for="p in row.platforms"
                :key="p"
                size="small"
                class="platform-tag"
              >
                {{ platformMap[p] || p }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="标签" min-width="120">
            <template #default="{ row }">
              <el-tag
                v-for="tag in row.tags"
                :key="tag"
                size="small"
                type="info"
                class="tag-item"
              >
                {{ tag }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="createdAt" label="创建时间" width="120" />
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click.stop="openCopyDetail(row)">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 子标签 3 — 发布记录 -->
      <el-tab-pane label="发布记录" name="history">
        <el-table :data="filteredPublish" stripe style="width: 100%" class="assets-table">
          <el-table-column prop="title" label="内容标题" min-width="160" show-overflow-tooltip />
          <el-table-column label="平台" min-width="100">
            <template #default="{ row }">
              {{ platformMap[row.platform] || row.platform }}
            </template>
          </el-table-column>
          <el-table-column label="发布状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="publishTime" label="发布时间" width="150" />
          <el-table-column prop="postId" label="平台 post_id" min-width="140" show-overflow-tooltip />
          <el-table-column label="结果" min-width="160">
            <template #default="{ row }">
              <span v-if="row.status === 'success'" class="result-link">
                <el-link type="primary" :href="row.link" target="_blank">查看链接</el-link>
              </span>
              <span v-else-if="row.status === 'failed'" class="result-error">
                {{ row.error }}
              </span>
              <span v-else class="result-pending">—</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 子标签 4 — 效果数据 -->
      <el-tab-pane label="效果数据" name="analytics">
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-label">总播放量</div>
            <div class="stat-value">{{ formatNumber(totalStats.views) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">总点赞</div>
            <div class="stat-value">{{ formatNumber(totalStats.likes) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">总评论</div>
            <div class="stat-value">{{ formatNumber(totalStats.comments) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">总分享</div>
            <div class="stat-value">{{ formatNumber(totalStats.shares) }}</div>
          </div>
        </div>

        <!-- 对比分析面板 -->
        <el-card class="compare-card" shadow="never">
          <template #header>
            <div class="compare-header">
              <span class="compare-title">对比分析</span>
              <el-radio-group v-model="compareDimension" size="small">
                <el-radio-button label="platform">按平台</el-radio-button>
                <el-radio-button label="contentType">按内容类型</el-radio-button>
                <el-radio-button label="time">按时间维度</el-radio-button>
              </el-radio-group>
            </div>
          </template>

          <!-- 按平台 -->
          <div v-if="compareDimension === 'platform'">
            <div class="bar-chart">
              <div v-for="item in platformStats" :key="item.platform" class="bar-row">
                <div class="bar-label">{{ platformMap[item.platform] || item.platform }}</div>
                <div class="bar-metrics">
                  <div class="bar-metric">
                    <span class="bar-metric-label">播放</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.totalViews, maxPlatformMetrics.totalViews), background: platformColors[item.platform] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ formatNumber(item.totalViews) }}</span>
                  </div>
                  <div class="bar-metric">
                    <span class="bar-metric-label">点赞</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.totalLikes, maxPlatformMetrics.totalLikes), background: platformColors[item.platform] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ formatNumber(item.totalLikes) }}</span>
                  </div>
                  <div class="bar-metric">
                    <span class="bar-metric-label">评论</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.totalComments, maxPlatformMetrics.totalComments), background: platformColors[item.platform] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ formatNumber(item.totalComments) }}</span>
                  </div>
                  <div class="bar-metric">
                    <span class="bar-metric-label">互动率</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.engagementRate, 15), background: platformColors[item.platform] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ item.engagementRate }}%</span>
                  </div>
                </div>
              </div>
            </div>

            <el-table :data="platformStats" stripe style="width: 100%" class="compare-table">
              <el-table-column prop="platform" label="平台" min-width="100">
                <template #default="{ row }">
                  <span class="platform-dot" :style="{ background: platformColors[row.platform] || '#999' }"></span>
                  {{ platformMap[row.platform] || row.platform }}
                </template>
              </el-table-column>
              <el-table-column prop="contentCount" label="内容数" width="90" sortable />
              <el-table-column prop="totalViews" label="总播放" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.totalViews) }}</template>
              </el-table-column>
              <el-table-column prop="totalLikes" label="总点赞" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.totalLikes) }}</template>
              </el-table-column>
              <el-table-column prop="totalComments" label="总评论" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.totalComments) }}</template>
              </el-table-column>
              <el-table-column prop="avgViews" label="平均播放" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.avgViews) }}</template>
              </el-table-column>
              <el-table-column prop="engagementRate" label="互动率" width="100" sortable>
                <template #default="{ row }">{{ row.engagementRate }}%</template>
              </el-table-column>
              <el-table-column prop="conversionRate" label="转化率" width="100" sortable>
                <template #default="{ row }">{{ row.conversionRate }}%</template>
              </el-table-column>
            </el-table>
            <div class="compare-total-row">
              <span class="total-label">总计</span>
              <span class="total-cell">{{ platformTableTotal.contentCount }}</span>
              <span class="total-cell">{{ formatNumber(platformTableTotal.totalViews) }}</span>
              <span class="total-cell">{{ formatNumber(platformTableTotal.totalLikes) }}</span>
              <span class="total-cell">{{ formatNumber(platformTableTotal.totalComments) }}</span>
              <span class="total-cell">—</span>
              <span class="total-cell">—</span>
              <span class="total-cell">—</span>
            </div>
          </div>

          <!-- 按内容类型 -->
          <div v-else-if="compareDimension === 'contentType'">
            <div class="bar-chart">
              <div v-for="item in contentTypeStats" :key="item.type" class="bar-row">
                <div class="bar-label">{{ item.typeLabel }}</div>
                <div class="bar-metrics">
                  <div class="bar-metric">
                    <span class="bar-metric-label">播放</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.totalViews, maxTypeMetrics.totalViews), background: typeColors[item.type] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ formatNumber(item.totalViews) }}</span>
                  </div>
                  <div class="bar-metric">
                    <span class="bar-metric-label">点赞</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.totalLikes, maxTypeMetrics.totalLikes), background: typeColors[item.type] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ formatNumber(item.totalLikes) }}</span>
                  </div>
                  <div class="bar-metric">
                    <span class="bar-metric-label">评论</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.totalComments, maxTypeMetrics.totalComments), background: typeColors[item.type] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ formatNumber(item.totalComments) }}</span>
                  </div>
                  <div class="bar-metric">
                    <span class="bar-metric-label">转化率</span>
                    <div class="bar-track">
                      <div class="bar-fill" :style="{ width: barWidth(item.conversionRate, 5), background: typeColors[item.type] || '#0ea5e9' }"></div>
                    </div>
                    <span class="bar-metric-value">{{ item.conversionRate }}%</span>
                  </div>
                </div>
              </div>
            </div>

            <el-table :data="contentTypeStats" stripe style="width: 100%" class="compare-table">
              <el-table-column prop="typeLabel" label="内容类型" min-width="100" />
              <el-table-column prop="contentCount" label="内容数" width="90" sortable />
              <el-table-column prop="totalViews" label="总播放" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.totalViews) }}</template>
              </el-table-column>
              <el-table-column prop="totalLikes" label="总点赞" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.totalLikes) }}</template>
              </el-table-column>
              <el-table-column prop="totalComments" label="总评论" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.totalComments) }}</template>
              </el-table-column>
              <el-table-column prop="avgViews" label="平均播放" width="110" sortable>
                <template #default="{ row }">{{ formatNumber(row.avgViews) }}</template>
              </el-table-column>
              <el-table-column prop="engagementRate" label="互动率" width="100" sortable>
                <template #default="{ row }">{{ row.engagementRate }}%</template>
              </el-table-column>
              <el-table-column prop="conversionRate" label="转化率" width="100" sortable>
                <template #default="{ row }">{{ row.conversionRate }}%</template>
              </el-table-column>
            </el-table>
            <div class="compare-total-row">
              <span class="total-label">总计</span>
              <span class="total-cell">{{ typeTableTotal.contentCount }}</span>
              <span class="total-cell">{{ formatNumber(typeTableTotal.totalViews) }}</span>
              <span class="total-cell">{{ formatNumber(typeTableTotal.totalLikes) }}</span>
              <span class="total-cell">{{ formatNumber(typeTableTotal.totalComments) }}</span>
              <span class="total-cell">—</span>
              <span class="total-cell">—</span>
              <span class="total-cell">—</span>
            </div>
          </div>

          <!-- 按时间维度 -->
          <div v-else-if="compareDimension === 'time'" class="trend-panel">
            <div class="trend-legend">
              <span class="legend-item"><span class="legend-dot" style="background:#0ea5e9"></span>发布数</span>
              <span class="legend-item"><span class="legend-dot" style="background:#8b5cf6"></span>播放数</span>
              <span class="legend-item"><span class="legend-dot" style="background:#f59e0b"></span>互动数</span>
            </div>
            <div class="trend-chart">
              <div class="trend-col" v-for="(item, idx) in timeTrendData" :key="item.date">
                <div class="trend-bars">
                  <div class="trend-bar publish" :style="{ height: lineHeight(item.publishCount, timeTrendMax.publishCount) }"></div>
                  <div class="trend-bar views" :style="{ height: lineHeight(item.views, timeTrendMax.views) }"></div>
                  <div class="trend-bar interactions" :style="{ height: lineHeight(item.interactions, timeTrendMax.interactions) }"></div>
                </div>
                <div class="trend-date">{{ item.date }}</div>
                <div class="trend-tip">
                  <div>发布: {{ item.publishCount }}</div>
                  <div>播放: {{ formatNumber(item.views) }}</div>
                  <div>互动: {{ formatNumber(item.interactions) }}</div>
                </div>
              </div>
            </div>
            <div class="trend-table-wrapper">
              <el-table :data="timeTrendData" stripe style="width: 100%" class="compare-table">
                <el-table-column prop="date" label="日期" width="100" />
                <el-table-column prop="publishCount" label="发布数" width="100" sortable />
                <el-table-column prop="views" label="播放数" width="120" sortable>
                  <template #default="{ row }">{{ formatNumber(row.views) }}</template>
                </el-table-column>
                <el-table-column prop="interactions" label="互动数" width="120" sortable>
                  <template #default="{ row }">{{ formatNumber(row.interactions) }}</template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-card>

        <el-table
          :data="filteredAnalytics"
          stripe
          style="width: 100%"
          class="assets-table"
          @sort-change="handleSort"
        >
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip sortable />
          <el-table-column label="平台" min-width="100">
            <template #default="{ row }">
              <span v-for="p in row.platforms" :key="p" class="platform-text">
                {{ platformMap[p] || p }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="views" label="播放" width="110" sortable>
            <template #default="{ row }">
              {{ formatNumber(row.views) }}
            </template>
          </el-table-column>
          <el-table-column prop="likes" label="点赞" width="110" sortable>
            <template #default="{ row }">
              {{ formatNumber(row.likes) }}
            </template>
          </el-table-column>
          <el-table-column prop="comments" label="评论" width="110" sortable>
            <template #default="{ row }">
              {{ formatNumber(row.comments) }}
            </template>
          </el-table-column>
          <el-table-column prop="shares" label="分享" width="110" sortable>
            <template #default="{ row }">
              {{ formatNumber(row.shares) }}
            </template>
          </el-table-column>
          <el-table-column prop="conversionRate" label="转化率" width="110" sortable>
            <template #default="{ row }">
              {{ row.conversionRate }}%
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 成片详情 Drawer -->
    <el-drawer
      v-model="videoDrawerVisible"
      title="内容详情"
      size="480"
      :destroy-on-close="true"
      class="detail-drawer"
    >
      <div v-if="selectedVideo" class="drawer-content">
        <div class="detail-thumbnail" :class="`type-${selectedVideo.type}`">
          <el-icon class="detail-type-icon"><VideoCamera /></el-icon>
        </div>
        <h3 class="detail-title">{{ selectedVideo.title }}</h3>
        <p class="detail-desc">{{ selectedVideo.description }}</p>
        <div class="detail-stats-row">
          <div class="detail-stat">
            <div class="detail-stat-label">播放</div>
            <div class="detail-stat-value">{{ formatNumber(selectedVideo.views) }}</div>
          </div>
          <div class="detail-stat">
            <div class="detail-stat-label">点赞</div>
            <div class="detail-stat-value">{{ formatNumber(selectedVideo.likes) }}</div>
          </div>
          <div class="detail-stat">
            <div class="detail-stat-label">评论</div>
            <div class="detail-stat-value">{{ formatNumber(selectedVideo.comments) }}</div>
          </div>
          <div class="detail-stat">
            <div class="detail-stat-label">分享</div>
            <div class="detail-stat-value">{{ formatNumber(selectedVideo.shares) }}</div>
          </div>
          <div class="detail-stat">
            <div class="detail-stat-label">收藏</div>
            <div class="detail-stat-value">{{ formatNumber(selectedVideo.favorites || 0) }}</div>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">平台标签</div>
          <div class="detail-tags">
            <el-tag
              v-for="p in selectedVideo.platforms"
              :key="p"
              class="platform-tag"
            >
              {{ platformMap[p] || p }}
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">原内容链接</div>
          <div class="detail-link">https://example.com/content/{{ selectedVideo.id }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">创建时间</div>
          <div class="detail-text">{{ selectedVideo.createdAt }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">最后修改</div>
          <div class="detail-text">{{ selectedVideo.updatedAt || selectedVideo.createdAt }}</div>
        </div>
      </div>
    </el-drawer>

    <!-- 文案详情 Drawer -->
    <el-drawer
      v-model="copyDrawerVisible"
      title="文案详情"
      size="480"
      :destroy-on-close="true"
      class="detail-drawer"
    >
      <div v-if="selectedCopy" class="drawer-content">
        <h3 class="detail-title">{{ selectedCopy.title }}</h3>
        <div class="detail-section">
          <div class="detail-label">正文</div>
          <div class="detail-body">{{ selectedCopy.content }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">标签</div>
          <div class="detail-tags">
            <el-tag
              v-for="tag in selectedCopy.tags"
              :key="tag"
              type="info"
              class="tag-item"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">使用次数</div>
          <div class="detail-text">{{ selectedCopy.useCount || 0 }} 次</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">创建时间</div>
          <div class="detail-text">{{ selectedCopy.createdAt }}</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import {
  Search, VideoCamera, View, Star, ChatDotRound
} from '@element-plus/icons-vue'

const activeTab = ref('videos')
const searchQuery = ref('')
const filterPlatforms = ref([])
const filterDateRange = ref([])
const filterContentType = ref('')

const videoDrawerVisible = ref(false)
const selectedVideo = ref(null)
const copyDrawerVisible = ref(false)
const selectedCopy = ref(null)

const contentAssets = ref([])
const copyLibrary = ref([])
const publishRecords = ref([])

async function loadAssets() {
  try {
    const [{ data: assets }, { data: copy }, { data: records }] = await Promise.all([
      axios.get('/api/publisher/content-assets'),
      axios.get('/api/publisher/copy-library'),
      axios.get('/api/publisher/logs'),
    ])
    contentAssets.value = assets.items || []
    copyLibrary.value = copy.items || []
    publishRecords.value = Array.isArray(records) ? records : (records.logs || [])
  } catch (e) {
    ElMessage.error('加载资产数据失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadAssets()
  loadAnalytics()
})

const platformMap = {
  douyin: '抖音',
  xhs: '小红书',
  kuaishou: '快手',
  bilibili: 'B站',
  videochannel: '视频号',
  weibo: '微博',
  wechat: '微信'
}

const statusType = (status) => {
  const map = { success: 'success', failed: 'danger', scheduled: 'warning' }
  return map[status] || 'info'
}
const statusText = (status) => {
  const map = { success: '成功', failed: '失败', scheduled: '排期中' }
  return map[status] || status
}

// ========== 对比分析 ==========
const compareDimension = ref('platform')

const platformStats = ref([])
const contentTypeStats = ref([])
const timeTrendData = ref([])

async function loadAnalytics() {
  try {
    // Load publisher stats for content counts
    const [pubRes, contentsRes] = await Promise.allSettled([
      axios.get('/api/publisher/stats'),
      axios.get('/api/publisher/contents'),
    ])
    const pubStats = pubRes.status === 'fulfilled' ? (pubRes.value.data || {}) : {}
    const contents = contentsRes.status === 'fulfilled' ? (contentsRes.value.data || []) : []

    // Platform stats: aggregate contents by platform
    const byPlatform = {}
    for (const c of (Array.isArray(contents) ? contents : [])) {
      const platforms = c.platforms || [c.platform].filter(Boolean)
      for (const p of platforms) {
        if (!byPlatform[p]) byPlatform[p] = { contentCount: 0, totalViews: 0, totalLikes: 0, totalComments: 0 }
        byPlatform[p].contentCount++
      }
    }
    platformStats.value = Object.entries(byPlatform).map(([platform, stats]) => ({
      platform, ...stats, avgViews: 0, engagementRate: 0, conversionRate: 0,
    }))

    // Content type stats: aggregate by content_type
    const byType = {}
    for (const c of (Array.isArray(contents) ? contents : [])) {
      const t = c.content_type || 'post'
      if (!byType[t]) byType[t] = { contentCount: 0, totalViews: 0, totalLikes: 0, totalComments: 0 }
      byType[t].contentCount++
    }
    contentTypeStats.value = Object.entries(byType).map(([type, stats]) => ({
      type, typeLabel: type, ...stats, avgViews: 0, engagementRate: 0, conversionRate: 0,
    }))

    // Time trend: compute from publish dates
    const byDate = {}
    const now = new Date()
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now); d.setDate(d.getDate() - i)
      const key = (d.getMonth() + 1).toString().padStart(2, '0') + '-' + d.getDate().toString().padStart(2, '0')
      byDate[key] = { date: key, publishCount: 0, views: 0, interactions: 0 }
    }
    for (const c of (Array.isArray(contents) ? contents : [])) {
      if (c.created_at) {
        const cd = new Date(c.created_at)
        const key = (cd.getMonth() + 1).toString().padStart(2, '0') + '-' + cd.getDate().toString().padStart(2, '0')
        if (byDate[key]) byDate[key].publishCount++
      }
    }
    timeTrendData.value = Object.values(byDate)
  } catch (_) {
    // Keep empty arrays
  }
}

const platformColors = {
  douyin: '#ff0050',
  xhs: '#fe2c55',
  bilibili: '#00a1d6',
  kuaishou: '#ff7f00',
  wechat_mp: '#07c160',
}

const typeColors = {
  video: '#0ea5e9',
  image_text: '#8b5cf6',
  text: '#7c3aed',
  audio: '#f59e0b',
  doc: '#3b82f6',
}

const maxPlatformMetrics = computed(() => {
  const keys = ['totalViews', 'totalLikes', 'totalComments', 'totalShares']
  const out = {}
  keys.forEach(k => {
    out[k] = Math.max(0, ...platformStats.value.map(p => p[k] || 0))
  })
  return out
})

const maxTypeMetrics = computed(() => {
  const keys = ['totalViews', 'totalLikes', 'totalComments', 'totalShares']
  const out = {}
  keys.forEach(k => {
    out[k] = Math.max(0, ...contentTypeStats.value.map(p => p[k] || 0))
  })
  return out
})

const platformTableTotal = computed(() => {
  return platformStats.value.reduce((acc, item) => {
    acc.contentCount += item.contentCount
    acc.totalViews += item.totalViews
    acc.totalLikes += item.totalLikes
    acc.totalComments += item.totalComments
    return acc
  }, { contentCount: 0, totalViews: 0, totalLikes: 0, totalComments: 0, avgViews: 0, engagementRate: 0, conversionRate: 0 })
})

const typeTableTotal = computed(() => {
  return contentTypeStats.value.reduce((acc, item) => {
    acc.contentCount += item.contentCount
    acc.totalViews += item.totalViews
    acc.totalLikes += item.totalLikes
    acc.totalComments += item.totalComments
    return acc
  }, { contentCount: 0, totalViews: 0, totalLikes: 0, totalComments: 0, avgViews: 0, engagementRate: 0, conversionRate: 0 })
})

const timeTrendMax = computed(() => {
  return {
    publishCount: Math.max(0, ...timeTrendData.value.map(d => d.publishCount)),
    views: Math.max(0, ...timeTrendData.value.map(d => d.views)),
    interactions: Math.max(0, ...timeTrendData.value.map(d => d.interactions)),
  }
})

function barWidth(value, max) {
  if (!max) return '0%'
  return Math.max(4, (value / max) * 100).toFixed(1) + '%'
}

function lineHeight(value, max) {
  if (!max) return '0%'
  return Math.max(4, (value / max) * 100).toFixed(1) + '%'
}

// 效果数据复用 contentAssets
const analyticsData = computed(() =>
  contentAssets.value.map(item => ({
    ...item,
    conversionRate: item.conversionRate || 0
  }))
)

// ========== 筛选逻辑 ==========
const baseFilter = (list) => {
  return list.filter(item => {
    const matchSearch = !searchQuery.value || item.title?.includes(searchQuery.value)
    const matchPlatforms = filterPlatforms.value.length === 0 ||
      (item.platforms && item.platforms.some(p => filterPlatforms.value.includes(p))) ||
      (item.platform && filterPlatforms.value.includes(item.platform))
    let matchDate = true
    if (filterDateRange.value && filterDateRange.value.length === 2) {
      const d = item.createdAt || item.publishTime?.slice(0, 10)
      matchDate = d >= filterDateRange.value[0] && d <= filterDateRange.value[1]
    }
    const matchType = !filterContentType.value || item.type === filterContentType.value
    return matchSearch && matchPlatforms && matchDate && matchType
  })
}

const filteredVideos = computed(() => baseFilter(contentAssets))
const filteredCopy = computed(() => baseFilter(copyLibrary))
const filteredPublish = computed(() => baseFilter(publishRecords))
const filteredAnalytics = computed(() => baseFilter(analyticsData))

const totalStats = computed(() => {
  return filteredAnalytics.value.reduce((acc, item) => {
    acc.views += item.views || 0
    acc.likes += item.likes || 0
    acc.comments += item.comments || 0
    acc.shares += item.shares || 0
    return acc
  }, { views: 0, likes: 0, comments: 0, shares: 0 })
})

function formatNumber(n) {
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n?.toString() || '0'
}

function openVideoDetail(item) {
  selectedVideo.value = item
  videoDrawerVisible.value = true
}
function openCopyDetail(row) {
  selectedCopy.value = row
  copyDrawerVisible.value = true
}

const sortField = ref('')
const sortOrder = ref('')
function handleSort({ prop, order }) {
  sortField.value = prop || ''
  sortOrder.value = order || ''
}
</script>

<style scoped>
.content-assets-page {
  padding: 24px;
  min-height: 100vh;
}

.page-header {
  margin-bottom: 20px;
}

.title-section {
  margin-bottom: 16px;
}

.page-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}

.filter-section {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.search-input {
  width: 240px;
}

.filter-item {
  width: 180px;
}

.content-tabs {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

:deep(.content-tabs .el-tabs__header) {
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  margin: 0;
}

:deep(.content-tabs .el-tabs__content) {
  padding: 16px;
}

/* 卡片网格 */
.card-grid {
  margin: 0 -8px;
}

.content-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
}

.content-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--border-active);
}

.thumbnail {
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.type-video {
  background: linear-gradient(135deg, #0ea5e9, #06b6d4);
}

.type-text {
  background: linear-gradient(135deg, #7c3aed, #a78bfa);
}

.type-image_text {
  background: linear-gradient(135deg, #8b5cf6, #a78bfa);
}

.type-audio {
  background: linear-gradient(135deg, #f59e0b, #fbbf24);
}

.type-doc {
  background: linear-gradient(135deg, #3b82f6, #60a5fa);
}

.type-icon {
  font-size: 40px;
  color: rgba(255, 255, 255, 0.9);
}

.card-body {
  padding: 12px;
}

.card-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.platform-tag {
  margin-right: 4px;
}

.card-meta {
  margin-bottom: 8px;
}

.meta-date {
  font-size: 12px;
  color: var(--text-tertiary);
}

.card-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.card-stats span {
  display: flex;
  align-items: center;
  gap: 3px;
}

/* 表格 */
.assets-table {
  background: transparent;
}

:deep(.assets-table .el-table__header-wrapper th) {
  background: var(--table-header-bg);
  color: var(--text-secondary);
  font-weight: 600;
}

:deep(.assets-table .el-table__row:hover > td) {
  background: var(--hover-bg) !important;
}

.tag-item {
  margin-right: 4px;
}

.result-link {
  font-size: 13px;
}

.result-error {
  color: var(--rose-500);
  font-size: 13px;
}

.result-pending {
  color: var(--text-tertiary);
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 16px;
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent-primary);
  font-variant-numeric: tabular-nums;
}

.platform-text {
  margin-right: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

/* Drawer */
:deep(.detail-drawer .el-drawer__body) {
  padding: 0;
}

.drawer-content {
  padding: 20px;
}

.detail-thumbnail {
  height: 200px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.detail-type-icon {
  font-size: 60px;
  color: rgba(255, 255, 255, 0.9);
}

.detail-title {
  margin: 0 0 10px;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.detail-stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  margin-bottom: 20px;
  padding: 12px;
  background: var(--bg-canvas);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.detail-stat {
  text-align: center;
}

.detail-stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.detail-stat-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
}

.detail-text {
  font-size: 13px;
  color: var(--text-primary);
}

.detail-body {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.8;
  padding: 12px;
  background: var(--bg-canvas);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  white-space: pre-wrap;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-link {
  font-size: 13px;
  color: var(--accent-primary);
  word-break: break-all;
}

/* 响应式 */
@media (max-width: 1280px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .bar-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .filter-section {
    flex-direction: column;
    align-items: stretch;
  }
  .search-input,
  .filter-item {
    width: 100%;
  }
  .stats-row {
    grid-template-columns: 1fr;
  }
  .detail-stats-row {
    grid-template-columns: repeat(3, 1fr);
  }
  .bar-metrics {
    grid-template-columns: 1fr;
  }
  .compare-total-row {
    display: none;
  }
  .trend-chart {
    gap: 8px;
  }
}

/* 对比分析面板 */
.compare-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}

.compare-card :deep(.el-card__header) {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-color);
  background: var(--table-header-bg);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}

.compare-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.compare-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 15px;
}

/* 条形图 */
.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px 8px;
  margin-bottom: 16px;
  background: var(--bg-canvas);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.bar-label {
  width: 72px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  flex-shrink: 0;
  text-align: right;
}

.bar-metrics {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  min-width: 0;
}

.bar-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.bar-metric-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.bar-track {
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
  opacity: 0.85;
}

.bar-metric-value {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* 对比表格 */
.compare-table {
  background: transparent;
}

:deep(.compare-table .el-table__header-wrapper th) {
  background: var(--table-header-bg);
  color: var(--text-secondary);
  font-weight: 600;
}

:deep(.compare-table .el-table__row:hover > td) {
  background: var(--hover-bg) !important;
}

.platform-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

/* 总计行 */
.compare-total-row {
  display: grid;
  grid-template-columns: 100px 90px 110px 110px 110px 110px 100px 100px;
  gap: 0;
  padding: 10px 12px;
  background: var(--table-header-bg);
  border-bottom: 1px solid var(--border-color);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  align-items: center;
}

.total-label {
  padding-left: 4px;
}

.total-cell {
  text-align: left;
  padding-left: 4px;
  font-variant-numeric: tabular-nums;
}

/* 时间趋势 */
.trend-panel {
  padding: 8px;
}

.trend-legend {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  padding: 0 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.trend-chart {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  height: 200px;
  padding: 16px 12px 8px;
  background: var(--bg-canvas);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  margin-bottom: 16px;
  position: relative;
}

.trend-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  position: relative;
  min-width: 0;
}

.trend-bars {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 4px;
  height: 140px;
  width: 100%;
}

.trend-bar {
  width: 8px;
  border-radius: 4px 4px 0 0;
  transition: height 0.6s ease;
  min-height: 2px;
}

.trend-bar.publish { background: #0ea5e9; }
.trend-bar.views { background: #8b5cf6; }
.trend-bar.interactions { background: #f59e0b; }

.trend-date {
  font-size: 12px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.trend-tip {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: 12px;
  color: var(--text-primary);
  white-space: nowrap;
  box-shadow: var(--shadow-md);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
  z-index: 10;
  margin-bottom: 6px;
}

.trend-tip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: var(--border-color);
}

.trend-col:hover .trend-tip {
  opacity: 1;
}

.trend-table-wrapper {
  margin-top: 8px;
}

@media (max-width: 1280px) {
  .compare-total-row {
    grid-template-columns: 100px 90px 110px 110px 110px 110px 100px 100px;
  }
  .bar-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .compare-total-row {
    display: none;
  }
  .bar-metrics {
    grid-template-columns: 1fr;
  }
  .trend-chart {
    gap: 8px;
    height: 160px;
  }
  .trend-bars {
    height: 110px;
  }
  .trend-bar {
    width: 6px;
  }
  .compare-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
