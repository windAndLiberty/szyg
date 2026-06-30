<template>
  <div class="page-placeholder">
    <h2 class="page-title">风控策略</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <el-tab-pane label="行为模拟" name="behavior">
        <el-form :model="behaviorForm" label-width="140px" class="param-form">
          <el-form-item label="点击间隔(秒)">
            <el-slider v-model="behaviorForm.clickInterval" :min="1" :max="10" :step="1" show-input />
          </el-form-item>
          <el-form-item label="鼠标轨迹随机度">
            <el-slider v-model="behaviorForm.mouseRandomness" :min="0" :max="100" :step="5" show-input />
          </el-form-item>
          <el-form-item label="浏览停留(秒)">
            <el-slider v-model="behaviorForm.browseStay" :min="3" :max="60" :step="3" show-input />
          </el-form-item>
          <el-form-item label="操作间隔随机偏移">
            <el-slider v-model="behaviorForm.intervalJitter" :min="0" :max="100" :step="5" show-input />
          </el-form-item>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="限额控制" name="limits">
        <el-form :model="limitsForm" label-width="160px" class="param-form">
          <el-form-item label="每日发布上限"><el-input-number v-model="limitsForm.dailyPublish" :min="1" :max="50" /></el-form-item>
          <el-form-item label="每日评论上限"><el-input-number v-model="limitsForm.dailyComment" :min="1" :max="200" /></el-form-item>
          <el-form-item label="每日私信上限"><el-input-number v-model="limitsForm.dailyDM" :min="1" :max="100" /></el-form-item>
          <el-form-item label="每日加人上限"><el-input-number v-model="limitsForm.dailyAddFriend" :min="1" :max="50" /></el-form-item>
          <el-form-item label="智能错峰">
            <el-switch v-model="limitsForm.smartStagger" active-text="开启" inactive-text="关闭" />
          </el-form-item>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="养号策略" name="nurture">
        <el-form :model="nurtureForm" label-width="140px" class="param-form">
          <el-form-item label="养号时段">
            <el-time-picker v-model="nurtureForm.timeRange" is-range range-separator="至" start-placeholder="开始" end-placeholder="结束" />
          </el-form-item>
          <el-form-item label="点赞概率">
            <el-slider v-model="nurtureForm.likeProbability" :min="0" :max="100" :step="5" show-input />
          </el-form-item>
          <el-form-item label="评论概率">
            <el-slider v-model="nurtureForm.commentProbability" :min="0" :max="100" :step="5" show-input />
          </el-form-item>
          <el-form-item label="浏览视频数">
            <el-input-number v-model="nurtureForm.browseCount" :min="10" :max="500" :step="10" />
          </el-form-item>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="内容安全" name="content">
        <el-form :model="contentForm" label-width="140px" class="param-form">
          <el-form-item label="合规检查">
            <el-switch v-model="contentForm.complianceCheck" active-text="开启" inactive-text="关闭" />
          </el-form-item>
          <el-form-item label="敏感词过滤">
            <el-switch v-model="contentForm.sensitiveFilter" active-text="开启" inactive-text="关闭" />
          </el-form-item>
          <el-form-item label="敏感词库">
            <el-input v-model="contentForm.sensitiveWords" type="textarea" :rows="5" placeholder="每行一个敏感词" />
          </el-form-item>
          <el-form-item label="硬广识别">
            <el-switch v-model="contentForm.hardAdDetect" active-text="开启" inactive-text="关闭" />
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
    <div class="save-bar">
      <el-button type="primary" @click="saveConfig">保存配置</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('behavior')
const behaviorForm = ref({ clickInterval: 3, mouseRandomness: 60, browseStay: 15, intervalJitter: 30 })
const limitsForm = ref({ dailyPublish: 10, dailyComment: 50, dailyDM: 30, dailyAddFriend: 20, smartStagger: true })
const nurtureForm = ref({ timeRange: null, likeProbability: 50, commentProbability: 20, browseCount: 200 })
const contentForm = ref({ complianceCheck: true, sensitiveFilter: true, sensitiveWords: '', hardAdDetect: true })

async function loadConfig() {
  try {
    const { data } = await axios.get('/api/risk-control/config')
    behaviorForm.value = data.behavior || behaviorForm.value
    limitsForm.value = data.limits || limitsForm.value
    nurtureForm.value = data.nurture || nurtureForm.value
    contentForm.value = data.content || contentForm.value
  } catch (e) {
    ElMessage.error('加载风控配置失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadConfig()
})

async function saveConfig() {
  try {
    await axios.put('/api/risk-control/config', {
      behavior: behaviorForm.value,
      limits: limitsForm.value,
      nurture: nurtureForm.value,
      content: contentForm.value,
    })
    ElMessage.success('风控配置已保存')
  } catch (e) {
    ElMessage.error('配置保存失败: ' + (e.response?.data?.detail || e.message))
  }
}
</script>

<style scoped>
.page-placeholder { padding: 0; }
.page-title { margin: 0 0 16px; font-size: 18px; }
.studio-tabs { border-radius: 8px; }
.param-form { max-width: 600px; padding: 24px; }
.save-bar { padding: 16px 24px; }
</style>
