<template>
  <div class="page-placeholder">
    <h2 class="page-title">商学院</h2>
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="行业分析" name="industry"><el-empty description="行业分析文章管理" /></el-tab-pane>
      <el-tab-pane label="营销技巧" name="marketing"><el-empty description="营销技巧文章管理" /></el-tab-pane>
      <el-tab-pane label="引流策略" name="strategy"><el-empty description="引流策略文章管理" /></el-tab-pane>
      <el-tab-pane label="一键解答" name="faq"><el-empty description="常见问题FAQ管理" /></el-tab-pane>
    </el-tabs>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const activeTab = ref('industry')
</script>
<style scoped>
.page-placeholder { padding: 24px; }
.page-title { margin: 0 0 16px; font-size: 18px; }
</style>
