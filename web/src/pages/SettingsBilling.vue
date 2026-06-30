<template>
  <div class="page-placeholder">
    <h2 class="page-title">计费管理</h2>
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="算力套餐" name="plans"><el-empty description="套餐配置与权益管理" /></el-tab-pane>
      <el-tab-pane label="充值记录" name="recharge"><el-empty description="充值历史记录" /></el-tab-pane>
      <el-tab-pane label="消耗统计" name="consumption"><el-empty description="算力消耗统计" /></el-tab-pane>
      <el-tab-pane label="会员管理" name="members"><el-empty description="会员等级与续费管理" /></el-tab-pane>
    </el-tabs>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const activeTab = ref('plans')
</script>
<style scoped>
.page-placeholder { padding: 24px; }
.page-title { margin: 0 0 16px; font-size: 18px; }
</style>
