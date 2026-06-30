<template>
  <div class="page-placeholder">
    <h2 class="page-title">到店引流</h2>
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="店铺配置" name="shop">
        <el-empty description="店铺名称/简介/宣传语/产品关键词配置" />
      </el-tab-pane>
      <el-tab-pane label="NFC卡片" name="nfc">
        <el-empty description="NFC卡片ID管理与链接生成" />
      </el-tab-pane>
      <el-tab-pane label="团购挂载" name="group">
        <el-empty description="抖音/美团团购链接配置" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const activeTab = ref('shop')
</script>
<style scoped>
.page-placeholder { padding: 24px; }
.page-title { margin: 0 0 16px; font-size: 18px; }
</style>
