<template>
    <el-card>
      <template #header><h3>系统管理</h3></template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="用户管理" name="users">
          <el-table :data="users" border stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ row.role }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="oem_id" label="OEM ID" />
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-divider />
          <el-form :model="newUser" inline>
            <el-form-item label="用户名"><el-input v-model="newUser.username" /></el-form-item>
            <el-form-item label="密码"><el-input v-model="newUser.password" type="password" show-password /></el-form-item>
            <el-form-item label="角色">
              <el-select v-model="newUser.role"><el-option label="user" value="user" /><el-option label="admin" value="admin" /></el-select>
            </el-form-item>
            <el-form-item><el-button type="primary" @click="addUser">添加用户</el-button></el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="系统配置" name="config">
          <pre>{{ configJson }}</pre>
        </el-tab-pane>
      </el-tabs>
    </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const activeTab = ref('users')
const users = ref([])
const configJson = ref('')
const newUser = reactive({ username: '', password: '', role: 'user' })

onMounted(async () => {
  try {
    const token = localStorage.getItem('token')
    const [uRes, cRes] = await Promise.all([
      axios.get('/api/auth/users', { headers: { Authorization: `Bearer ${token}` } }),
      axios.get('/api/config'),
    ])
    users.value = uRes.data
    configJson.value = JSON.stringify(cRes.data, null, 2)
  } catch (_) {}
})

async function addUser() {
  if (!newUser.username || !newUser.password) return ElMessage.warning('填写完整')
  try {
    const token = localStorage.getItem('token')
    await axios.post('/api/auth/users', null, {
      params: newUser,
      headers: { Authorization: `Bearer ${token}` },
    })
    ElMessage.success('用户已创建')
    newUser.username = ''; newUser.password = ''
    const { data } = await axios.get('/api/auth/users', { headers: { Authorization: `Bearer ${token}` } })
    users.value = data
  } catch (e) { ElMessage.error(e.response?.data?.detail || '创建失败') }
}
</script>
