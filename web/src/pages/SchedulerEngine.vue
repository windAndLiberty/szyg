<template>
  <div class="page-placeholder">
    <h2 class="page-title">调度引擎</h2>
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="任务列表" name="jobs">
        <el-table :data="jobs" stripe>
          <el-table-column prop="name" label="任务名称" min-width="160" />
          <el-table-column prop="trigger" label="触发类型" width="100" />
          <el-table-column prop="nextRun" label="下次执行" width="160" />
          <el-table-column prop="status" label="状态" width="80" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="执行历史" name="history">
        <el-empty description="执行历史时间线" />
      </el-tab-pane>
      <el-tab-pane label="统计" name="stats">
        <el-empty description="调度统计面板" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const activeTab = ref('jobs')
const jobs = ref([])
</script>
<style scoped>
.page-placeholder { padding: 24px; }
.page-title { margin: 0 0 16px; font-size: 18px; }
</style>
