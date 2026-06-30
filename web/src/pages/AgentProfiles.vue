<template>
  <div class="agent-profiles">
    <div class="page-header">
      <h2 class="page-title">员工配置</h2>
      <p class="page-subtitle">AI 员工角色与能力配置</p>
    </div>

    <div class="profiles-layout">
      <!-- Left: Agent List -->
      <div class="agent-list">
        <div
          v-for="agent in agents"
          :key="agent.id"
          class="agent-card"
          :class="{ active: selectedAgent?.id === agent.id }"
          @click="selectAgent(agent)"
        >
          <div class="agent-emoji" :style="{ backgroundColor: agent.color + '20' }">
            {{ agent.emoji }}
          </div>
          <div class="agent-info">
            <div class="agent-name">
              {{ agent.name }}
              <el-tag v-if="!agent.enabled" type="info" size="small">已禁用</el-tag>
            </div>
            <div class="agent-id">{{ agent.id }}</div>
          </div>
          <div class="agent-arrow">▶</div>
        </div>
      </div>

      <!-- Right: Config Panel -->
      <div class="config-panel">
        <div v-if="selectedAgent" class="config-content">
          <div class="config-header">
            <div class="config-header-left">
              <span class="config-emoji">{{ selectedAgent.emoji }}</span>
              <span class="config-header-title">{{ selectedAgent.name }} 配置</span>
            </div>
            <el-button type="primary" @click="showDeployDialog = true">
              <el-icon><Upload /></el-icon> 一键部署
            </el-button>
          </div>

          <el-collapse v-model="activeCollapse" class="config-collapse">
            <!-- 基础配置 -->
            <el-collapse-item name="basic" title="基础配置">
              <div class="config-group">
                <el-form label-width="120px">
                  <el-form-item label="角色名称">
                    <el-input v-model="currentConfig.basic.name" />
                  </el-form-item>
                  <el-form-item label="角色描述">
                    <el-input v-model="currentConfig.basic.description" type="textarea" :rows="2" />
                  </el-form-item>
                  <el-form-item label="头像">
                    <div class="avatar-picker">
                      <span class="avatar-preview">{{ currentConfig.basic.avatar }}</span>
                      <el-button link size="small" @click="cycleAvatar">切换</el-button>
                    </div>
                  </el-form-item>
                  <el-form-item label="启用状态">
                    <el-switch v-model="currentConfig.basic.enabled" />
                  </el-form-item>
                </el-form>
              </div>
            </el-collapse-item>

            <!-- SOUL 配置 -->
            <el-collapse-item name="soul" title="SOUL 配置">
              <div class="config-group">
                <el-form label-width="120px">
                  <el-form-item label="系统提示词">
                    <el-input v-model="currentConfig.soul.systemPrompt" type="textarea" :rows="4" placeholder="输入系统提示词，定义 AI 的核心行为..." />
                  </el-form-item>
                  <el-form-item label="行为模式">
                    <el-radio-group v-model="currentConfig.soul.behaviorMode">
                      <el-radio-button label="cautious">谨慎</el-radio-button>
                      <el-radio-button label="balanced">均衡</el-radio-button>
                      <el-radio-button label="fast">快速</el-radio-button>
                    </el-radio-group>
                  </el-form-item>
                  <el-form-item label="温度系数">
                    <div class="slider-row">
                      <el-slider v-model="currentConfig.soul.temperature" :min="0" :max="2" :step="0.1" style="flex:1" />
                      <span class="slider-value">{{ currentConfig.soul.temperature }}</span>
                    </div>
                  </el-form-item>
                </el-form>
              </div>
            </el-collapse-item>

            <!-- Memory 配置 -->
            <el-collapse-item name="memory" title="Memory 配置">
              <div class="config-group">
                <el-form label-width="140px">
                  <el-form-item label="短期记忆深度">
                    <el-input-number v-model="currentConfig.memory.shortTermDepth" :min="1" :max="50" :step="1" />
                  </el-form-item>
                  <el-form-item label="长期记忆启用">
                    <el-switch v-model="currentConfig.memory.longTermEnabled" />
                  </el-form-item>
                  <el-form-item label="知识库关联">
                    <el-select v-model="currentConfig.memory.knowledgeBases" multiple placeholder="选择知识库" style="width:100%">
                      <el-option label="产品知识库" value="product" />
                      <el-option label="销售话术库" value="sales" />
                      <el-option label="品牌规范库" value="brand" />
                      <el-option label="竞品分析库" value="competitor" />
                    </el-select>
                  </el-form-item>
                </el-form>
              </div>
            </el-collapse-item>

            <!-- Skills 配置 -->
            <el-collapse-item name="skills" title="Skills 配置">
              <div class="config-group">
                <div class="skills-section">
                  <div class="skills-subtitle">已启用技能</div>
                  <div class="skills-list">
                    <div
                      v-for="skill in currentConfig.skills.list"
                      :key="skill.id"
                      class="skill-item"
                    >
                      <el-checkbox v-model="skill.enabled" size="small">
                        {{ skill.name }}
                      </el-checkbox>
                      <span class="skill-desc">{{ skill.description }}</span>
                    </div>
                  </div>
                </div>
                <div class="skills-section">
                  <div class="skills-subtitle">技能优先级</div>
                  <div class="priority-list">
                    <div
                      v-for="(skill, index) in enabledSkillsSorted"
                      :key="skill.id"
                      class="priority-item"
                    >
                      <span class="priority-rank">{{ index + 1 }}</span>
                      <span class="priority-name">{{ skill.name }}</span>
                      <div class="priority-actions">
                        <el-button
                          v-if="index > 0"
                          link
                          size="small"
                          @click="moveSkillUp(index)"
                        >
                          <el-icon><ArrowUp /></el-icon>
                        </el-button>
                        <el-button
                          v-if="index < enabledSkillsSorted.length - 1"
                          link
                          size="small"
                          @click="moveSkillDown(index)"
                        >
                          <el-icon><ArrowDown /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                  <div v-if="enabledSkillsSorted.length === 0" class="priority-empty">
                    暂无启用的技能
                  </div>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>

          <div class="config-footer">
            <el-button @click="resetConfig">重置</el-button>
            <el-button type="primary" @click="saveConfig">
              <el-icon><Check /></el-icon> 保存配置
            </el-button>
          </div>
        </div>

        <div v-else class="config-empty">
          <el-empty description="请选择左侧员工进行配置" />
        </div>
      </div>
    </div>

    <!-- Deploy Dialog -->
    <el-dialog v-model="showDeployDialog" title="一键部署" width="420px">
      <div class="deploy-dialog">
        <p class="deploy-desc">选择预设模板，自动填充所有配置字段</p>
        <el-select v-model="deployTemplate" placeholder="选择模板" style="width:100%">
          <el-option label="标准模板（默认）" value="default" />
          <el-option label="高效执行模板" value="fast" />
          <el-option label="安全保守模板" value="safe" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="showDeployDialog = false">取消</el-button>
        <el-button type="primary" @click="oneClickDeploy">部署</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, ArrowUp, ArrowDown, Upload } from '@element-plus/icons-vue'
