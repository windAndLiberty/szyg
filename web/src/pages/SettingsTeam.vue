<template>
  <div class="settings-team-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-text">
        <h2 class="page-title">
          团队管理
          <el-tag size="small" type="warning" effect="light">Admin</el-tag>
        </h2>
        <p class="page-subtitle">团队成员与权限管理</p>
      </div>
      <div class="header-actions">
        <el-input
          v-model="searchQuery"
          placeholder="搜索成员..."
          prefix-icon="Search"
          class="search-input"
          clearable
        />
        <el-button type="primary" @click="inviteDialogVisible = true">
          <el-icon><Plus /></el-icon> 邀请成员
        </el-button>
      </div>
    </div>

    <!-- Members Table -->
    <el-card class="table-card" shadow="never">
      <el-table
        :data="filteredMembers"
        stripe
        style="width: 100%"
        :header-cell-style="{ background: 'var(--table-header-bg)' }"
        :row-class-name="() => 'team-row'"
      >
        <el-table-column label="头像" width="70" align="center">
          <template #default="{ row }">
            <div class="avatar-circle">{{ row.username.charAt(0).toUpperCase() }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="username" label="用户名" min-width="120" />

        <el-table-column prop="role" label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="email" label="邮箱" min-width="180" />

        <el-table-column prop="lastLogin" label="最后登录" width="160" />

        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'warning'" size="small">
              {{ row.status === 'active' ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="editMember(row)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button
              size="small"
              text
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" text type="danger" @click="deleteMember(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Invite Dialog -->
    <el-dialog
      v-model="inviteDialogVisible"
      title="邀请成员"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="inviteForm" label-width="80px" :rules="inviteRules" ref="inviteFormRef">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="inviteForm.username" placeholder="输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="inviteForm.email" placeholder="user@example.com" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="inviteForm.role" placeholder="选择角色" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inviteDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitInvite">发送邀请</el-button>
      </template>
    </el-dialog>

    <!-- Edit Dialog -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑成员"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role" placeholder="选择角色" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import axios from 'axios'

// ── API Data ──
const members = ref([])
const searchQuery = ref('')

async function loadMembers() {
  try {
    const { data } = await axios.get('/api/auth/users')
    const arr = Array.isArray(data) ? data : (data.data || [])
    members.value = arr.map(u => ({
      ...u,
      status: u.is_active ? 'active' : 'inactive',
    }))
  } catch (e) {
    ElMessage.error('加载成员失败: ' + (e.response?.data?.detail || e.message))
  }
}

onMounted(() => {
  loadMembers()
})

const filteredMembers = computed(() => {
  if (!searchQuery.value) return members.value
  const q = searchQuery.value.toLowerCase()
  return members.value.filter(
    m => m.username.toLowerCase().includes(q) || m.email.toLowerCase().includes(q)
  )
})

// ── Status Toggle ──
async function toggleStatus(member) {
  try {
    const { data } = await axios.put(`/api/auth/users/${member.id}/toggle`)
    member.is_active = data.is_active
    member.status = data.is_active ? 'active' : 'inactive'
    ElMessage.success(`${member.username} 已${member.status === 'active' ? '启用' : '禁用'}`)
  } catch (e) {
    ElMessage.error('操作失败: ' + (e.response?.data?.detail || e.message))
  }
}

// ── Delete ──
async function deleteMember(member) {
  try {
    await ElMessageBox.confirm(
      `确定要删除成员 ${member.username} 吗？此操作不可撤销。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await axios.delete(`/api/auth/users/${member.id}`)
    members.value = members.value.filter(m => m.id !== member.id)
    ElMessage.success(`${member.username} 已删除`)
  } catch (e) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
    }
  }
}

// ── Invite ──
const inviteDialogVisible = ref(false)
const inviteFormRef = ref(null)
const inviteForm = reactive({ username: '', email: '', role: 'user' })
const inviteRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

function submitInvite() {
  inviteFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      const { data } = await axios.post('/api/auth/users', null, {
        params: {
          username: inviteForm.username,
          password: 'changeme123',
          email: inviteForm.email,
          role: inviteForm.role,
        }
      })
      members.value.push({ ...data, status: data.is_active ? 'active' : 'inactive' })
      inviteDialogVisible.value = false
      ElMessage.success('邀请已发送')
      inviteForm.username = ''
      inviteForm.email = ''
      inviteForm.role = 'user'
    } catch (e) {
      ElMessage.error('邀请失败: ' + (e.response?.data?.detail || e.message))
    }
  })
}

// ── Edit ──
const editDialogVisible = ref(false)
const editForm = reactive({ id: null, username: '', email: '', role: '' })

function editMember(member) {
  Object.assign(editForm, { ...member })
  editDialogVisible.value = true
}

async function submitEdit() {
  try {
    await axios.put(`/api/auth/users/${editForm.id}`, null, {
      params: {
        email: editForm.email,
        role: editForm.role,
      }
    })
    const idx = members.value.findIndex(m => m.id === editForm.id)
    if (idx !== -1) {
      members.value[idx] = { ...members.value[idx], ...editForm }
    }
    editDialogVisible.value = false
    ElMessage.success('成员信息已更新')
  } catch (e) {
    ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message))
  }
}
</script>

<style scoped>
.settings-team-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.page-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-input {
  width: 240px;
}

.table-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}
.table-card :deep(.el-card__body) {
  padding: 0;
}

.avatar-circle {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--accent-gradient);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  margin: 0 auto;
}

:deep(.team-row:hover td) {
  background: var(--hover-bg) !important;
}

:deep(.el-table__header th) {
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 13px;
}

:deep(.el-table__row td) {
  color: var(--text-primary);
  font-size: 13px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid var(--border-color);
  padding: 16px 20px;
  margin-right: 0;
}
:deep(.el-dialog__footer) {
  border-top: 1px solid var(--border-color);
  padding: 12px 20px;
}

:deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-weight: 500;
}
:deep(.el-input__wrapper) {
  background: var(--input-bg) !important;
  box-shadow: 0 0 0 1px var(--input-border) inset;
}
:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--input-border-hover) inset;
}
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--input-focus) inset !important;
}

/* Responsive */
@media (max-width: 768px) {
  .header-actions { flex-direction: column; align-items: stretch; }
  .search-input { width: 100%; }
}
</style>
