/** 纯展示型辅助函数（非模拟数据） — 状态/类型标签与颜色映射。 */

export const getStatusColor = (status: string): string => {
  switch (status) {
    case 'active':
      return '#10B981'
    case 'training':
      return '#F59E0B'
    case 'idle':
      return '#64748B'
    case 'error':
      return '#EF4444'
    default:
      return '#64748B'
  }
}

export const getStatusLabel = (status: string): string => {
  switch (status) {
    case 'active':
      return '运行中'
    case 'training':
      return '训练中'
    case 'idle':
      return '待机'
    case 'error':
      return '异常'
    default:
      return status
  }
}

export const getTypeLabel = (type: string): string => {
  switch (type) {
    case 'sales':
      return '销售'
    case 'customer_service':
      return '客服'
    case 'marketing':
      return '营销'
    case 'data_analyst':
      return '数据分析'
    case 'custom':
      return '定制'
    default:
      return type
  }
}

export const getTypeIcon = (type: string): string => {
  switch (type) {
    case 'sales':
      return 'TrendingUp'
    case 'customer_service':
      return 'Headphones'
    case 'marketing':
      return 'Megaphone'
    case 'data_analyst':
      return 'BarChart3'
    case 'custom':
      return 'Settings'
    default:
      return 'Bot'
  }
}

/** 相对时间格式化（基于真实当前时间）。 */
export function getRelativeTime(timestamp: string): string {
  if (!timestamp) return ''
  const now = Date.now()
  const time = new Date(timestamp).getTime()
  if (Number.isNaN(time)) return ''
  const diff = now - time
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(hours / 24)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 7) return `${days} 天前`
  return new Date(timestamp).toLocaleDateString('zh-CN')
}

/** 数字格式化（万/k）。 */
export function formatNumber(num: number): string {
  if (num >= 10000) return `${(num / 10000).toFixed(1)}w`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
  return num.toString()
}