import axios from 'axios'

const agents = ref([])

async function loadAgents() {
  try {
    const { data } = await axios.get('/api/staff/list')
    const staffList = data?.staff || []
    agents.value = staffList.map(s => ({
      id: s.id,
      name: s.name,
      emoji: s.emoji,
      color: s.color || '#4f46e5',
      enabled: s.status === 'running',
      status: s.status,
    }))
  } catch (e) {
    ElMessage.error('加载员工列表失败: ' + (e.response?.data?.detail || e.message))
  }
}

// Default config fallback (used when API not available)
const defaultConfigs = {
  content: {
    basic: { name: '内容专员', description: '负责内容创作、文案撰写、脚本生成', avatar: '📝', enabled: true },
    soul: { systemPrompt: '你是一位专业的内容创作专员，擅长短视频脚本、社交媒体文案和品牌内容输出。请确保内容符合品牌调性，语言生动有趣。', behaviorMode: 'balanced', temperature: 0.8 },
    memory: { shortTermDepth: 10, longTermEnabled: true, knowledgeBases: ['product', 'brand'] },
    skills: {
      list: [
        { id: 'script', name: '脚本生成', description: '自动生成短视频脚本', enabled: true, priority: 1 },
        { id: 'copy', name: '文案撰写', description: '撰写社交媒体文案', enabled: true, priority: 2 },
        { id: 'adapt', name: '多平台适配', description: '适配不同平台内容格式', enabled: true, priority: 3 },
        { id: 'aigc', name: 'AIGC图像', description: '生成配图和封面', enabled: false, priority: 4 },
      ]
    }
  },
  acquisition: {
    basic: { name: '获客专员', description: '负责公域拓客、搜索截流、评论互动', avatar: '🎯', enabled: true },
    soul: { systemPrompt: '你是一位精准的获客专员，擅长通过关键词搜索、评论互动和截流策略获取高意向客户。行为要自然，避免过度营销。', behaviorMode: 'fast', temperature: 0.9 },
    memory: { shortTermDepth: 15, longTermEnabled: true, knowledgeBases: ['sales', 'competitor'] },
    skills: {
      list: [
        { id: 'search', name: '搜索截流', description: '关键词搜索与线索截流', enabled: true, priority: 1 },
        { id: 'comment', name: '评论生成', description: '自动生成互动评论', enabled: true, priority: 2 },
        { id: 'deai', name: 'DeAI处理', description: '智能线索评分', enabled: true, priority: 3 },
        { id: 'reply', name: '自动回复', description: '私信自动接待', enabled: false, priority: 4 },
      ]
    }
  },
  conversion: {
    basic: { name: '转化专员', description: '负责私域转化、客户跟进、成交推进', avatar: '💰', enabled: true },
    soul: { systemPrompt: '你是一位专业的销售转化专员，擅长客户跟进、需求挖掘和成交推进。请以客户为中心，提供个性化解决方案。', behaviorMode: 'cautious', temperature: 0.6 },
    memory: { shortTermDepth: 20, longTermEnabled: true, knowledgeBases: ['sales', 'product'] },
    skills: {
      list: [
        { id: 'lead', name: '线索管理', description: '管理和跟进销售线索', enabled: true, priority: 1 },
        { id: 'sop', name: 'SOP执行', description: '执行标准销售流程', enabled: true, priority: 2 },
        { id: 'bridge', name: '微信桥接', description: '私域客户桥接管理', enabled: true, priority: 3 },
        { id: 'knowledge', name: '知识库检索', description: '检索产品知识库', enabled: false, priority: 4 },
      ]
    }
  },
  ops: {
    basic: { name: '运营专员', description: '负责调度引擎、数据报告、审计日志', avatar: '🚀', enabled: true },
    soul: { systemPrompt: '你是一位运营调度专员，负责协调各 AI 员工的工作流、生成数据报告并监控系统运行状态。请确保调度高效、数据准确。', behaviorMode: 'balanced', temperature: 0.7 },
    memory: { shortTermDepth: 8, longTermEnabled: false, knowledgeBases: ['product'] },
    skills: {
      list: [
        { id: 'scheduler', name: '调度引擎', description: '任务调度与定时执行', enabled: true, priority: 1 },
        { id: 'abtest', name: 'A/B测试', description: '策略对比测试', enabled: true, priority: 2 },
        { id: 'report', name: '数据报告', description: '自动生成运营报告', enabled: true, priority: 3 },
        { id: 'audit', name: '审计日志', description: '操作日志记录与分析', enabled: false, priority: 4 },
      ]
    }
  }
}

