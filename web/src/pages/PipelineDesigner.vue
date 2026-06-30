<template>
  <div class="page-placeholder">
    <h2 class="page-title">流水线编排</h2>
    <div class="pipeline-layout">
      <div class="node-palette">
        <div class="palette-title">节点类型</div>
        <div v-for="n in nodeTypes" :key="n.type" class="palette-item" draggable="true" @dragstart="onDragStart($event, n)">
          <el-icon><component :is="n.icon" /></el-icon>
          <span>{{ n.label }}</span>
        </div>
      </div>
      <div class="canvas-area" @drop="onDrop" @dragover.prevent>
        <el-empty description="拖拽节点到画布开始编排流水线" />
      </div>
      <div class="props-panel">
        <div class="props-title">属性面板</div>
        <el-empty :image-size="60" description="选择节点查看属性" />
      </div>
    </div>
    <div class="template-bar">
      <span class="template-label">模板库:</span>
      <el-tag v-for="t in templates" :key="t.name" class="template-tag" effect="plain" @click="loadTemplate(t)">
        {{ t.label }}
      </el-tag>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { EditPen, Picture, VideoCamera, Headset, Tools } from '@element-plus/icons-vue'

const nodeTypes = [
  { type: 'text', label: '文本生成', icon: 'EditPen' },
  { type: 'image', label: '图像生成', icon: 'Picture' },
  { type: 'video', label: '视频生成', icon: 'VideoCamera' },
  { type: 'audio', label: '语音合成', icon: 'Headset' },
  { type: 'skill', label: '技能调用', icon: 'Tools' },
]
const templates = [
  { name: 'video-create', label: 'AI短视频' },
  { name: 'content-create', label: '智能内容' },
  { name: 'image-set', label: 'AI图集' },
]

function onDragStart(e, node) { e.dataTransfer.setData('node', JSON.stringify(node)) }
function onDrop() {}
function loadTemplate(t) {}
</script>

<style scoped>
.page-placeholder { padding: 0; }
.page-title { margin: 0 0 16px; font-size: 18px; }
.pipeline-layout { display: flex; gap: 1px; background: var(--border-color); height: calc(100vh - 220px); }
.node-palette { width: 180px; background: var(--sidebar-bg, var(--header-bg)); padding: 12px; }
.palette-title { font-size: 12px; font-weight: 600; color: var(--text-tertiary); margin-bottom: 8px; }
.palette-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; cursor: grab; font-size: 13px; margin-bottom: 4px; }
.palette-item:hover { background: var(--hover-bg); }
.canvas-area { flex: 1; background: var(--bg-main); display: flex; align-items: center; justify-content: center; }
.props-panel { width: 260px; background: var(--sidebar-bg, var(--header-bg)); padding: 12px; }
.props-title { font-size: 12px; font-weight: 600; color: var(--text-tertiary); margin-bottom: 8px; }
.template-bar { display: flex; align-items: center; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border-color); }
.template-label { font-size: 12px; color: var(--text-tertiary); }
.template-tag { cursor: pointer; }
</style>
