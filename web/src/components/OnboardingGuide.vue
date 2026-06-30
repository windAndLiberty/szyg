<template>
  <teleport to="body">
    <div class="onboarding-overlay" @click.self="skipGuide">
      <!-- Guide Card -->
      <div class="onboarding-card">
        <div class="onboarding-header">
          <h3 class="onboarding-title">欢迎使用 szyg</h3>
          <button class="onboarding-skip" @click="skipGuide">跳过</button>
        </div>

        <div class="onboarding-body">
          <!-- Step indicator -->
          <div class="step-dots">
            <span
              v-for="n in 3"
              :key="n"
              class="step-dot"
              :class="{ active: currentStep === n }"
            />
          </div>

          <!-- Step content -->
          <div class="step-content">
            <div class="step-number">步骤 {{ currentStep }} / 3</div>
            <h4 class="step-title">{{ currentStepData.title }}</h4>
            <p class="step-description">{{ currentStepData.description }}</p>
            <div class="step-hint">{{ currentStepData.hint }}</div>
          </div>
        </div>

        <div class="onboarding-footer">
          <el-button v-if="currentStep > 1" @click="prevStep">上一步</el-button>
          <el-button v-if="currentStep < 3" type="primary" @click="nextStep">下一步</el-button>
          <el-button v-else type="success" @click="completeGuide">完成引导</el-button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['complete'])
const router = useRouter()

const currentStep = ref(1)

const steps = [
  {
    title: '绑定平台账号',
    description: '第一步：绑定你的平台账号，让 AI 员工能够操作真实平台',
    hint: '👆 点击顶部导航的【系统设置】，进入平台账号页面进行绑定',
  },
  {
    title: '使用超级员工完成第一个任务',
    description: '第二步：点击超级员工按钮，输入你的第一个任务指令',
    hint: '👆 点击右下角的超级员工按钮（闪电图标），在面板中输入任务',
  },
  {
    title: '查看仪表盘结果',
    description: '第三步：在仪表盘查看任务执行结果和今日数据',
    hint: '👆 点击顶部导航的【仪表盘】，查看任务执行结果和数据统计',
  },
]

const currentStepData = computed(() => steps[currentStep.value - 1])

const nextStep = () => {
  if (currentStep.value < 3) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

const skipGuide = () => {
  localStorage.setItem('szyg_onboarding_completed', 'true')
  emit('complete')
}

const completeGuide = () => {
  localStorage.setItem('szyg_onboarding_completed', 'true')
  ElMessage?.success('引导完成！开始使用 szyg') || console.log('引导完成')
  emit('complete')
}
</script>

<style scoped>
.onboarding-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.3s ease;
}

.onboarding-card {
  width: 480px;
  max-width: 90vw;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, #d4e4cc);
  border-radius: var(--radius-lg, 16px);
  box-shadow: var(--shadow-xl, 0 24px 64px rgba(0, 0, 0, 0.1));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.4s var(--ease-out-expo, cubic-bezier(0.16, 1, 0.3, 1));
}

.onboarding-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 0;
}

.onboarding-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #1a2e1a);
}

.onboarding-skip {
  background: none;
  border: none;
  font-size: 13px;
  color: var(--text-tertiary, #6b8a5e);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm, 6px);
  transition: all 0.2s ease;
}

.onboarding-skip:hover {
  color: var(--accent-primary, #166534);
  background: var(--hover-bg, #eef5ea);
}

.onboarding-body {
  padding: 16px 24px 24px;
  flex: 1;
}

.step-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 20px;
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--border-color, #d4e4cc);
  transition: all 0.3s ease;
}

.step-dot.active {
  background: var(--accent-primary, #166534);
  box-shadow: 0 0 8px var(--accent-primary, #166534);
  transform: scale(1.2);
}

.step-content {
  text-align: center;
}

.step-number {
  font-size: 12px;
  color: var(--text-tertiary, #6b8a5e);
  margin-bottom: 8px;
  font-weight: 500;
}

.step-title {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #1a2e1a);
}

.step-description {
  margin: 0 0 16px;
  font-size: 14px;
  color: var(--text-secondary, #4a6741);
  line-height: 1.6;
}

.step-hint {
  font-size: 13px;
  color: var(--text-muted, #8fa883);
  padding: 12px 16px;
  background: var(--hover-bg, #eef5ea);
  border-radius: var(--radius-md, 10px);
  line-height: 1.5;
  text-align: left;
}

.onboarding-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 24px 20px;
  border-top: 1px solid var(--border-color, #d4e4cc);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Dark mode adjustments */
html.dark .onboarding-card {
  background: var(--card-bg, #2a2a2a);
  border-color: var(--border-color, #333333);
}

html.dark .onboarding-title {
  color: var(--text-primary, #e8e8e8);
}

html.dark .step-title {
  color: var(--text-primary, #e8e8e8);
}

html.dark .step-description {
  color: var(--text-secondary, #a0a0a0);
}

html.dark .step-hint {
  background: var(--bg-hover, rgba(255, 255, 255, 0.05));
  color: var(--text-muted, #505050);
}

html.dark .step-dot {
  background: var(--border-color, #333333);
}

html.dark .step-dot.active {
  background: var(--accent, #818cf8);
}

html.dark .onboarding-skip:hover {
  color: var(--accent, #818cf8);
  background: var(--bg-hover, rgba(255, 255, 255, 0.05));
}
</style>
