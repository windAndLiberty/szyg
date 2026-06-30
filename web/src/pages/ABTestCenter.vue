<template>
  <div class="page-container">
    <h2 class="page-title">A/B测试</h2>
    <el-tabs v-model="activeTab" type="border-card" class="studio-tabs">
      <el-tab-pane label="进行中" name="active">
        <div class="tab-content">
          <el-button type="primary" size="small" @click="showCreate = true" style="margin-bottom: 16px">新建测试</el-button>
          <el-table :data="activeTests" stripe>
            <el-table-column prop="name" label="测试名称" min-width="160" />
            <el-table-column prop="strategyA" label="策略A" min-width="120" />
            <el-table-column prop="strategyB" label="策略B" min-width="120" />
            <el-table-column prop="sentA" label="A发送量" width="90" />
            <el-table-column prop="repliedA" label="A回复量" width="90" />
            <el-table-column prop="sentB" label="B发送量" width="90" />
            <el-table-column prop="repliedB" label="B回复量" width="90" />
            <el-table-column label="回复率对比" width="140">
              <template #default="{ row }">
                <span>{{ row.sentA ? ((row.repliedA / row.sentA) * 100).toFixed(1) : 0 }}% vs {{ row.sentB ? ((row.repliedB / row.sentB) * 100).toFixed(1) : 0 }}%</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="endTest(row)">结束测试</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!activeTests.length" description="暂无进行中的测试" />
        </div>
      </el-tab-pane>
      <el-tab-pane label="已完成" name="completed">
        <el-table :data="completedTests" stripe>
          <el-table-column prop="name" label="测试名称" min-width="160" />
          <el-table-column prop="winner" label="胜出策略" width="100">
            <template #default="{ row }">
              <el-tag type="success" size="small">{{ row.winner }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="improvement" label="提升幅度" width="100">
            <template #default="{ row }">
              <span :class="{ positive: row.improvement > 0 }">{{ row.improvement > 0 ? '+' : '' }}{{ row.improvement }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="completedAt" label="完成时间" width="160" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button size="small" plain @click="viewResult(row)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!completedTests.length" description="暂无已完成的测试" />
      </el-tab-pane>
    </el-tabs>
    <el-dialog v-model="showCreate" title="新建A/B测试" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="策略A"><el-input v-model="createForm.strategyA" type="textarea" :rows="3" placeholder="策略A评论模板" /></el-form-item>
        <el-form-item label="策略B"><el-input v-model="createForm.strategyB" type="textarea" :rows="3" placeholder="策略B评论模板" /></el-form-item>
        <el-form-item label="分配比例"><el-slider v-model="createForm.ratio" :min="10" :max="90" :step="10" show-input /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showCreate = false">取消</el-button><el-button type="primary" @click="createTest">创建</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const activeTab = ref('active')
const showCreate = ref(false)
const createForm = ref({ name: '', strategyA: '', strategyB: '', ratio: 50 })
const activeTests = ref([])
const completedTests = ref([])

async function loadTests() {
  try {
    const { data } = await axios.get('/api/acquisition/ab-test')
    const tests = data?.tests || data || []
    activeTests.value = (Array.isArray(tests) ? tests : []).filter(t => t.status === 'running')
    completedTests.value = (Array.isArray(tests) ? tests : []).filter(t => t.status !== 'running')
  } catch {
    activeTests.value = []
    completedTests.value = []
  }
}

onMounted(() => { loadTests() })

async function createTest() {
  if (!createForm.value.name) { ElMessage.warning('请输入测试名称'); return }
  try {
    await axios.post('/api/acquisition/ab-test/start', {
      name: createForm.value.name,
      strategy_a: createForm.value.strategyA,
      strategy_b: createForm.value.strategyB,
      ratio: createForm.value.ratio,
    })
    showCreate.value = false
    createForm.value = { name: '', strategyA: '', strategyB: '', ratio: 50 }
    ElMessage.success('测试已创建')
    loadTests()
  } catch (e) {
    ElMessage.error('创建失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function endTest(row) {
  try {
    await axios.post(`/api/acquisition/ab-test/${row.id}/stop`)
    ElMessage.success('测试已停止')
    loadTests()
  } catch (e) {
    ElMessage.error('停止失败: ' + (e.response?.data?.detail || e.message))
  }
}

function viewResult(row) {
  ElMessage.info(`查看测试「${row.name}」详情`)
}
</script>

<style scoped>
.page-container { padding: 24px; }
.page-title { margin: 0 0 20px; font-size: 18px; }
.studio-tabs { border-radius: 8px; }
.tab-content { padding: 16px 0; }
.positive { color: #22c55e; font-weight: 600; }
</style>
