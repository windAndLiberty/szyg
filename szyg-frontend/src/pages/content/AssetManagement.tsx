import { useState, useCallback, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Image as AssetManagementIcon,
  Search,
  Upload,
  Trash2,
  Download,
  X,
  Grid3X3,
  List,
  FileImage,
  FileVideo,
  FileAudio,
  FileText,
  Loader2,
  FolderOpen,
} from 'lucide-react'

type AssetType = 'all' | 'image' | 'video' | 'audio' | 'text'

interface Asset {
  id: string
  name: string
  type: 'image' | 'video' | 'audio' | 'text'
  url: string
  size: number
  created_at: string
}

const ASSET_TYPE_FILTERS: { key: AssetType; label: string; icon: typeof FileImage }[] = [
  { key: 'all', label: '全部', icon: Grid3X3 },
  { key: 'image', label: '图片', icon: FileImage },
  { key: 'video', label: '视频', icon: FileVideo },
  { key: 'audio', label: '音频', icon: FileAudio },
  { key: 'text', label: '文案', icon: FileText },
]

const TYPE_ICONS: Record<string, typeof FileImage> = {
  image: FileImage,
  video: FileVideo,
  audio: FileAudio,
  text: FileText,
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function AssetManagement() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [filter, setFilter] = useState<AssetType>('all')
  const [search, setSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [previewAsset, setPreviewAsset] = useState<Asset | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load assets
  useEffect(() => {
    loadAssets()
  }, [])

  const loadAssets = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/materials')
      if (res.ok) {
        const data = await res.json()
        setAssets(data.items || [])
      }
    } catch {
      // Use mock data for demo
      setAssets([
        { id: '1', name: '产品图-001.png', type: 'image', url: '/api/files/sample.png', size: 2048000, created_at: '2026-07-06T10:00:00Z' },
        { id: '2', name: '宣传视频.mp4', type: 'video', url: '/api/files/sample.mp4', size: 15728640, created_at: '2026-07-06T09:30:00Z' },
        { id: '3', name: '配音素材.wav', type: 'audio', url: '/api/files/sample.wav', size: 524288, created_at: '2026-07-06T09:00:00Z' },
        { id: '4', name: '朋友圈文案.txt', type: 'text', url: '', size: 1024, created_at: '2026-07-05T15:00:00Z' },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setError(null)

    try {
      for (const file of Array.from(files)) {
        const formData = new FormData()
        formData.append('file', file)
        const res = await fetch('/api/materials/upload', {
          method: 'POST',
          body: formData,
        })
        if (!res.ok) throw new Error(`上传失败: ${file.name}`)
      }
      await loadAssets()
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }, [])

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm('确定删除此素材？')) return
    try {
      await fetch(`/api/materials/${id}`, { method: 'DELETE' })
      setAssets((prev) => prev.filter((a) => a.id !== id))
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } catch {
      setError('删除失败')
    }
  }, [])

  const handleBulkDelete = useCallback(async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`确定删除 ${selectedIds.size} 个素材？`)) return
    try {
      for (const id of selectedIds) {
        await fetch(`/api/materials/${id}`, { method: 'DELETE' })
      }
      setAssets((prev) => prev.filter((a) => !selectedIds.has(a.id)))
      setSelectedIds(new Set())
    } catch {
      setError('批量删除失败')
    }
  }, [selectedIds])

  const handleDownload = useCallback((asset: Asset) => {
    if (!asset.url) return
    const a = document.createElement('a')
    a.href = asset.url
    a.download = asset.name
    a.click()
  }, [])

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const filteredAssets = assets.filter((a) => {
    if (filter !== 'all' && a.type !== filter) return false
    if (search && !a.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="flex flex-col h-full"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#1E293B]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#6366F1] to-[#8B5CF6] flex items-center justify-center">
            <AssetManagementIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-display-sm text-[#F1F5F9]">素材管理</h1>
            <p className="text-body-sm text-[#64748B]">管理所有上传和AI生成的素材</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 && (
            <button
              onClick={handleBulkDelete}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#EF4444]/20 text-[#EF4444] hover:bg-[#EF4444]/30 text-body-sm transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              删除 ({selectedIds.size})
            </button>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 bg-[#6366F1] hover:bg-[#5558E6] disabled:opacity-50 rounded-lg text-body-sm text-white transition-colors"
          >
            {uploading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            上传
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,video/*,audio/*,.txt,.md"
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
          />
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-4 px-6 py-3 border-b border-[#1E293B]">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#64748B]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索素材..."
            className="w-full pl-9 pr-4 py-2 bg-[#0B0F1A] border border-[#1E293B] rounded-lg text-body-sm text-[#F1F5F9] placeholder:text-[#475569] focus:outline-none focus:border-[#6366F1]"
          />
        </div>

        {/* Type Filter */}
        <div className="flex gap-1">
          {ASSET_TYPE_FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-body-xs transition-all ${
                filter === f.key
                  ? 'bg-[#6366F1]/20 text-[#6366F1] border border-[#6366F1]/30'
                  : 'text-[#94A3B8] hover:bg-[#1E293B]'
              }`}
            >
              <f.icon className="w-3.5 h-3.5" />
              {f.label}
            </button>
          ))}
        </div>

        {/* View Mode */}
        <div className="flex gap-1 border-l border-[#1E293B] pl-4">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-1.5 rounded-md transition-colors ${
              viewMode === 'grid' ? 'bg-[#1E293B] text-[#F1F5F9]' : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-1.5 rounded-md transition-colors ${
              viewMode === 'list' ? 'bg-[#1E293B] text-[#F1F5F9]' : 'text-[#64748B] hover:text-[#94A3B8]'
            }`}
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {/* Error */}
        {error && (
          <div className="mb-4 glass-card rounded-card-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-4 text-[#EF4444] text-body-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-[#EF4444] hover:text-[#DC2626]">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Loading */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 text-[#6366F1] animate-spin" />
          </div>
        ) : filteredAssets.length === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <FolderOpen className="w-16 h-16 text-[#334155] mb-4" />
            <p className="text-body-lg text-[#94A3B8] mb-2">暂无素材</p>
            <p className="text-body-sm text-[#64748B] mb-4">点击上传按钮添加素材</p>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2 bg-[#6366F1] hover:bg-[#5558E6] rounded-lg text-body-sm text-white transition-colors"
            >
              <Upload className="w-4 h-4" />
              上传素材
            </button>
          </div>
        ) : viewMode === 'grid' ? (
          /* Grid View */
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {filteredAssets.map((asset) => {
              const Icon = TYPE_ICONS[asset.type] || FileImage
              return (
                <div
                  key={asset.id}
                  className={`glass-card rounded-card-lg border overflow-hidden cursor-pointer transition-all hover:border-[#6366F1]/50 ${
                    selectedIds.has(asset.id) ? 'border-[#6366F1] ring-1 ring-[#6366F1]/30' : 'border-[#1E293B]'
                  }`}
                  onClick={() => setPreviewAsset(asset)}
                >
                  {/* Thumbnail */}
                  <div className="aspect-square bg-[#0B0F1A] flex items-center justify-center relative">
                    {asset.type === 'image' && asset.url ? (
                      <img src={asset.url} alt={asset.name} className="w-full h-full object-cover" />
                    ) : (
                      <Icon className="w-12 h-12 text-[#334155]" />
                    )}
                    {/* Select checkbox */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleSelect(asset.id)
                      }}
                      className={`absolute top-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        selectedIds.has(asset.id)
                          ? 'bg-[#6366F1] border-[#6366F1]'
                          : 'border-[#475569] bg-[#0B0F1A]/80'
                      }`}
                    >
                      {selectedIds.has(asset.id) && (
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>
                  </div>

                  {/* Info */}
                  <div className="p-3">
                    <p className="text-body-sm text-[#F1F5F9] truncate">{asset.name}</p>
                    <p className="text-body-xs text-[#64748B] mt-1">{formatFileSize(asset.size)}</p>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          /* List View */
          <div className="space-y-2">
            {filteredAssets.map((asset) => {
              const Icon = TYPE_ICONS[asset.type] || FileImage
              return (
                <div
                  key={asset.id}
                  className={`glass-card rounded-card-lg border flex items-center gap-4 px-4 py-3 cursor-pointer transition-all hover:border-[#6366F1]/50 ${
                    selectedIds.has(asset.id) ? 'border-[#6366F1]' : 'border-[#1E293B]'
                  }`}
                  onClick={() => setPreviewAsset(asset)}
                >
                  {/* Select */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleSelect(asset.id)
                    }}
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                      selectedIds.has(asset.id)
                        ? 'bg-[#6366F1] border-[#6366F1]'
                        : 'border-[#475569]'
                    }`}
                  >
                    {selectedIds.has(asset.id) && (
                      <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>

                  {/* Icon */}
                  <div className="w-10 h-10 rounded-lg bg-[#1E293B] flex items-center justify-center">
                    <Icon className="w-5 h-5 text-[#64748B]" />
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-body-sm text-[#F1F5F9] truncate">{asset.name}</p>
                    <p className="text-body-xs text-[#64748B]">{formatFileSize(asset.size)}</p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDownload(asset)
                      }}
                      className="p-2 rounded-lg hover:bg-[#1E293B] text-[#64748B] hover:text-[#F1F5F9] transition-colors"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(asset.id)
                      }}
                      className="p-2 rounded-lg hover:bg-[#EF4444]/20 text-[#64748B] hover:text-[#EF4444] transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Preview Modal */}
      {previewAsset && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPreviewAsset(null)}
        >
          <div
            className="glass-card rounded-card-xl border border-[#1E293B] max-w-4xl max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#1E293B]">
              <div className="flex items-center gap-3">
                {(() => {
                  const Icon = TYPE_ICONS[previewAsset.type] || FileImage
                  return <Icon className="w-5 h-5 text-[#6366F1]" />
                })()}
                <div>
                  <p className="text-body-md text-[#F1F5F9] font-medium">{previewAsset.name}</p>
                  <p className="text-body-xs text-[#64748B]">
                    {formatFileSize(previewAsset.size)} · {new Date(previewAsset.created_at).toLocaleDateString('zh-CN')}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setPreviewAsset(null)}
                className="p-2 rounded-lg hover:bg-[#1E293B] text-[#64748B] hover:text-[#F1F5F9] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6">
              {previewAsset.type === 'image' && previewAsset.url && (
                <img src={previewAsset.url} alt={previewAsset.name} className="max-w-full max-h-[60vh] mx-auto rounded-lg" />
              )}
              {previewAsset.type === 'video' && previewAsset.url && (
                <video src={previewAsset.url} controls className="max-w-full max-h-[60vh] mx-auto rounded-lg" />
              )}
              {previewAsset.type === 'audio' && previewAsset.url && (
                <audio src={previewAsset.url} controls className="w-full" />
              )}
              {previewAsset.type === 'text' && (
                <div className="bg-[#0B0F1A] rounded-lg p-4 min-h-[200px]">
                  <p className="text-body-md text-[#F1F5F9] whitespace-pre-wrap">文案内容加载中...</p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-[#1E293B]">
              <button
                onClick={() => handleDownload(previewAsset)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#1E293B] hover:bg-[#334155] text-[#F1F5F9] text-body-sm transition-colors"
              >
                <Download className="w-4 h-4" />
                下载
              </button>
              <button
                onClick={() => {
                  handleDelete(previewAsset.id)
                  setPreviewAsset(null)
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#EF4444]/20 hover:bg-[#EF4444]/30 text-[#EF4444] text-body-sm transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  )
}
