<template>
  <div class="task-board">
    <!-- Toolbar -->
    <div class="toolbar">
      <el-button type="primary" @click="openNewTaskDialog">
        <el-icon><Plus /></el-icon>
        新建任务
      </el-button>
      <div class="filters">
        <el-select
          v-model="filterAssignee"
          placeholder="按员工筛选"
          clearable
          size="small"
          style="width: 140px"
        >
          <el-option label="全部" value="" />
          <el-option
            v-for="staff in assigneeOptions"
            :key="staff"
            :label="staff"
            :value="staff"
          />
        </el-select>
        <el-select
          v-model="filterStatus"
          placeholder="按状态筛选"
          clearable
          size="small"
          style="width: 140px"
        >
          <el-option label="全部" value="" />
          <el-option label="高优先级" value="high" />
          <el-option label="今日截止" value="today" />
        </el-select>
      </div>
    </div>

    <!-- Kanban Columns -->
    <div class="board-columns">
      <div
        v-for="col in columns"
        :key="col.key"
        class="board-column"
        :style="{ borderLeftColor: col.color }"
        @dragover.prevent
        @drop="handleDrop(col.key, $event)"
      >
        <div class="column-header" :style="{ color: col.color }">
          <span class="column-title">{{ col.title }}</span>
          <span class="column-count">{{ filteredTasksByColumn(col.key).length }}</span>
        </div>
        <div class="column-body">
          <div
            v-for="task in filteredTasksByColumn(col.key)"
            :key="task.id"
            class="task-card"
            :class="{ 'review-card': col.key === 'review' }"
            draggable="true"
            @dragstart="handleDragStart(task, $event)"
          >
            <div class="task-name">{{ task.name }}</div>

            <!-- Review badges -->
            <div v-if="col.key === 'review'" class="review-badges">
              <el-tag
                :type="reviewBadgeType(task.reviewStatus)"
                size="small"
                effect="dark"
                class="review-badge"
              >
                {{ reviewBadgeText(task.reviewStatus) }}
              </el-tag>
              <span v-if="task.reviewTime" class="review-time">{{ task.reviewTime }}</span>
            </div>

            <div class="task-meta">
              <el-tag
                :color="assigneeColor(task.assignee)"
                effect="dark"
                size="small"
                class="assignee-tag"
              >
                {{ task.assignee }}
              </el-tag>
              <el-tag
                :type="priorityType(task.priority)"
                size="small"
                class="priority-tag"
              >
                {{ priorityLabel(task.priority) }}
              </el-tag>
            </div>

            <el-progress
              :percentage="task.progress"
              :stroke-width="6"
              :color="col.color"
              :show-text="false"
              class="task-progress"
            />

            <div class="task-footer">
              <span class="deadline" :class="{ overdue: isOverdue(task.deadline) }">
                {{ task.deadline }}
              </span>
              <div class="task-actions">
                <!-- Submit for review button -->
                <el-button
                  v-if="canSubmitReview(task)"
                  type="warning"
                  link
                  size="small"
                  title="提交审核"
                  @click="submitForReview(task)"
                >
                  <el-icon><Check /></el-icon>
                </el-button>
                <!-- Review button (opens dialog) -->
                <el-button
                  v-if="task.status === 'review'"
                  type="primary"
                  link
                  size="small"
                  title="审核"
                  @click="openReviewDialog(task)"
                >
                  <el-icon><Search /></el-icon>
                </el-button>
                <el-button
                  type="primary"
                  link
                  size="small"
                  @click="editTask(task)"
                >
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button
                  type="danger"
                  link
                  size="small"
                  @click="deleteTask(task.id)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>

            <!-- Inline review actions (only in review column) -->
            <div v-if="task.status === 'review'" class="inline-review">
              <el-input
                v-model="task._reviewInput"
                type="textarea"
                :rows="2"
                placeholder="输入审核评论..."
                size="small"
                class="review-textarea"
              />
              <div class="inline-review-actions">
                <el-button
                  type="success"
                  size="small"
                  @click="approveReview(task, task._reviewInput)"
                >
                  <el-icon><Check /></el-icon> 通过
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click="rejectReview(task, task._reviewInput)"
                >
                  <el-icon><Close /></el-icon> 驳回
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- New Task Dialog -->
    <el-dialog
      v-model="dialogVisible"
      title="新建任务"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="newTaskForm"
        label-width="80px"
        :rules="formRules"
      >
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="newTaskForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="指派员工" prop="assignee">
          <el-select v-model="newTaskForm.assignee" placeholder="请选择员工" style="width: 100%">
            <el-option
              v-for="staff in assigneeOptions"
              :key="staff"
              :label="staff"
              :value="staff"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="newTaskForm.priority">
            <el-radio-button label="high">高</el-radio-button>
            <el-radio-button label="medium">中</el-radio-button>
            <el-radio-button label="low">低</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="截止日期" prop="deadline">
          <el-date-picker
            v-model="newTaskForm.deadline"
            type="date"
            placeholder="选择截止日期"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitNewTask">确定</el-button>
      </template>
    </el-dialog>

    <!-- Edit Task Dialog -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑任务"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="editFormRef"
        :model="editTaskForm"
        label-width="80px"
        :rules="formRules"
      >
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="editTaskForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="指派员工" prop="assignee">
          <el-select v-model="editTaskForm.assignee" placeholder="请选择员工" style="width: 100%">
            <el-option
              v-for="staff in assigneeOptions"
              :key="staff"
              :label="staff"
              :value="staff"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="editTaskForm.priority">
            <el-radio-button label="high">高</el-radio-button>
            <el-radio-button label="medium">中</el-radio-button>
            <el-radio-button label="low">低</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="截止日期" prop="deadline">
          <el-date-picker
            v-model="editTaskForm.deadline"
            type="date"
            placeholder="选择截止日期"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEditTask">确定</el-button>
      </template>
    </el-dialog>

    <!-- Review Dialog -->
    <el-dialog
      v-model="reviewDialogVisible"
      title="任务审核"
      width="520px"
      :close-on-click-modal="false"
    >
      <div v-if="reviewTarget" class="review-dialog-content">
        <div class="review-task-info">
          <div class="review-task-name">{{ reviewTarget.name }}</div>
          <div class="review-task-meta">
            <el-tag :color="assigneeColor(reviewTarget.assignee)" effect="dark" size="small">
              {{ reviewTarget.assignee }}
            </el-tag>
            <el-tag :type="priorityType(reviewTarget.priority)" size="small">
              {{ priorityLabel(reviewTarget.priority) }}
            </el-tag>
            <el-tag
              :type="reviewBadgeType(reviewTarget.reviewStatus)"
              size="small"
              effect="dark"
            >
              {{ reviewBadgeText(reviewTarget.reviewStatus) }}
            </el-tag>
          </div>
          <div class="review-task-detail">
            <span>进度：{{ reviewTarget.progress }}%</span>
            <span>截止：{{ reviewTarget.deadline }}</span>
            <span v-if="reviewTarget.reviewTime">提交时间：{{ reviewTarget.reviewTime }}</span>
          </div>
        </div>

        <div class="review-comment-history">
          <div class="review-section-title">评论历史</div>
          <div v-if="reviewTarget.reviewComment" class="review-history-item">
            <div class="review-history-text">{{ reviewTarget.reviewComment }}</div>
          </div>
          <div v-else class="review-history-empty">暂无评论</div>
        </div>

        <el-input
          v-model="reviewDialogComment"
          type="textarea"
          :rows="3"
          placeholder="输入审核评论..."
          class="review-dialog-textarea"
        />
      </div>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">关闭</el-button>
        <el-button
          type="danger"
          @click="rejectReview(reviewTarget, reviewDialogComment); reviewDialogVisible = false"
        >
          <el-icon><Close /></el-icon> 驳回
        </el-button>
        <el-button
          type="success"
          @click="approveReview(reviewTarget, reviewDialogComment); reviewDialogVisible = false"
        >
          <el-icon><Check /></el-icon> 通过
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Check, Close, Search } from '@element-plus/icons-vue'
import axios from 'axios'

