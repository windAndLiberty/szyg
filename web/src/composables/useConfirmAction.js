/**
 * useConfirmAction — 确认 + 执行 + 错误处理 组合函数
 *
 * 消除各页面重复的:
 *   await ElMessageBox.confirm(...)
 *   await axios.delete(...)
 *   ElMessage.success(...)
 *   catch (e) { if (e !== 'cancel' ...) ElMessage.error(...) }
 *
 * 用法:
 *   const { run: doDelete } = useConfirmAction({
 *     confirm: (row) => `确定要删除 ${row.name} 吗？`,
 *     action: (row) => axios.delete(`/api/items/${row.id}`),
 *     onSuccess: (row) => { items.value = items.value.filter(i => i.id !== row.id) },
 *     successMsg: (row) => `${row.name} 已删除`,
 *     errorPrefix: '删除',
 *   })
 */

import { ElMessage, ElMessageBox } from 'element-plus'
import { getErrorMessage } from '@/api'

export function useConfirmAction(options = {}) {
  const {
    confirm = null,
    confirmTitle = '操作确认',
    confirmButton = '确认',
    cancelButton = '取消',
    action,
    onSuccess = null,
    successMsg = null,
    errorPrefix = '操作',
  } = options

  async function run(item) {
    try {
      if (confirm) {
        const msg = typeof confirm === 'function' ? confirm(item) : confirm
        await ElMessageBox.confirm(msg, confirmTitle, {
          confirmButtonText: confirmButton,
          cancelButtonText: cancelButton,
          type: 'warning',
        })
      }
      const result = await action(item)
      if (onSuccess) onSuccess(item, result)
      if (successMsg) {
        const msg = typeof successMsg === 'function' ? successMsg(item) : successMsg
        ElMessage.success(msg)
      }
      return result
    } catch (e) {
      if (e !== 'cancel' && e?.message !== 'cancel') {
        ElMessage.error(`${errorPrefix}失败: ${getErrorMessage(e)}`)
      }
    }
  }

  return { run }
}
