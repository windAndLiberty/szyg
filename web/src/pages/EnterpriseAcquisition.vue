<template>
  <div class="page-placeholder">
    <h2 class="page-title">企业获客</h2>
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="企业查询" name="enterprise">
        <el-empty description="基于企查查/天眼查的企业信息查询获客" />
      </el-tab-pane>
      <el-tab-pane label="LBS获客" name="lbs">
        <el-empty description="基于高德地图API的地理位置获客" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const activeTab = ref('enterprise')
</script>
<style scoped>
.page-placeholder { padding: 24px; }
.page-title { margin: 0 0 16px; font-size: 18px; }
</style>