// Template presets for one-click deploy
const templatePresets = {
  default: { behaviorMode: 'balanced', temperature: 0.7, shortTermDepth: 10 },
  fast: { behaviorMode: 'fast', temperature: 0.9, shortTermDepth: 5 },
  safe: { behaviorMode: 'cautious', temperature: 0.5, shortTermDepth: 20 },
}

const selectedAgent = ref(null)
const activeCollapse = ref(['basic', 'soul'])
const showDeployDialog = ref(false)
const deployTemplate = ref('default')

// Deep clone helper
const deepClone = (obj) => JSON.parse(JSON.stringify(obj))

const agentConfigs = ref({})

async function loadConfigs() {
  try {
    const { data } = await axios.get('/api/staff/configs/list')
    agentConfigs.value = data.configs || {}
    // Select first agent after load
    if (agents.value.length > 0 && !selectedAgent.value) {
      selectAgent(agents.value[0])
    }
  } catch {
    // Fallback to defaults if API unavailable
    agentConfigs.value = {
      content: deepClone(defaultConfigs.content),
      acquisition: deepClone(defaultConfigs.acquisition),
      conversion: deepClone(defaultConfigs.conversion),
      ops: deepClone(defaultConfigs.ops),
    }
    if (agents.value.length > 0 && !selectedAgent.value) {
      selectAgent(agents.value[0])
    }
  }
}

onMounted(() => {
  loadAgents()
  loadConfigs()
})

const currentConfig = ref(null)

const selectAgent = (agent) => {
  selectedAgent.value = agent
  const cfg = agentConfigs.value[agent.id]
  if (cfg) {
    currentConfig.value = cfg
  } else if (defaultConfigs[agent.id]) {
    currentConfig.value = deepClone(defaultConfigs[agent.id])
  }
}

// Select first agent after data is loaded

