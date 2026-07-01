/**
 * useDataLoader — 通用数据加载组合函数
 *
 * 消除各页面重复的:
 *   const items = ref([])
 *   async function loadItems() { try { ... } catch { ElMessage.error(...) } }
 *   onMounted(() => loadItems())
 *
 * 用法:
 *   const { data, loading, reload } = useDataLoader('/api/team', {
 *     transform: raw => raw.data || [],
 *     errorPrefix: '加载团队',
 *     immediate: true,
 *   })
 */

import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { getErrorMessage } from '@/api'

export function useDataLoader(url, options = {}) {
  const {
    transform = raw => (Array.isArray(raw) ? raw : raw.data || []),
    errorPrefix = '加载数据',
    immediate = true,
    defaultValue = [],
    params = {},
  } = options

  const data = ref(defaultValue)
  const loading = ref(false)

  async function reload(extraParams = {}) {
    loading.value = true
    try {
      const { data: raw } = await axios.get(url, { params: { ...params, ...extraParams } })
      data.value = transform(raw)
    } catch (e) {
      ElMessage.error(`${errorPrefix}失败: ${getErrorMessage(e)}`)
    } finally {
      loading.value = false
    }
  }

  if (immediate) {
    onMounted(() => reload())
  }

  return { data, loading, reload }
}
