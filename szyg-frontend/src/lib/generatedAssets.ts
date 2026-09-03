export function resolveGeneratedAssetUrl(url: string, path = ''): string {
  const candidate = (url || '').trim()
  if (candidate.startsWith('http://') || candidate.startsWith('https://') || candidate.startsWith('/')) {
    return candidate
  }

  const localPath = (path || candidate).replace(/\\/g, '/')
  const fileName = localPath.split('/').filter(Boolean).pop()
  if (!fileName) return candidate

  if (localPath.includes('/server/data/volcengine_output/')) {
    return `/api/files/server_volcengine_output/${encodeURIComponent(fileName)}`
  }
  if (localPath.includes('/volcengine_output/')) {
    return `/api/files/volcengine_output/${encodeURIComponent(fileName)}`
  }
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  if (['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(ext)) {
    return `/api/media/files/image/${encodeURIComponent(fileName)}`
  }
  if (['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext)) {
    return `/api/media/files/video/${encodeURIComponent(fileName)}`
  }
  if (['mp3', 'wav', 'm4a', 'aac', 'flac'].includes(ext)) {
    return `/api/media/files/audio/${encodeURIComponent(fileName)}`
  }
  if (['md', 'txt'].includes(ext)) {
    return `/api/media/files/document/${encodeURIComponent(fileName)}`
  }
  return candidate
}

export async function downloadGeneratedAsset(asset: { url: string; path?: string }, filename?: string): Promise<void> {
  const displayUrl = resolveGeneratedAssetUrl(asset.url, asset.path || '')
  const fallbackName = (asset.path || displayUrl).split(/[\\/]/).filter(Boolean).pop() || `generated-${Date.now()}.jpg`

  try {
    const response = await fetch(displayUrl)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filename || fallbackName
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
  } catch (error) {
    const path = asset.path || displayUrl
    try {
      await navigator.clipboard.writeText(path)
      window.alert(`下载未完成，已复制文件路径：\n${path}`)
    } catch {
      window.alert(`下载未完成，请手动打开文件：\n${path}`)
    }
    throw error
  }
}
