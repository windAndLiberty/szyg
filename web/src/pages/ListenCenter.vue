<template>
  <div class="page-placeholder">
    <h2 class="page-title">舆情监听</h2>
    <div class="listen-layout">
      <div class="listen-sidebar">
        <div class="sidebar-header">
          <span>监听目标</span>
          <el-button text size="small" @click="showAdd = true"><el-icon><Plus /></el-icon></el-button>
        </div>
        <div class="target-list">
          <div v-for="t in targets" :key="t.id" class="target-item" :class="{ active: t.id === activeTarget }" @click="activeTarget = t.id">
            <div class="target-platform"><el-tag size="small">{{ t.platform }}</el-tag></div>
            <div class="target-title">{{ t.title }}</div>
            <div class="target-stats">
              <span>新评论: {{ t.newComments }}</span>
              <span>线索: {{ t.leads }}</span>
            </div>
          </div>
          <el-empty v-if="!targets.length" :image-size="60" description="暂无监听目标" />
        </div>
      </div>
      <div class="listen-main">
        <div class="listen-toolbar">
          <el-switch v-model="engineRunning" active-text="监听引擎运行中" inactive-text="已停止" @change="toggleEngine" />
          <span class="engine-info">轮询间隔: {{ pollInterval }}s | 已发现线索: {{ totalLeads }}</span>
        </div>
        <div class="comment-stream">
          <div v-for="c in comments" :key="c.id" class="comment-item">
            <div class="comment-header">
              <span class="comment-author">{{ c.author }}</span>
              <el-tag size="small" :type="sentimentType(c.sentiment)">{{ sentimentLabel(c.sentiment) }}</el-tag>
            </div>
            <div class="comment-text">{{ c.text }}</div>
            <div class="comment-time">{{ c.time }}</div>
          </div>
          <el-empty v-if="!comments.length" description="暂无评论数据" />
        </div>
      </div>
    </div>
    <el-dialog v-model="showAdd" title="添加监听目标" width="500px">
      <el-form label-width="80px">
        <el-form-item label="平台"><el-select v-model="addForm.platform"><el-option label="抖音" value="douyin" /><el-option label="小红书" value="xhs" /><el-option label="B站" value="bilibili" /><el-option label="快手" value="kuaishou" /></el-select></el-form-item>
        <el-form-item label="视频URL"><el-input v-model="addForm.url" placeholder="粘贴视频链接" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showAdd = false">取消</el-button><el-button type="primary" @click="addTarget">添加</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const activeTarget = ref(null)
const engineRunning = ref(false)
const pollInterval = ref(60)
const totalLeads = ref(0)
const showAdd = ref(false)
const addForm = ref({ platform: 'douyin', url: '' })
const targets = ref([])
const comments = ref([])

function sentimentType(s) { return { positive: 'success', negative: 'danger', question: 'warning', lead: 'primary' }[s] || 'info' }
function sentimentLabel(s) { return { positive: '正面', negative: '负面', question: '提问', lead: '线索' }[s] || '未知' }

function toggleEngine(val) {
  ElMessage.info(val ? '监听引擎已启动' : '监听引擎已停止')
}

function addTarget() {
  if (!addForm.value.url) { ElMessage.warning('请输入视频URL'); return }
  targets.value.push({ id: Date.now(), platform: addForm.value.platform, title: addForm.value.url.slice(0, 30), newComments: 0, leads: 0 })
  showAdd.value = false
  addForm.value = { platform: 'douyin', url: '' }
}
</script>

<style scoped>
.page-placeholder { padding: 0; }
.page-title { margin: 0 0 16px; font-size: 18px; }
.listen-layout { display: flex; gap: 1px; background: var(--border-color); height: calc(100vh - 160px); }
.listen-sidebar { width: 280px; background: var(--sidebar-bg, var(--header-bg)); display: flex; flex-direction: column; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-color); font-size: 13px; font-weight: 600; }
.target-list { flex: 1; overflow-y: auto; padding: 8px; }
.target-item { padding: 10px 12px; border-radius: 8px; cursor: pointer; margin-bottom: 4px; }
.target-item:hover { background: var(--hover-bg); }
.target-item.active { background: var(--accent-soft); }
.target-title { font-size: 12px; margin: 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.target-stats { font-size: 11px; color: var(--text-tertiary); display: flex; gap: 12px; }
.listen-main { flex: 1; display: flex; flex-direction: column; background: var(--bg-main); }
.listen-toolbar { display: flex; align-items: center; gap: 16px; padding: 12px 16px; border-bottom: 1px solid var(--border-color); }
.engine-info { font-size: 12px; color: var(--text-tertiary); }
.comment-stream { flex: 1; overflow-y: auto; padding: 16px; }
.comment-item { padding: 12px; border-bottom: 1px solid var(--border-color); }
.comment-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.comment-author { font-size: 13px; font-weight: 600; }
.comment-text { font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.comment-time { font-size: 11px; color: var(--text-tertiary); margin-top: 4px; }
</style>