const enabledSkillsSorted = computed(() => {
  if (!currentConfig.value) return []
  return currentConfig.value.skills.list
    .filter(s => s.enabled)
    .sort((a, b) => a.priority - b.priority)
})

const cycleAvatar = () => {
  const avatars = ['📝', '🎯', '💰', '🚀', '🤖', '👤', '⭐', '🔧']
  const idx = avatars.indexOf(currentConfig.value.basic.avatar)
  currentConfig.value.basic.avatar = avatars[(idx + 1) % avatars.length]
}

const moveSkillUp = (index) => {
  const list = enabledSkillsSorted.value
  if (index <= 0) return
  const prev = list[index - 1]
  const curr = list[index]
  const temp = prev.priority
  prev.priority = curr.priority
  curr.priority = temp
}

const moveSkillDown = (index) => {
  const list = enabledSkillsSorted.value
  if (index >= list.length - 1) return
  const next = list[index + 1]
  const curr = list[index]
  const temp = next.priority
  next.priority = curr.priority
  curr.priority = temp
}

const saveConfig = async () => {
  if (!selectedAgent.value) return
  const id = selectedAgent.value.id
  agentConfigs.value[id] = deepClone(currentConfig.value)
  try {
    await axios.put(`/api/staff/configs/${id}`, {
      basic: currentConfig.value.basic,
      soul: currentConfig.value.soul,
      memory: currentConfig.value.memory,
      skills: currentConfig.value.skills,
    })
    ElMessage.success('配置已保存到服务器')
  } catch (e) {
    ElMessage.warning('配置已保存到本地（服务器不可用）')
  }
}

const resetConfig = async () => {
  if (!selectedAgent.value) return
  const id = selectedAgent.value.id
  try {
    const { data } = await axios.post(`/api/staff/configs/${id}/reset`)
    currentConfig.value = data.config
    agentConfigs.value[id] = data.config
    ElMessage.info('配置已重置为默认值')
  } catch {
    currentConfig.value = deepClone(defaultConfigs[id])
    agentConfigs.value[id] = deepClone(defaultConfigs[id])
    ElMessage.info('配置已重置为默认值（本地）')
  }
}

const oneClickDeploy = () => {
  if (!selectedAgent.value || !deployTemplate.value) return
  const preset = templatePresets[deployTemplate.value]
  const cfg = currentConfig.value
  cfg.soul.behaviorMode = preset.behaviorMode
  cfg.soul.temperature = preset.temperature
  cfg.memory.shortTermDepth = preset.shortTermDepth
  // Auto-enable all skills
  cfg.skills.list.forEach(s => { s.enabled = true })
  showDeployDialog.value = false
  ElMessage.success('配置已部署')
}
</script>

<style scoped>
.agent-profiles {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.page-header {
  margin-bottom: 20px;
  flex-shrink: 0;
}

.page-title {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}

.profiles-layout {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

.agent-list {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.agent-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-card);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: box-shadow var(--duration-fast) ease;
}

.agent-card:hover {
  box-shadow: var(--shadow-card);
}

.agent-card.active {
  background: var(--accent-soft);
}

.agent-emoji {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm, 6px);
  font-size: 20px;
  flex-shrink: 0;
}

.agent-info {
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.agent-id {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
}

.agent-arrow {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.agent-card.active .agent-arrow {
  color: var(--accent);
}

.config-panel {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--bg-card);
  border: none;
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow-card);
}

.config-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-light);
}

.config-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.config-emoji {
  font-size: 24px;
}

.config-header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.config-collapse {
  flex: 1;
  min-height: 0;
}

.config-collapse :deep(.el-collapse-item__header) {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.config-group {
  padding: 8px 0;
}

.avatar-picker {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar-preview {
  font-size: 28px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-value {
  font-size: 13px;
  color: var(--text-secondary);
  min-width: 32px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.skills-section {
  margin-bottom: 16px;
}

.skills-subtitle {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.skill-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: auto;
}

.priority-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.priority-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.priority-rank {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  border-radius: 50%;
  flex-shrink: 0;
}

.priority-name {
  font-size: 13px;
  color: var(--text-primary);
  flex: 1;
}

.priority-actions {
  display: flex;
  gap: 4px;
}

.priority-empty {
  font-size: 13px;
  color: var(--text-tertiary);
  text-align: center;
  padding: 16px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.config-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.config-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.deploy-dialog {
  padding: 8px 0;
}

.deploy-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

/* Responsive */
@media (max-width: 991px) {
  .profiles-layout {
    flex-direction: column;
  }

  .agent-list {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
  }

  .agent-card {
    min-width: 180px;
  }
}
</style>
