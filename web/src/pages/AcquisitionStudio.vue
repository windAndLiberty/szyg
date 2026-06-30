<template>
  <div class="acquisition-studio">
    <h2 class="page-title">智能截流</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">

      <!-- ════════════════════════════════════════════
           Tab 1 — 搜索截流
           ════════════════════════════════════════════ -->
      <el-tab-pane label="搜索截流" name="search">
        <div class="tab-content">
          <!-- 搜索条件区 -->
          <el-card class="search-card" shadow="never">
            <div class="search-row">
              <el-input
                v-model="searchKeyword"
                placeholder="输入关键词搜索视频..."
                size="large"
                class="search-input"
                clearable
                @keyup.enter="handleSearch"
              >
                <template #append>
                  <el-button type="primary" :loading="searchLoading" @click="handleSearch">🔍 搜索</el-button>
                </template>
              </el-input>
            </div>
            <div class="filter-row">
              <div class="filter-group">
                <span class="filter-label">平台：</span>
                <el-checkbox-group v-model="selectedPlatforms">
                  <el-checkbox label="douyin">抖音</el-checkbox>
                  <el-checkbox label="xhs">小红书</el-checkbox>
                  <el-checkbox label="bilibili">B站</el-checkbox>
                  <el-checkbox label="kuaishou">快手</el-checkbox>
                </el-checkbox-group>
              </div>
              <div class="filter-group">
                <span class="filter-label">评分阈值：</span>
                <el-slider v-model="scoreThreshold" :min="30" :max="100" :show-input="true" style="width:220px" />
              </div>
              <div class="filter-group">
                <span class="filter-label">时间范围：</span>
                <el-select v-model="timeRange" placeholder="时间范围" style="width:120px">
                  <el-option label="全部" value="all" />
                  <el-option label="24小时内" value="day" />
                  <el-option label="7天内" value="week" />
                  <el-option label="30天内" value="month" />
                </el-select>
              </div>
              <div class="filter-group">
                <span class="filter-label">排序：</span>
                <el-select v-model="sortOrder" placeholder="排序方式" style="width:120px">
                  <el-option label="综合排序" value="default" />
                  <el-option label="评分最高" value="score" />
                  <el-option label="热度最高" value="hot" />
                  <el-option label="最新发布" value="new" />
                </el-select>
              </div>
            </div>
          </el-card>

          <!-- 搜索结果列表 -->
          <div class="results-list">
            <div
              v-for="item in filteredResults"
              :key="item.id"
              class="result-card"
              :class="{ 'high-score': item.score >= 70 }"
            >
              <div class="thumbnail-wrap">
                <div class="thumbnail" :style="{ backgroundColor: item.thumbnailColor }">
                  <span class="thumbnail-text">{{ platformShort(item.platform) }}</span>
                </div>
              </div>
              <div class="result-info">
                <div class="result-header">
                  <h4 class="result-title">{{ item.title }}</h4>
                  <el-tag size="small" :type="platformTagType(item.platform)">{{ platformName(item.platform) }}</el-tag>
                </div>
                <div class="result-meta">
                  <span class="meta-item"><span class="meta-label">作者：</span>{{ item.author }}</span>
                </div>
                <div class="result-stats">
                  <span class="stat-item">
                    <span class="stat-icon">👍</span>
                    <span class="tabular-nums">{{ formatNumber(item.likes) }}</span>
                  </span>
                  <span class="stat-item">
                    <span class="stat-icon">💬</span>
                    <span class="tabular-nums">{{ formatNumber(item.comments) }}</span>
                  </span>
                  <span class="stat-item">
                    <span class="stat-icon">🔄</span>
                    <span class="tabular-nums">{{ formatNumber(item.shares) }}</span>
                  </span>
                </div>
                <div class="result-score">
                  <span class="score-label">截流评分</span>
                  <el-progress
                    :percentage="item.score"
                    :color="scoreColor(item.score)"
                    :stroke-width="10"
                    :show-text="true"
                    class="score-progress"
                  />
                </div>
                <div class="result-actions">
                  <el-button type="primary" size="small" @click="intercept(item)">🎯 一键截流</el-button>
                  <el-button size="small" plain @click="viewDetail(item)">查看详情</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════
           Tab 2 — 截流任务
           ════════════════════════════════════════════ -->
      <el-tab-pane label="截流任务" name="intercept">
        <div class="tab-content">
          <!-- 统计卡片行 -->
          <el-row :gutter="16" class="stats-row">
            <el-col :xs="12" :sm="12" :md="6" :lg="6">
              <el-card class="stat-card" shadow="never">
                <div class="stat-inner">
                  <div class="stat-icon">⏳</div>
                  <div class="stat-body">
                    <div class="stat-value pending">{{ taskStats.pending }}</div>
                    <div class="stat-label">待发送</div>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6" :lg="6">
              <el-card class="stat-card" shadow="never">
                <div class="stat-inner">
                  <div class="stat-icon">📤</div>
                  <div class="stat-body">
                    <div class="stat-value sent">{{ taskStats.sent }}</div>
                    <div class="stat-label">已发送</div>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6" :lg="6">
              <el-card class="stat-card" shadow="never">
                <div class="stat-inner">
                  <div class="stat-icon">✅</div>
                  <div class="stat-body">
                    <div class="stat-value success">{{ taskStats.success }}</div>
                    <div class="stat-label">成功</div>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6" :lg="6">
              <el-card class="stat-card" shadow="never">
                <div class="stat-inner">
                  <div class="stat-icon">❌</div>
                  <div class="stat-body">
                    <div class="stat-value failed">{{ taskStats.failed }}</div>
                    <div class="stat-label">失败</div>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- 评论队列列表 -->
          <el-card class="queue-card" shadow="never">
            <template #header>
              <div class="queue-header">
                <span class="card-title">评论队列</span>
                <div class="batch-actions">
                  <el-button
                    type="primary"
                    size="small"
                    :disabled="selectedQueueItems.length === 0"
                    @click="batchSend"
                  >
                    批量发送 ({{ selectedQueueItems.length }})
                  </el-button>
                  <el-button
                    type="danger"
                    size="small"
                    plain
                    :disabled="selectedQueueItems.length === 0"
                    @click="batchDelete"
                  >
                    批量删除
                  </el-button>
                </div>
              </div>
            </template>
            <el-table
              :data="queueItems"
              @selection-change="handleQueueSelectionChange"
              style="width: 100%"
            >
              <el-table-column type="selection" width="55" />
              <el-table-column prop="videoTitle" label="视频标题" min-width="180" show-overflow-tooltip />
              <el-table-column prop="comment" label="评论内容" min-width="200" show-overflow-tooltip />
              <el-table-column prop="platform" label="平台" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="platformTagType(row.platform)">{{ platformName(row.platform) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150">
                <template #default="{ row }">
                  <el-button v-if="row.status === 'pending'" type="primary" size="small" @click="sendComment(row)">发送</el-button>
                  <el-button v-else type="success" size="small" disabled>已发送</el-button>
                  <el-button size="small" plain @click="deleteQueueItem(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 速率监控仪表 -->
          <el-card class="rate-card" shadow="never">
            <template #header>
              <span class="card-title">📊 速率监控</span>
            </template>
            <el-row :gutter="24" class="rate-row">
              <el-col :span="8">
                <div class="rate-item">
                  <div class="rate-label">今日发送数</div>
                  <div class="rate-value">{{ rateStats.todaySent }}</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="rate-item">
                  <div class="rate-label">频率限制</div>
                  <el-progress
                    :percentage="rateStats.ratePercent"
                    :color="rateStats.ratePercent > 80 ? '#f43f5e' : '#22c55e'"
                    :stroke-width="16"
                    class="rate-progress"
                  />
                  <div class="rate-sublabel">{{ rateStats.ratePercent }}% / 100%</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="rate-item">
                  <div class="rate-label">账号健康度</div>
                  <div class="health-value" :class="healthClass(rateStats.health)">{{ rateStats.health }}%</div>
                </div>
              </el-col>
            </el-row>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════
           Tab 3 — 互动管理
           ════════════════════════════════════════════ -->
      <el-tab-pane label="互动管理" name="interaction">
        <div class="tab-content">
          <!-- 自动回复模板管理 -->
          <el-card class="template-card" shadow="never">
            <template #header>
              <div class="template-header">
                <span class="card-title">🤖 自动回复模板</span>
                <el-button type="primary" size="small" @click="showAddTemplate = true">+ 新建模板</el-button>
              </div>
            </template>
            <el-table :data="replyTemplates" style="width:100%">
              <el-table-column prop="name" label="模板名称" min-width="120" />
              <el-table-column prop="keywords" label="触发关键词" min-width="160">
                <template #default="{ row }">
                  <el-tag v-for="kw in row.keywords" :key="kw" size="small" class="kw-tag">{{ kw }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="content" label="回复内容" min-width="220" show-overflow-tooltip />
              <el-table-column prop="enabled" label="启用状态" width="100">
                <template #default="{ row }">
                  <el-switch v-model="row.enabled" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button size="small" @click="editTemplate(row)">编辑</el-button>
                  <el-button size="small" type="danger" plain @click="deleteTemplate(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- DeAI 预处理预览 -->
          <el-card class="deai-card" shadow="never">
            <template #header>
              <span class="card-title">🧠 DeAI 预处理预览</span>
            </template>
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="deai-section">
                  <div class="section-label">原始评论</div>
                  <el-input
                    v-model="deaiInput"
                    type="textarea"
                    :rows="5"
                    placeholder="粘贴原始评论内容..."
                  />
                  <el-button type="primary" class="deai-btn" @click="processDeAI">DeAI 处理</el-button>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="deai-section">
                  <div class="section-label">处理后结果</div>
                  <div class="deai-result">
                    <div v-if="deaiResult" class="result-text">{{ deaiResult }}</div>
                    <div v-else class="result-placeholder">点击左侧「DeAI 处理」查看结果</div>
                  </div>
                  <div v-if="deaiStats" class="deai-stats">
                    <div class="stat-pill">
                      <span class="pill-label">去AI味评分</span>
                      <span class="pill-value">{{ deaiScoreText }}</span>
                    </div>
                    <div class="stat-pill">
                      <span class="pill-label">替换词数</span>
                      <span class="pill-value">{{ deaiStats.replacedWords }}</span>
                    </div>
                    <div class="stat-pill">
                      <span class="pill-label">中文占比</span>
                      <span class="pill-value">{{ deaiStats.chineseRatio }}%</span>
                    </div>
                  </div>
                </div>
              </el-col>
            </el-row>
          </el-card>

          <!-- 违禁词检测 -->
          <el-card class="banned-card" shadow="never">
            <template #header>
              <span class="card-title">🛡️ 违禁词检测</span>
            </template>
            <div class="banned-input-row">
              <el-input
                v-model="bannedInput"
                placeholder="输入待检测内容..."
                clearable
                style="flex:1"
                @keyup.enter="detectBanned"
              />
              <el-button type="warning" @click="detectBanned">检测</el-button>
            </div>
            <div v-if="bannedResult" class="banned-result">
              <div class="result-badge" :class="bannedResult.status">
                <span v-if="bannedResult.status === 'pass'">✅ 通过检测</span>
                <span v-else-if="bannedResult.status === 'warn'">⚠️ 警告</span>
                <span v-else>❌ 检测失败</span>
              </div>
              <div v-if="bannedResult.words.length" class="banned-words">
                <span class="words-label">违禁词：</span>
                <el-tag v-for="w in bannedResult.words" :key="w" type="danger" effect="dark" size="small">{{ w }}</el-tag>
              </div>
              <div class="detected-text">
                <span v-for="(part, idx) in bannedResult.highlighted" :key="idx">
                  <span v-if="part.isBanned" class="highlight-banned">{{ part.text }}</span>
                  <span v-else>{{ part.text }}</span>
                </span>
              </div>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════
           Tab 4 — 监听雷达
           ════════════════════════════════════════════ -->
      <el-tab-pane label="监听雷达" name="monitor">
        <div class="tab-content">
          <!-- 监听目标列表 -->
          <el-card class="target-card" shadow="never">
            <template #header>
              <div class="target-header">
                <span class="card-title">🎯 监听目标</span>
                <el-button type="primary" size="small" @click="showAddTarget = true">+ 添加监听目标</el-button>
              </div>
            </template>
            <el-table :data="monitorTargets" style="width:100%">
              <el-table-column prop="videoTitle" label="视频标题" min-width="200" show-overflow-tooltip />
              <el-table-column prop="platform" label="平台" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="platformTagType(row.platform)">{{ platformName(row.platform) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="status" label="监听状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'monitoring' ? 'success' : 'info'" size="small">
                    {{ row.status === 'monitoring' ? '监听中' : '已停止' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="lastUpdate" label="最近更新" width="160" />
              <el-table-column label="操作" width="180">
                <template #default="{ row }">
                  <el-button v-if="row.status === 'stopped'" type="success" size="small" @click="row.status = 'monitoring'">启动</el-button>
                  <el-button v-else type="warning" size="small" @click="row.status = 'stopped'">停止</el-button>
                  <el-button size="small" plain @click="deleteTarget(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- 实时评论区 + 线索面板 -->
          <el-row :gutter="16" class="monitor-row">
            <el-col :xs="24" :sm="24" :md="14" :lg="14">
              <el-card class="live-card" shadow="never">
                <template #header>
                  <span class="card-title">
                    💬 实时评论
                    <span class="live-badge">
                      <span class="live-dot"></span>
                      实时
                    </span>
                  </span>
                </template>
                <div ref="liveCommentsRef" class="live-comments">
                  <div
                    v-for="comment in liveComments"
                    :key="comment.id"
                    class="live-comment"
                  >
                    <div class="comment-avatar" :style="{ backgroundColor: comment.avatarColor }">{{ comment.nickname.charAt(0) }}</div>
                    <div class="comment-body">
                      <div class="comment-header">
                        <span class="comment-nickname">{{ comment.nickname }}</span>
                        <span class="comment-time">{{ comment.time }}</span>
                      </div>
                      <div class="comment-text">{{ comment.content }}</div>
                      <div class="comment-footer">
                        <el-tag :type="sentimentTagType(comment.sentiment)" size="small" effect="dark">
                          {{ sentimentLabel(comment.sentiment) }}
                        </el-tag>
                        <el-button size="small" type="primary" plain @click="markAsLead(comment)">标记为线索</el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :xs="24" :sm="24" :md="10" :lg="10">
              <el-card class="lead-card" shadow="never">
                <template #header>
                  <span class="card-title">🎯 线索自动标记</span>
                </template>
                <div class="lead-list">
                  <div v-for="lead in leads" :key="lead.id" class="lead-item">
                    <div class="lead-info">
                      <div class="lead-name">{{ lead.nickname }}</div>
                      <div class="lead-summary">{{ lead.summary }}</div>
                    </div>
                    <div class="lead-level">
                      <el-tag :type="leadLevelType(lead.level)" size="small" effect="dark">意向 {{ lead.level }}</el-tag>
                    </div>
                  </div>
                  <div v-if="leads.length === 0" class="lead-empty">暂无标记线索</div>
                </div>
                <div class="lead-actions">
                  <el-button type="primary" :disabled="leads.length === 0" @click="replyAllLeads">一键回复</el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════
           Tab 5 — 养号
           ════════════════════════════════════════════ -->
      <el-tab-pane label="养号" name="nurture">
        <div class="tab-content">
          <el-card shadow="never" class="nurture-card">
            <template #header>
              <span class="card-title">🌱 养号策略配置</span>
            </template>
            <el-form :model="nurtureForm" label-width="120px" style="max-width:600px">
              <el-form-item label="选择平台">
                <el-select v-model="nurtureForm.platform" placeholder="选择平台">
                  <el-option label="抖音" value="douyin" />
                  <el-option label="小红书" value="xhs" />
                  <el-option label="B站" value="bilibili" />
                  <el-option label="快手" value="kuaishou" />
                </el-select>
              </el-form-item>
              <el-form-item label="浏览视频数">
                <el-input-number v-model="nurtureForm.browseCount" :min="10" :max="500" :step="10" />
              </el-form-item>
              <el-form-item label="点赞概率">
                <el-slider v-model="nurtureForm.likeProbability" :min="0" :max="100" :step="5" show-input />
              </el-form-item>
              <el-form-item label="评论概率">
                <el-slider v-model="nurtureForm.commentProbability" :min="0" :max="100" :step="5" show-input />
              </el-form-item>
              <el-form-item label="停留时间(秒)">
                <el-slider v-model="nurtureForm.stayDuration" :min="3" :max="60" :step="3" show-input />
              </el-form-item>
              <el-form-item label="养号时段">
                <el-time-picker v-model="nurtureForm.timeRange" is-range range-separator="至" start-placeholder="开始" end-placeholder="结束" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="startNurture" :loading="nurtureLoading">开始养号</el-button>
                <el-button type="warning" plain @click="stopNurture" :disabled="!nurtureRunning">停止</el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <el-card shadow="never" class="nurture-card" style="margin-top:16px">
            <template #header>
              <span class="card-title">📊 养号记录</span>
            </template>
            <el-table :data="nurtureLogs" stripe style="width:100%">
              <el-table-column prop="time" label="时间" width="160" />
              <el-table-column prop="platform" label="平台" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="platformTagType(row.platform)">{{ platformName(row.platform) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="browsed" label="浏览数" width="80" />
              <el-table-column prop="liked" label="点赞数" width="80" />
              <el-table-column prop="commented" label="评论数" width="80" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'running' ? 'success' : 'info'" size="small">{{ row.status === 'running' ? '进行中' : '已完成' }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ════════════════════════════════════════════
           Tab 6 — 平台状态
           ════════════════════════════════════════════ -->
      <el-tab-pane label="平台状态" name="status">
        <div class="tab-content">
          <el-row :gutter="16">
            <el-col :span="6" v-for="p in platformStatusList" :key="p.platform">
              <el-card shadow="never" class="status-card" :class="p.online ? 'online' : 'offline'">
                <div class="status-card-inner">
                  <div class="status-platform-name">{{ p.name }}</div>
                  <div class="status-indicator">
                    <span class="status-dot" :class="p.online ? 'online' : 'offline'"></span>
                    <span class="status-text">{{ p.online ? '在线' : '离线' }}</span>
                  </div>
                  <div class="status-meta">
                    <div>账号: {{ p.account || '未绑定' }}</div>
                    <div>最后活跃: {{ p.lastActive || '—' }}</div>
                  </div>
                  <el-button size="small" type="primary" plain @click="goToPlatformSettings(p.platform)">前往设置</el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加监听目标对话框 -->
    <el-dialog v-model="showAddTarget" title="添加监听目标" width="500px">
      <el-form :model="newTarget" label-width="80px">
        <el-form-item label="视频URL">
          <el-input v-model="newTarget.url" placeholder="粘贴视频链接..." />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="newTarget.platform" placeholder="选择平台">
            <el-option label="抖音" value="douyin" />
            <el-option label="小红书" value="xhs" />
            <el-option label="B站" value="bilibili" />
            <el-option label="快手" value="kuaishou" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="newTarget.videoTitle" placeholder="输入视频标题..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddTarget = false">取消</el-button>
        <el-button type="primary" @click="addTarget">确定</el-button>
      </template>
    </el-dialog>

    <!-- 添加模板对话框 -->
    <el-dialog v-model="showAddTemplate" title="新建模板" width="500px">
      <el-form :model="newTemplate" label-width="100px">
        <el-form-item label="模板名称">
          <el-input v-model="newTemplate.name" />
        </el-form-item>
        <el-form-item label="触发关键词">
          <el-input v-model="newTemplate.keywordsInput" placeholder="用逗号分隔多个关键词" />
        </el-form-item>
        <el-form-item label="回复内容">
          <el-input v-model="newTemplate.content" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="newTemplate.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddTemplate = false">取消</el-button>
        <el-button type="primary" @click="addTemplate">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const PLATFORM_COLOR = { douyin: '#ff0050', xhs: '#ff2442', bilibili: '#00b4d8', kuaishou: '#ff6600' }

// ════════════════════════════════════════════
// Tab State
// ════════════════════════════════════════════
const activeTab = ref('search')

// ════════════════════════════════════════════
// Tab 1: 搜索截流 — POST /api/acquisition/search
// ════════════════════════════════════════════
const searchKeyword = ref('护肤')
const selectedPlatforms = ref(['douyin', 'xhs', 'bilibili', 'kuaishou'])
const scoreThreshold = ref(50)
const timeRange = ref('all')
const sortOrder = ref('default')
const searchLoading = ref(false)

const searchResults = ref([])

const filteredResults = computed(() => {
  let results = [...searchResults.value]
  results = results.filter(r => selectedPlatforms.value.includes(r.platform))
  results = results.filter(r => r.score >= scoreThreshold.value)
  if (sortOrder.value === 'score') results.sort((a, b) => b.score - a.score)
  if (sortOrder.value === 'hot') results.sort((a, b) => b.likes - a.likes)
  if (sortOrder.value === 'new') results.sort((a, b) => b.id - a.id)
  return results
})

async function handleSearch () {
  if (!searchKeyword.value.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  if (selectedPlatforms.value.length === 0) {
    ElMessage.warning('请至少选择一个平台')
    return
  }
  searchLoading.value = true
  try {
    const { data } = await axios.post('/api/acquisition/search', {
      keyword: searchKeyword.value.trim(),
      platforms: selectedPlatforms.value,
      limit: 30,
      min_score: scoreThreshold.value
    })
    const videos = Array.isArray(data.videos) ? data.videos : []
    searchResults.value = videos.map((v, idx) => ({
      id: v.video_id || idx,
      title: v.title || '(无标题)',
      author: v.author || '未知作者',
      platform: v.platform,
      likes: v.likes || 0,
      comments: v.comments_count || 0,
      shares: v.shares || 0,
      score: v.quality_score || 0,
      url: v.url || '',
      description: v.description || '',
      thumbnailColor: PLATFORM_COLOR[v.platform] || '#888'
    }))
    ElMessage.success(`搜索完成，发现 ${searchResults.value.length} 个目标`)
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message))
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

// 一键截流: AI 为该视频生成真实评论 → 加入待发送队列
async function intercept (item) {
  try {
    const { data } = await axios.post('/api/acquisition/comments/generate', {
      video_title: item.title,
      video_description: item.description || '',
      count: 3,
      strategy: 'balanced'
    })
    const comments = Array.isArray(data.comments) ? data.comments : []
    if (comments.length === 0) {
      ElMessage.warning('未能生成评论')
      return
    }
    comments.forEach((text) => {
      queueItems.value.unshift({
        id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        videoTitle: item.title,
        videoId: item.id,
        comment: text,
        platform: item.platform,
        status: 'pending',
        local: true
      })
    })
    taskStats.pending += comments.length
    activeTab.value = 'intercept'
    ElMessage.success(`已为「${item.title}」生成 ${comments.length} 条评论，请在截流任务中确认发送`)
  } catch (e) {
    ElMessage.error('生成评论失败: ' + (e.response?.data?.detail || e.message))
  }
}

function viewDetail (item) {
  if (item.url) {
    window.open(item.url, '_blank')
  } else {
    ElMessage.info('该目标暂无可跳转链接')
  }
}

// ════════════════════════════════════════════
// Tab 2: 截流任务 — /api/acquisition/comments/*
// ════════════════════════════════════════════
const taskStats = reactive({ pending: 0, sent: 0, success: 0, failed: 0 })
const queueItems = ref([])
const selectedQueueItems = ref([])
const rateStats = reactive({ todaySent: 0, ratePercent: 0, health: 100 })

async function loadQueue () {
  try {
    const { data } = await axios.get('/api/acquisition/comments/queue', { params: { limit: 100, offset: 0 } })
    const serverItems = (Array.isArray(data.items) ? data.items : []).map(i => ({
      id: i.id,
      videoTitle: i.video_title || '(未知视频)',
      videoId: i.video_id || '',
      comment: i.comment_text || '',
      platform: i.platform,
      status: i.status || 'pending',
      local: false
    }))
    // 保留本地未持久化的待发送项，合并服务端项
    const localItems = queueItems.value.filter(i => i.local)
    queueItems.value = [...localItems, ...serverItems]
  } catch {
    // 队列为空或接口不可用时静默
  }
}

async function loadCommentStats () {
  try {
    const { data } = await axios.get('/api/acquisition/comments/stats')
    const q = data.queue || {}
    taskStats.pending = q.total_pending || 0
    taskStats.sent = q.total_sent || 0
    taskStats.success = q.total_sent || 0
    taskStats.failed = q.total_failed || 0
    // 速率: 取所有平台中已用比例最高者作为概览
    const rl = data.rate_limits || {}
    let used = 0, total = 0
    Object.values(rl).forEach(v => {
      if (v && typeof v === 'object') {
        const dl = v.daily_limit || 0
        const dr = v.daily_remaining ?? dl
        used += (dl - dr)
        total += dl
      }
    })
    rateStats.todaySent = used
    rateStats.ratePercent = total > 0 ? Math.round((used / total) * 100) : 0
    rateStats.health = Math.max(0, 100 - rateStats.ratePercent)
  } catch {
    // 静默
  }
}

function handleQueueSelectionChange (selection) {
  selectedQueueItems.value = selection
}

// 按平台分组调用 batch-send
async function sendItems (items) {
  const pending = items.filter(i => i.status === 'pending')
  if (pending.length === 0) return
  const byPlatform = {}
  pending.forEach(i => {
    (byPlatform[i.platform] = byPlatform[i.platform] || []).push(i)
  })
  let totalSent = 0
  for (const [platform, group] of Object.entries(byPlatform)) {
    try {
      const { data } = await axios.post('/api/acquisition/comments/batch-send', {
        platform,
        comments: group.map(i => ({
          video_id: i.videoId || '',
          video_title: i.videoTitle || '',
          comment_text: i.comment || ''
        })),
        strategy: 'balanced',
        deai: true
      })
      totalSent += data.sent || 0
      group.forEach(i => { i.status = 'sent' })
    } catch (e) {
      ElMessage.error(`${platform} 发送失败: ` + (e.response?.data?.detail || e.message))
      group.forEach(i => { i.status = 'failed' })
    }
  }
  if (totalSent > 0) ElMessage.success(`已发送 ${totalSent} 条评论`)
  await loadCommentStats()
}

async function batchSend () {
  await sendItems(selectedQueueItems.value)
  selectedQueueItems.value = []
}

async function batchDelete () {
  for (const row of selectedQueueItems.value) {
    await deleteQueueItem(row, true)
  }
  selectedQueueItems.value = []
  await loadCommentStats()
}

async function sendComment (row) {
  await sendItems([row])
}

async function deleteQueueItem (row, silent = false) {
  if (!row.local) {
    try {
      await axios.delete(`/api/acquisition/comments/queue/${row.id}`)
    } catch (e) {
      if (!silent) ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
  queueItems.value = queueItems.value.filter(i => i.id !== row.id)
  if (!silent) await loadCommentStats()
}

// ════════════════════════════════════════════
// Tab 3: 互动管理
// ════════════════════════════════════════════
const replyTemplates = ref([])

async function loadReplyTemplates() {
  try {
    const { data } = await axios.get('/api/acquisition/reply-templates')
    replyTemplates.value = data.templates || []
  } catch (e) {
    ElMessage.error('加载模板失败: ' + (e.response?.data?.detail || e.message))
  }
}

const showAddTemplate = ref(false)
const newTemplate = reactive({ name: '', keywordsInput: '', content: '', enabled: true })

async function addTemplate() {
  const keywords = newTemplate.keywordsInput.split(/[,，]/).map(s => s.trim()).filter(Boolean)
  const item = { name: newTemplate.name, keywords, content: newTemplate.content, enabled: newTemplate.enabled }
  try {
    const { data } = await axios.post('/api/acquisition/reply-templates', item)
    replyTemplates.value.push(data)
    showAddTemplate.value = false
    newTemplate.name = ''
    newTemplate.keywordsInput = ''
    newTemplate.content = ''
    newTemplate.enabled = true
  } catch (e) {
    ElMessage.error('添加模板失败: ' + (e.response?.data?.detail || e.message))
  }
}

function editTemplate(row) {
  ElMessage.info(`编辑模板「${row.name}」（模板编辑功能开发中）`)
}

async function deleteTemplate(row) {
  try {
    await axios.delete(`/api/acquisition/reply-templates/${row.id}`)
    replyTemplates.value = replyTemplates.value.filter(t => t.id !== row.id)
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

// DeAI — POST /api/acquisition/comments/deai
const deaiInput = ref('')
const deaiResult = ref('')
const deaiStats = ref(null)

const deaiScoreText = computed(() => {
  if (!deaiStats.value) return ''
  const s = deaiStats.value.score
  if (s >= 90) return '优秀'
  if (s >= 70) return '良好'
  if (s >= 50) return '一般'
  return '需优化'
})

async function processDeAI () {
  if (!deaiInput.value) return
  const input = deaiInput.value
  try {
    const { data } = await axios.post('/api/acquisition/comments/deai', {
      text: input,
      platform: 'douyin'
    })
    const result = data.processed || input
    deaiResult.value = result
    const diff = Math.abs(input.length - result.length)
    const chineseChars = (result.match(/[\u4e00-\u9fa5]/g) || []).length
    const chineseRatio = result.length ? Math.round((chineseChars / result.length) * 100) : 100
    const changed = result !== input
    deaiStats.value = {
      score: changed ? Math.min(95, 75 + Math.floor(diff / 2)) : 60,
      replacedWords: Math.max(changed ? 1 : 0, Math.floor(diff / 3)),
      chineseRatio: Math.min(99, chineseRatio)
    }
  } catch (e) {
    ElMessage.error('DeAI 处理失败: ' + (e.response?.data?.detail || e.message))
  }
}

// 违禁词/发前检查 — POST /api/acquisition/comments/preflight
const bannedInput = ref('')
const bannedResult = ref(null)

async function detectBanned () {
  const text = bannedInput.value
  if (!text) return
  try {
    const { data } = await axios.post('/api/acquisition/comments/preflight', { text })
    const risks = Array.isArray(data.risks) ? data.risks : []
    // 从风险描述中提取屏蔽词，用于高亮
    const found = []
    risks.forEach(r => {
      const m = /屏蔽词[:：]\s*(.+)/.exec(r)
      if (m) found.push(m[1].trim())
    })
    const status = data.pass ? 'pass' : (data.risk_level === 'high' ? 'fail' : 'warn')
    const highlighted = []
    let remaining = text
    const sortedFound = [...new Set(found)].sort((a, b) => text.indexOf(a) - text.indexOf(b))
    for (const w of sortedFound) {
      const idx = remaining.indexOf(w)
      if (idx === -1) continue
      if (idx > 0) highlighted.push({ text: remaining.slice(0, idx), isBanned: false })
      highlighted.push({ text: w, isBanned: true })
      remaining = remaining.slice(idx + w.length)
    }
    if (remaining) highlighted.push({ text: remaining, isBanned: false })
    bannedResult.value = { status, words: found, risks, highlighted }
  } catch (e) {
    ElMessage.error('检测失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ════════════════════════════════════════════
// Tab 4: 监听雷达 — /api/acquisition/monitor/* + /leads
// ════════════════════════════════════════════
const monitorTargets = ref([])

const showAddTarget = ref(false)
const newTarget = reactive({ url: '', platform: 'douyin', videoTitle: '' })

async function loadTargets () {
  try {
    const { data } = await axios.get('/api/acquisition/monitor/targets')
    const targets = Array.isArray(data.targets) ? data.targets : []
    monitorTargets.value = targets.map(t => ({
      id: t.target_id,
      videoTitle: t.video_title || '(未命名)',
      platform: t.platform,
      status: t.enabled ? 'monitoring' : 'stopped',
      lastUpdate: t.last_poll_at || '—'
    }))
  } catch {
    monitorTargets.value = []
  }
}

async function addTarget () {
  try {
    await axios.post('/api/acquisition/monitor/targets', {
      platform: newTarget.platform,
      video_url: newTarget.url,
      video_title: newTarget.videoTitle || '未命名视频',
      owner: 'competitor'
    })
    ElMessage.success('监听目标已添加')
    showAddTarget.value = false
    newTarget.url = ''
    newTarget.videoTitle = ''
    newTarget.platform = 'douyin'
    await loadTargets()
  } catch (e) {
    ElMessage.error('添加失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteTarget (row) {
  try {
    await axios.delete(`/api/acquisition/monitor/targets/${row.id}`)
    await loadTargets()
  } catch (e) {
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

const liveCommentsRef = ref(null)
const liveComments = ref([])
const leads = ref([])

async function loadLeads () {
  try {
    const { data } = await axios.get('/api/acquisition/leads', { params: { limit: 50 } })
    const list = Array.isArray(data.leads) ? data.leads : []
    leads.value = list.map(l => ({
      id: l.lead_id || l.id,
      nickname: l.author_name || l.nickname || '匿名用户',
      summary: l.comment_text || l.text || '',
      level: l.grade || 'C'
    }))
  } catch {
    leads.value = []
  }
}

onMounted(() => {
  loadQueue()
  loadCommentStats()
  loadTargets()
  loadLeads()
  loadReplyTemplates()
  loadPlatformStatus()
})

onUnmounted(() => {})

function markAsLead (comment) {
  const level = comment.sentiment === 'positive' ? 'A' : (comment.sentiment === 'neutral' ? 'B' : 'C')
  if (!leads.value.find(l => l.nickname === comment.nickname && l.summary === comment.content)) {
    leads.value.unshift({
      id: `local-${Date.now()}`,
      nickname: comment.nickname,
      summary: comment.content,
      level
    })
  }
}

// 一键回复所有线索 — POST /api/acquisition/auto-reply
async function replyAllLeads () {
  if (leads.value.length === 0) return
  try {
    const { data } = await axios.post('/api/acquisition/auto-reply', {
      platform: 'douyin',
      comments: leads.value.map(l => ({
        author_name: l.nickname,
        comment_text: l.summary
      })),
      dry_run: false
    })
    ElMessage.success(`已回复 ${data.sent || 0} / ${data.total || leads.value.length} 条线索`)
    await loadLeads()
  } catch (e) {
    ElMessage.error('一键回复失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ════════════════════════════════════════════
// Helpers
// ════════════════════════════════════════════
function formatNumber (num) {
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num.toString()
}

function platformName (platform) {
  const map = { douyin: '抖音', xhs: '小红书', bilibili: 'B站', kuaishou: '快手' }
  return map[platform] || platform
}

function platformShort (platform) {
  const map = { douyin: '抖', xhs: '红', bilibili: 'B', kuaishou: '快' }
  return map[platform] || platform
}

function platformTagType (platform) {
  const map = { douyin: 'danger', xhs: 'danger', bilibili: 'primary', kuaishou: 'warning' }
  return map[platform] || 'info'
}

function scoreColor (score) {
  if (score < 40) return '#94a3b8'
  if (score < 70) return '#fbbf24'
  return '#4f46e5'
}

function statusTagType (status) {
  const map = { pending: 'warning', sent: 'success', failed: 'danger' }
  return map[status] || 'info'
}

function statusLabel (status) {
  const map = { pending: '待发送', sent: '已发送', failed: '失败' }
  return map[status] || status
}

function healthClass (health) {
  if (health >= 90) return 'health-good'
  if (health >= 70) return 'health-normal'
  return 'health-bad'
}

function sentimentTagType (s) {
  const map = { positive: 'success', negative: 'danger', neutral: 'info' }
  return map[s] || 'info'
}

function sentimentLabel (s) {
  const map = { positive: '正面', negative: '负面', neutral: '中性' }
  return map[s] || s
}

function leadLevelType (level) {
  const map = { A: 'success', B: 'primary', C: 'warning', D: 'info' }
  return map[level] || 'info'
}

// ════════════════════════════════════════════
// Tab 5: 养号
// ════════════════════════════════════════════
const nurtureForm = reactive({
  platform: 'douyin',
  browseCount: 200,
  likeProbability: 50,
  commentProbability: 20,
  stayDuration: 15,
  timeRange: null,
})
const nurtureLoading = ref(false)
const nurtureRunning = ref(false)
const nurtureLogs = ref([])

async function startNurture() {
  nurtureLoading.value = true
  try {
    await axios.post('/api/acquisition/nurture/start', {
      platform: nurtureForm.platform,
      browse_count: nurtureForm.browseCount,
      like_probability: nurtureForm.likeProbability,
      comment_probability: nurtureForm.commentProbability,
      stay_duration: nurtureForm.stayDuration,
    })
    nurtureRunning.value = true
    nurtureLogs.value.unshift({
      time: new Date().toLocaleString('zh-CN'),
      platform: nurtureForm.platform,
      browsed: 0,
      liked: 0,
      commented: 0,
      status: 'running',
    })
    ElMessage.success('养号任务已启动')
  } catch (e) {
    ElMessage.error('启动失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    nurtureLoading.value = false
  }
}

function stopNurture() {
  nurtureRunning.value = false
  if (nurtureLogs.value.length) nurtureLogs.value[0].status = 'done'
  ElMessage.info('养号任务已停止')
}

// ════════════════════════════════════════════
// Tab 6: 平台状态
// ════════════════════════════════════════════
import { useRouter } from 'vue-router'
const _router = useRouter()

const platformStatusList = ref([
  { platform: 'douyin', name: '抖音', online: false, account: '', lastActive: '' },
  { platform: 'xhs', name: '小红书', online: false, account: '', lastActive: '' },
  { platform: 'bilibili', name: 'B站', online: false, account: '', lastActive: '' },
  { platform: 'kuaishou', name: '快手', online: false, account: '', lastActive: '' },
])

async function loadPlatformStatus() {
  try {
    const { data } = await axios.get('/api/platforms')
    const platforms = data.platforms || data || []
    platformStatusList.value = platformStatusList.value.map(p => {
      const found = platforms.find(f => f.platform === p.platform || f.name === p.platform)
      return found ? { ...p, online: found.online ?? found.status === 'online', account: found.account || found.nickname || '', lastActive: found.last_active || '' } : p
    })
  } catch {
    // 静默
  }
}

function goToPlatformSettings(platform) {
  _router.push('/settings/platforms')
}
</script>

<style scoped>
.acquisition-studio {
  padding: 24px;
}

.page-title {
  margin: 0 0 20px;
  font-size: 18px;
  color: var(--text-primary);
}

.tab-content {
  padding: 16px 0;
}

.card-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

/* ── Tab 1: 搜索截流 ── */
.search-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
  margin-bottom: 16px;
}

.search-row {
  margin-bottom: 16px;
}

.search-input {
  max-width: 600px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 20px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-radius: var(--radius-md, 10px);
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
  transition: box-shadow 0.25s ease, border-color 0.25s ease;
}

.result-card.high-score {
  border-color: var(--border-active);
  box-shadow: var(--accent-glow-sm);
}

.thumbnail-wrap {
  flex-shrink: 0;
}

.thumbnail {
  width: 120px;
  height: 75px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 18px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

.result-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.result-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-meta {
  font-size: 13px;
  color: var(--text-secondary);
}

.meta-label {
  color: var(--text-tertiary);
}

.result-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.stat-icon {
  font-size: 12px;
}

.result-score {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 2px;
}

.score-label {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.score-progress {
  flex: 1;
  max-width: 200px;
}

.result-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

/* ── Tab 2: 截流任务 ── */
.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
}

.stat-inner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 4px;
}

.stat-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.stat-body {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-value.pending { color: var(--amber-500, #f59e0b); }
.stat-value.sent { color: var(--accent-primary, #166534); }
.stat-value.success { color: var(--green-500, #22c55e); }
.stat-value.failed { color: var(--rose-500, #f43f5e); }

.stat-label {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.queue-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
  margin-bottom: 16px;
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.batch-actions {
  display: flex;
  gap: 8px;
}

.rate-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
}

.rate-row {
  align-items: center;
}

.rate-item {
  text-align: center;
  padding: 8px 0;
}

.rate-label {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.rate-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.rate-sublabel {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.rate-progress {
  max-width: 200px;
  margin: 0 auto;
}

.health-value {
  font-size: 28px;
  font-weight: 700;
}

.health-good { color: #22c55e; }
.health-normal { color: #fbbf24; }
.health-bad { color: #f43f5e; }

/* ── Tab 3: 互动管理 ── */
.template-card,
.deai-card,
.banned-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
  margin-bottom: 16px;
}

.template-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kw-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}

.deai-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.deai-btn {
  align-self: flex-start;
}

.deai-result {
  min-height: 120px;
  padding: 12px;
  border-radius: var(--radius-sm, 6px);
  background: var(--bg-main, #f4f7f2);
  border: 1px solid var(--border-light, #e8f0e3);
}

.result-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}

.result-placeholder {
  font-size: 13px;
  color: var(--text-tertiary);
  text-align: center;
  padding-top: 30px;
}

.deai-stats {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.stat-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: var(--radius-sm, 6px);
  background: var(--hover-bg, #eef5ea);
}

.pill-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.pill-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.banned-input-row {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.banned-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: var(--radius-sm, 6px);
  font-size: 14px;
  font-weight: 600;
  width: fit-content;
}

.result-badge.pass { background: rgba(34, 197, 94, 0.1); color: #22c55e; }
.result-badge.warn { background: rgba(251, 191, 36, 0.1); color: #f59e0b; }
.result-badge.fail { background: rgba(244, 63, 94, 0.1); color: #f43f5e; }

.banned-words {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.words-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.detected-text {
  padding: 12px;
  border-radius: var(--radius-sm, 6px);
  background: var(--bg-main, #f4f7f2);
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.highlight-banned {
  background: rgba(244, 63, 94, 0.2);
  color: #f43f5e;
  padding: 1px 4px;
  border-radius: 4px;
  font-weight: 600;
}

/* ── Tab 4: 监听雷达 ── */
.target-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
  margin-bottom: 16px;
}

.target-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.monitor-row {
  margin-top: 16px;
}

.live-card,
.lead-card {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #d4e4cc);
}

.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 10px;
  padding: 2px 10px;
  border-radius: var(--radius-full, 999px);
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  font-size: 12px;
  font-weight: 600;
  vertical-align: middle;
}

.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.live-comments {
  max-height: 480px;
  overflow-y: auto;
  background: var(--bg-main, #f4f7f2);
  border-radius: var(--radius-sm, 6px);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.live-comment {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: var(--radius-sm, 6px);
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-light, #e8f0e3);
  transition: transform 0.2s ease;
}

.comment-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}

.comment-body {
  flex: 1;
  min-width: 0;
}

.comment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.comment-nickname {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.comment-time {
  font-size: 12px;
  color: var(--text-muted);
}

.comment-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 6px;
}

.comment-footer {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lead-list {
  max-height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.lead-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 10px;
  border-radius: var(--radius-sm, 6px);
  background: var(--bg-main, #f4f7f2);
  border: 1px solid var(--border-light, #e8f0e3);
}

.lead-info {
  flex: 1;
  min-width: 0;
}

.lead-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.lead-summary {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lead-empty {
  text-align: center;
  padding: 40px 0;
  color: var(--text-tertiary);
  font-size: 13px;
}

.lead-actions {
  margin-top: 16px;
  text-align: center;
}

/* ── Tab 5: 养号 ── */
.nurture-card { background: var(--card-bg); border: 1px solid var(--border-color); }
.nurture-card :deep(.el-card__body) { padding: 20px; }

/* ── Tab 6: 平台状态 ── */
.status-card { background: var(--card-bg); border: 1px solid var(--border-color); transition: all 0.3s; }
.status-card.online { border-color: #22c55e; }
.status-card.offline { border-color: var(--border-color); opacity: 0.8; }
.status-card :deep(.el-card__body) { padding: 20px; }
.status-card-inner { display: flex; flex-direction: column; gap: 12px; align-items: flex-start; }
.status-platform-name { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.status-indicator { display: flex; align-items: center; gap: 8px; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; }
.status-dot.online { background: #22c55e; box-shadow: 0 0 8px rgba(34, 197, 94, 0.5); }
.status-dot.offline { background: var(--text-muted); }
.status-text { font-size: 13px; color: var(--text-secondary); }
.status-meta { font-size: 12px; color: var(--text-tertiary); line-height: 1.6; }

/* ── Responsive tweaks ── */
@media (max-width: 768px) {
  .filter-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .result-card {
    flex-direction: column;
  }
  .thumbnail {
    width: 100%;
    height: 120px;
  }
  .monitor-row .el-col {
    margin-bottom: 16px;
  }
}
</style>