const columns = [
  { key: 'ready', title: '待执行', color: '#999999' },
  { key: 'running', title: '进行中', color: '#4f46e5' },
  { key: 'blocked', title: '受阻', color: '#d97706' },
  { key: 'review', title: '审核中', color: '#7c3aed' },
  { key: 'done', title: '已完成', color: '#16a34a' },
]

const tasks = ref([])

async function loadTasks() {
  try {
    const { data } = await axios.get('/api/staff/tasks/list')
    tasks.value = (data.tasks || []).map(t => ({ ...t, _reviewInput: '' }))
  } catch (e) {
    ElMessage.error('加载任务失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadTasks()
  loadAssignees()
})

const assigneeOptions = ref([])
const assigneeColors = ref({})

async function loadAssignees() {
  try {
    const { data } = await axios.get('/api/staff/list')
    const staff = data?.staff || []
    const colors = {}
    const presetColors = ['#4f46e5', '#6366f1', '#d97706', '#7c3aed', '#2563eb', '#dc2626', '#ca8a04', '#9333ea']
    assigneeOptions.value = staff.map((s, i) => {
      colors[s.name] = s.color || presetColors[i % presetColors.length]
      return s.name
    })
    assigneeColors.value = colors
  } catch {
    assigneeOptions.value = ['内容专员', '获客专员', '转化专员', '运营专员']
  }
}

const filterAssignee = ref('')
const filterStatus = ref('')

const todayStr = (() => {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
})()

const filteredTasks = computed(() => {
  let result = tasks.value

  if (filterAssignee.value) {
    result = result.filter(t => t.assignee === filterAssignee.value)
  }

  if (filterStatus.value === 'high') {
    result = result.filter(t => t.priority === 'high')
  } else if (filterStatus.value === 'today') {
    result = result.filter(t => t.deadline === todayStr)
  }

  return result
})

const filteredTasksByColumn = (columnKey) => {
  return filteredTasks.value.filter(t => t.status === columnKey)
}

const assigneeColor = (name) => assigneeColors.value[name] || '#6b7280'

const priorityType = (p) => {
  if (p === 'high') return 'danger'
  if (p === 'medium') return 'warning'
  return 'info'
}

const priorityLabel = (p) => {
  if (p === 'high') return '高'
  if (p === 'medium') return '中'
  return '低'
}

const isOverdue = (deadline) => deadline < todayStr

// Review helpers
const reviewBadgeType = (status) => {
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  return 'warning'
}

const reviewBadgeText = (status) => {
  if (status === 'approved') return '已通过'
  if (status === 'rejected') return '已驳回'
  return '待审核'
}

const canSubmitReview = (task) => {
  return task.status === 'blocked' || task.status === 'running'
}

const submitForReview = async (task) => {
  const reviewTime = `${todayStr} ${new Date().toTimeString().slice(0, 5)}`
  try {
    await axios.put(`/api/staff/tasks/${task.id}`, { status: 'review', reviewStatus: 'pending', reviewTime })
    task.status = 'review'
    task.reviewStatus = 'pending'
    task.reviewTime = reviewTime
    ElMessage.success('任务已提交审核')
  } catch (e) {
    ElMessage.error('提交失败: ' + (e.response?.data?.detail || e.message))
  }
}

const approveReview = async (task, comment) => {
  if (!task) return
  try {
    await axios.put(`/api/staff/tasks/${task.id}`, { status: 'done', reviewStatus: 'approved', progress: 100, reviewComment: comment || '' })
    task.status = 'done'
    task.reviewStatus = 'approved'
    task.progress = 100
    if (comment) task.reviewComment = comment
    ElMessage.success('审核已通过，任务已移至已完成')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}

const rejectReview = async (task, comment) => {
  if (!task) return
  try {
    await axios.put(`/api/staff/tasks/${task.id}`, { status: 'ready', reviewStatus: 'rejected', progress: 0, reviewComment: comment || '' })
    task.status = 'ready'
    task.reviewStatus = 'rejected'
    task.progress = 0
    if (comment) task.reviewComment = comment
    ElMessage.warning('任务已驳回，回到待执行列')
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}

// Review dialog
const reviewDialogVisible = ref(false)
const reviewTarget = ref(null)
const reviewDialogComment = ref('')

const openReviewDialog = (task) => {
  reviewTarget.value = task
  reviewDialogComment.value = ''
  reviewDialogVisible.value = true
}

// Drag and Drop
const draggedTaskId = ref(null)

const handleDragStart = (task, event) => {
  draggedTaskId.value = task.id
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(task.id))
}

const handleDrop = async (columnKey, event) => {
  event.preventDefault()
  const id = Number(event.dataTransfer.getData('text/plain')) || draggedTaskId.value
  if (!id) return

  const task = tasks.value.find(t => t.id === id)
  if (task && task.status !== columnKey) {
    const oldStatus = task.status
    task.status = columnKey
    if (columnKey === 'done') {
      task.progress = 100
    } else if (columnKey === 'ready') {
      task.progress = 0
    }
    try {
      await axios.put(`/api/staff/tasks/${id}`, { status: columnKey, progress: task.progress })
      ElMessage.success(`任务已移至"${columns.find(c => c.key === columnKey).title}"`)
    } catch (e) {
      task.status = oldStatus
      ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
    }
  }
  draggedTaskId.value = null
}

// New Task Dialog
const dialogVisible = ref(false)
const formRef = ref(null)
const newTaskForm = ref({
  name: '',
  assignee: '',
  priority: 'medium',
  deadline: '',
})

const formRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  assignee: [{ required: true, message: '请选择指派员工', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  deadline: [{ required: true, message: '请选择截止日期', trigger: 'change' }],
}

const openNewTaskDialog = () => {
  newTaskForm.value = {
    name: '',
    assignee: '',
    priority: 'medium',
    deadline: todayStr,
  }
  dialogVisible.value = true
}

const submitNewTask = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const { data } = await axios.post('/api/staff/tasks/create', newTaskForm.value)
        tasks.value.push({ ...data.task, _reviewInput: '' })
        dialogVisible.value = false
        ElMessage.success('任务创建成功')
      } catch (e) {
        ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
      }
    }
  })
}

