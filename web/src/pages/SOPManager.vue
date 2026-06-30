<template>
  <div class="page-placeholder">
    <h2 class="page-title">SOP管理</h2>
    <div class="sop-layout">
      <div class="sop-list">
        <el-button type="primary" size="small" @click="showAdd = true" style="margin-bottom: 12px">新建SOP</el-button>
        <el-empty :image-size="60" description="暂无SOP模板" />
      </div>
      <div class="sop-editor">
        <el-empty description="选择SOP查看步骤详情" />
      </div>
    </div>
    <el-dialog v-model="showAdd" title="新建SOP" width="500px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="newSop.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="newSop.desc" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showAdd = false">取消</el-button><el-button type="primary" @click="showAdd = false">创建</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const showAdd = ref(false)
const newSop = ref({ name: '', desc: '' })
</script>
<style scoped>
.page-placeholder { padding: 24px; }
.page-title { margin: 0 0 16px; font-size: 18px; }
.sop-layout { display: flex; gap: 16px; }
.sop-list { width: 300px; }
.sop-editor { flex: 1; }
</style>