// Edit Task
const editDialogVisible = ref(false)
const editFormRef = ref(null)
const editTaskForm = ref({
  id: null,
  name: '',
  assignee: '',
  priority: 'medium',
  deadline: '',
})

const editTask = (task) => {
  editTaskForm.value = { ...task }
  editDialogVisible.value = true
}

const submitEditTask = async () => {
  if (!editFormRef.value) return
  await editFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        await axios.put(`/api/staff/tasks/${editTaskForm.value.id}`, {
          name: editTaskForm.value.name,
          assignee: editTaskForm.value.assignee,
          priority: editTaskForm.value.priority,
          deadline: editTaskForm.value.deadline,
        })
        const idx = tasks.value.findIndex(t => t.id === editTaskForm.value.id)
        if (idx !== -1) {
          tasks.value[idx] = { ...tasks.value[idx], ...editTaskForm.value }
        }
        editDialogVisible.value = false
        ElMessage.success('任务更新成功')
      } catch (e) {
        ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
      }
    }
  })
}

// Delete Task
const deleteTask = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await axios.delete(`/api/staff/tasks/${id}`)
    const idx = tasks.value.findIndex(t => t.id === id)
    if (idx !== -1) {
      tasks.value.splice(idx, 1)
    }
    ElMessage.success('任务已删除')
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}
</script>

<style scoped>
.task-board {
  padding: 24px;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.filters {
  display: flex;
  gap: 12px;
}

.board-columns {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow-x: auto;
}

.board-column {
  display: flex;
  flex-direction: column;
  background: var(--bg-body);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  border-left-width: 4px;
  min-height: 400px;
  max-height: 100%;
  overflow: hidden;
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-card);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  flex-shrink: 0;
}

.column-count {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.column-body {
  padding: 12px;
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-card {
  background: var(--bg-card);
  border: none;
  border-radius: var(--radius-sm);
  padding: 12px;
  cursor: grab;
  transition: box-shadow var(--duration-fast) ease;
}

.task-card:hover {
  box-shadow: var(--shadow-card);
}

.task-card:active {
  cursor: grabbing;
}

.review-card {
  background: var(--accent-soft);
}

.task-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  word-break: break-word;
}

.review-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.review-badge {
  border: none !important;
}

.review-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.task-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.assignee-tag {
  border: none !important;
}

.assignee-tag :deep(.el-tag__content) {
  color: #fff;
}

.task-progress {
  margin-bottom: 8px;
}

.task-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.deadline {
  font-size: 11px;
  color: var(--text-tertiary);
}

.deadline.overdue {
  color: var(--rose-500);
  font-weight: 600;
}

.task-actions {
  display: flex;
  gap: 4px;
}

.task-actions .el-button {
  padding: 4px;
  height: auto;
}

/* Inline review actions */
.inline-review {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-color);
}

.review-textarea :deep(.el-textarea__inner) {
  font-size: 12px;
}

.inline-review-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  justify-content: flex-end;
}

/* Review dialog */
.review-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.review-task-info {
  padding: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.review-task-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.review-task-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.review-task-detail {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.review-comment-history {
  min-height: 60px;
}

.review-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.review-history-item {
  padding: 10px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.review-history-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.review-history-empty {
  font-size: 13px;
  color: var(--text-tertiary);
  padding: 12px;
  text-align: center;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.review-dialog-textarea :deep(.el-textarea__inner) {
  font-size: 13px;
}

/* Responsive */
@media (max-width: 1400px) {
  .board-columns {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 991px) {
  .board-columns {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .task-board {
    padding: 16px;
  }

  .board-columns {
    grid-template-columns: 1fr;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .filters {
    justify-content: flex-end;
  }
}
</style>
