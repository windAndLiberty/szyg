import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AlertCircle,
  Archive,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Database,
  FileAudio,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileVideo,
  FolderOpen,
  HardDrive,
  Layers3,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import {
  deleteKnowledgeDocument,
  getKnowledgeCollections,
  getKnowledgeDocument,
  getKnowledgeStats,
  knowledgeSourceUrl,
  listKnowledgeDocuments,
  reparseKnowledgeDocument,
  testKnowledgeRetrieval,
  uploadKnowledgeDocument,
  type KnowledgeDocument,
  type KnowledgeResult,
  type KnowledgeStats,
} from './knowledgeApi'

const inputClass = 'w-full rounded-md border border-[#273449] bg-[#0B0F1A] px-3 py-2.5 text-sm text-[#E2E8F0] outline-none transition focus:border-[#6366F1] focus:ring-2 focus:ring-[#6366F1]/15'
const primaryButton = 'inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-[#6366F1] px-4 text-sm font-medium text-white transition hover:bg-[#5558E8] disabled:cursor-not-allowed disabled:opacity-45'
const secondaryButton = 'inline-flex h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-[#273449] bg-[#111827] px-3 text-sm text-[#CBD5E1] transition hover:border-[#3B4A63] hover:bg-[#172033] disabled:cursor-not-allowed disabled:opacity-45'

const processingStates = new Set(['queued', 'parsing', 'normalizing', 'indexing'])
const statusLabel: Record<string, string> = {
  queued: '等待解析', parsing: '读取源文件', normalizing: '生成 Markdown', indexing: '建立索引',
  ready: '可检索', failed: '解析失败', needs_human: '需要处理',
}

function fileIcon(extension: string) {
  if (['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff'].includes(extension)) return FileImage
  if (['.mp4', '.mov', '.mkv', '.avi', '.webm', '.mpeg', '.mpg'].includes(extension)) return FileVideo
  if (['.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma'].includes(extension)) return FileAudio
  if (['.xlsx', '.xlsm', '.csv', '.tsv'].includes(extension)) return FileSpreadsheet
  return FileText
}

function formatBytes(value: number) {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1)
  return `${(value / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`
}

function formatTime(value?: string | null) {
  if (!value) return '—'
  const time = new Date(value).getTime()
  if (!Number.isFinite(time)) return '—'
  const minutes = Math.max(0, Math.floor((Date.now() - time) / 60000))
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)}小时前`
  if (minutes < 43200) return `${Math.floor(minutes / 1440)}天前`
  return new Date(value).toLocaleDateString('zh-CN')
}

function Status({ document }: { document: KnowledgeDocument }) {
  if (processingStates.has(document.status)) return <span className="inline-flex items-center gap-1.5 text-xs text-[#A5B4FC]"><Loader2 className="h-3.5 w-3.5 animate-spin" />{statusLabel[document.status]}</span>
  if (document.status === 'ready') return <span className="inline-flex items-center gap-1.5 text-xs text-[#6EE7B7]"><CheckCircle2 className="h-3.5 w-3.5" />可检索</span>
  return <span className="inline-flex items-center gap-1.5 text-xs text-[#FCA5A5]"><AlertCircle className="h-3.5 w-3.5" />{statusLabel[document.status] || document.status}</span>
}

export default function KnowledgeBase() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [stats, setStats] = useState<KnowledgeStats | null>(null)
  const [collections, setCollections] = useState<Array<{ name: string; count: number }>>([])
  const [collection, setCollection] = useState('企业资料')
  const [collectionFilter, setCollectionFilter] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [selected, setSelected] = useState<KnowledgeDocument | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [retrievalQuery, setRetrievalQuery] = useState('')
  const [retrievalResults, setRetrievalResults] = useState<KnowledgeResult[]>([])
  const [retrieving, setRetrieving] = useState(false)
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null)

  const notify = (text: string, error = false) => setToast({ text, error })
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(null), 3200); return () => window.clearTimeout(timer) }, [toast])

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const [documentData, statData, collectionData] = await Promise.all([
        listKnowledgeDocuments({ q: query, collection: collectionFilter }), getKnowledgeStats(), getKnowledgeCollections(),
      ])
      setDocuments(documentData.items)
      setStats(statData)
      setCollections(collectionData.items)
    } catch (error) {
      notify(error instanceof Error ? error.message : '知识库加载失败', true)
    } finally { setLoading(false) }
  }, [collectionFilter, query])

  useEffect(() => { const timer = window.setTimeout(() => refresh(), 180); return () => window.clearTimeout(timer) }, [refresh])
  useEffect(() => {
    if (!documents.some((item) => processingStates.has(item.status))) return
    const timer = window.setInterval(() => refresh(true), 1800)
    return () => window.clearInterval(timer)
  }, [documents, refresh])

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return
    setUploading(true)
    let success = 0
    for (const file of files) {
      try {
        const result = await uploadKnowledgeDocument(file, collection.trim() || '企业资料')
        success += 1
        if (result.duplicate) notify(`${file.name} 已在知识库中，无需重复上传`)
      } catch (error) {
        notify(`${file.name}：${error instanceof Error ? error.message : '上传失败'}`, true)
      }
    }
    if (success) notify(`已接收 ${success} 份资料，正在转换为知识`)
    setUploading(false)
    await refresh(true)
  }

  const openDetail = async (document: KnowledgeDocument) => {
    setSelected(document)
    setDetailLoading(true)
    try { setSelected(await getKnowledgeDocument(document.id)) }
    catch (error) { notify(error instanceof Error ? error.message : '详情加载失败', true) }
    finally { setDetailLoading(false) }
  }

  const remove = async (document: KnowledgeDocument) => {
    if (!window.confirm(`从企业知识库移除“${document.filename}”？源文件和索引会一并移除。`)) return
    await deleteKnowledgeDocument(document.id)
    if (selected?.id === document.id) setSelected(null)
    notify('已从知识库移除')
    await refresh(true)
  }

  const reparse = async (document: KnowledgeDocument) => {
    try { await reparseKnowledgeDocument(document.id); notify('已重新开始解析'); setSelected(null); await refresh(true) }
    catch (error) { notify(error instanceof Error ? error.message : '重新解析失败', true) }
  }

  const runRetrieval = async () => {
    if (!retrievalQuery.trim()) return
    setRetrieving(true)
    try { setRetrievalResults((await testKnowledgeRetrieval(retrievalQuery, collectionFilter)).results) }
    catch (error) { notify(error instanceof Error ? error.message : '检索失败', true) }
    finally { setRetrieving(false) }
  }

  const metricItems = useMemo(() => [
    { label: '企业资料', value: stats?.total_docs ?? 0, hint: '已保存源文件', icon: Archive },
    { label: '知识片段', value: stats?.total_chunks ?? 0, hint: '可供超级员工检索', icon: Layers3 },
    { label: '正在整理', value: stats?.processing ?? 0, hint: '解析与建立索引', icon: Loader2 },
    { label: '占用空间', value: formatBytes(stats?.total_bytes ?? 0), hint: stats?.storage_dir || '系统知识目录', icon: HardDrive },
  ], [stats])

  return (
    <div className="min-h-full bg-[#090E18] px-6 py-5 text-[#E2E8F0]">
      <p className="mb-5 text-sm text-[#94A3B8]">上传企业资料，系统会统一整理为 Markdown，并自动供超级员工检索使用。</p>

      <section className="grid overflow-hidden rounded-lg border border-[#1E293B] bg-[#0F1625] sm:grid-cols-2 xl:grid-cols-4">
        {metricItems.map(({ label, value, hint, icon: Icon }, index) => <div key={label} className={`px-5 py-4 ${index ? 'border-l border-[#1E293B]' : ''}`}><div className="flex items-center justify-between"><p className="text-xs text-[#64748B]">{label}</p><Icon className={`h-4 w-4 text-[#818CF8] ${label === '正在整理' && Number(value) > 0 ? 'animate-spin' : ''}`} /></div><p className="mt-2 text-xl font-semibold text-[#F8FAFC]">{value}</p><p className="mt-1 truncate text-xs text-[#475569]" title={hint}>{hint}</p></div>)}
      </section>

      <section
        className={`mt-5 flex min-h-28 items-center justify-between gap-5 rounded-lg border border-dashed px-5 py-4 transition ${dragging ? 'border-[#818CF8] bg-[#6366F1]/10' : 'border-[#334155] bg-[#0F1625]'}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); void uploadFiles(Array.from(event.dataTransfer.files)) }}
      >
        <div className="flex min-w-0 items-center gap-4"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-[#6366F1]/15 text-[#A5B4FC]"><Upload className="h-5 w-5" /></div><div><h2 className="text-sm font-semibold text-[#F1F5F9]">添加企业资料</h2><p className="mt-1 text-xs leading-5 text-[#64748B]">文档、表格、演示文稿、图片、录音和视频均可直接上传。</p></div></div>
        <div className="flex shrink-0 items-center gap-2"><input value={collection} onChange={(event) => setCollection(event.target.value)} className={`${inputClass} w-36`} aria-label="资料分类" /><input ref={fileRef} type="file" multiple className="hidden" onChange={(event) => { void uploadFiles(Array.from(event.target.files || [])); event.target.value = '' }} /><button onClick={() => fileRef.current?.click()} disabled={uploading} className={`${primaryButton} min-w-24`}>{uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}{uploading ? '正在接收' : '选择文件'}</button></div>
      </section>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(340px,.75fr)]">
        <section className="overflow-hidden rounded-lg border border-[#1E293B] bg-[#0F1625]">
          <div className="flex flex-wrap items-center gap-3 border-b border-[#1E293B] px-5 py-4"><div className="relative min-w-52 flex-1"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[#475569]" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索文件名" className={`${inputClass} pl-9`} /></div><select value={collectionFilter} onChange={(event) => setCollectionFilter(event.target.value)} className={`${inputClass} w-40`}><option value="">全部分类</option>{collections.map((item) => <option key={item.name} value={item.name}>{item.name} ({item.count})</option>)}</select></div>
          <div className="min-h-80 divide-y divide-[#1E293B]">
            {loading ? <div className="flex h-72 items-center justify-center text-sm text-[#64748B]"><Loader2 className="mr-2 h-4 w-4 animate-spin" />正在读取知识库</div> : documents.length === 0 ? <div className="flex h-72 flex-col items-center justify-center text-center"><BookOpen className="h-8 w-8 text-[#334155]" /><p className="mt-3 text-sm text-[#94A3B8]">还没有符合条件的资料</p><p className="mt-1 text-xs text-[#475569]">添加第一份企业资料后，超级员工即可引用它。</p></div> : documents.map((document) => { const Icon = fileIcon(document.extension); return <button key={document.id} onClick={() => void openDetail(document)} className="group flex w-full items-center gap-4 px-5 py-4 text-left transition hover:bg-[#141D2E]"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-[#172033] text-[#A5B4FC]"><Icon className="h-5 w-5" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="truncate text-sm font-medium text-[#E2E8F0]">{document.filename}</p><span className="rounded bg-[#1E293B] px-1.5 py-0.5 text-[10px] uppercase text-[#64748B]">{document.extension.slice(1) || 'file'}</span></div><div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#64748B]"><span>{document.collection}</span><span>{formatBytes(document.size)}</span><span>{document.chunk_count} 个知识片段</span><span>{formatTime(document.updated_at)}</span></div>{processingStates.has(document.status) && <div className="mt-2 h-1 overflow-hidden rounded-full bg-[#1E293B]"><div className="h-full rounded-full bg-[#6366F1] transition-all" style={{ width: `${Math.max(document.progress, 5)}%` }} /></div>}{document.error && <p className="mt-2 truncate text-xs text-[#FCA5A5]">{document.error}</p>}</div><div className="flex shrink-0 items-center gap-3"><Status document={document} /><ChevronRight className="h-4 w-4 text-[#334155] transition group-hover:translate-x-0.5 group-hover:text-[#818CF8]" /></div></button> })}
          </div>
        </section>

        <section className="self-start overflow-hidden rounded-lg border border-[#1E293B] bg-[#0F1625]">
          <div className="border-b border-[#1E293B] px-5 py-4"><div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-[#A5B4FC]" /><h2 className="text-sm font-semibold text-[#F1F5F9]">检索试问</h2></div><p className="mt-1 text-xs leading-5 text-[#64748B]">查看超级员工回答问题时能找到哪些企业资料。</p></div>
          <div className="p-5"><textarea value={retrievalQuery} onChange={(event) => setRetrievalQuery(event.target.value)} rows={4} placeholder="例如：我们的产品适合哪些客户？" className={`${inputClass} resize-none leading-6`} /><button onClick={() => void runRetrieval()} disabled={!retrievalQuery.trim() || retrieving} className={`${primaryButton} mt-3 w-full`}>{retrieving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}查找企业知识</button><div className="mt-4 space-y-2">{retrievalResults.map((result, index) => <button key={result.chunk_id} onClick={() => { const document = documents.find((item) => item.id === result.document_id); if (document) void openDetail(document) }} className="w-full rounded-md border border-[#243047] bg-[#0B0F1A] p-3 text-left transition hover:border-[#46577A]"><div className="flex items-center justify-between gap-2"><p className="truncate text-xs font-medium text-[#C7D2FE]">{index + 1}. {result.filename}</p><span className="text-[10px] text-[#64748B]">{Math.round(result.score * 100)}%</span></div><p className="mt-2 line-clamp-3 text-xs leading-5 text-[#94A3B8]">{result.content}</p><p className="mt-2 truncate text-[10px] text-[#475569]">{result.locator || result.heading || result.collection}</p></button>)}</div></div>
        </section>
      </div>

      {selected && <div className="fixed inset-0 z-50 flex justify-end bg-black/55 backdrop-blur-sm" onMouseDown={(event) => { if (event.currentTarget === event.target) setSelected(null) }}><aside className="h-full w-full max-w-2xl overflow-y-auto border-l border-[#273449] bg-[#0F1624] shadow-2xl"><div className="sticky top-0 z-10 border-b border-[#273449] bg-[#0F1624]/95 px-6 py-5 backdrop-blur"><div className="flex items-start justify-between gap-4"><div className="min-w-0"><p className="text-xs text-[#818CF8]">{selected.collection}</p><h2 className="mt-1 truncate text-lg font-semibold text-[#F1F5F9]">{selected.filename}</h2><div className="mt-2 flex items-center gap-4 text-xs text-[#64748B]"><Status document={selected} /><span>{formatBytes(selected.size)}</span><span>{selected.chunk_count} 个片段</span></div></div><button onClick={() => setSelected(null)} className="flex h-8 w-8 items-center justify-center rounded-md text-[#64748B] transition hover:bg-[#1E293B] hover:text-white" title="关闭"><X className="h-4 w-4" /></button></div><div className="mt-4 flex flex-wrap gap-2"><a href={knowledgeSourceUrl(selected.id)} target="_blank" rel="noreferrer" className={secondaryButton}><FolderOpen className="h-4 w-4" />打开源文件</a><button onClick={() => void reparse(selected)} className={secondaryButton}><RefreshCw className="h-4 w-4" />重新解析</button><button onClick={() => void remove(selected)} className={`${secondaryButton} ml-auto text-[#FCA5A5] hover:border-[#7F1D1D]`}><Trash2 className="h-4 w-4" />移除</button></div></div><div className="p-6">{detailLoading ? <div className="flex h-72 items-center justify-center text-sm text-[#64748B]"><Loader2 className="mr-2 h-4 w-4 animate-spin" />正在读取 Markdown</div> : selected.error && !selected.markdown ? <div className="rounded-lg border border-[#7F1D1D]/50 bg-[#450A0A]/20 p-5"><p className="text-sm text-[#FCA5A5]">{selected.error}</p></div> : <article className="prose prose-invert max-w-none prose-headings:text-[#F1F5F9] prose-p:text-[#CBD5E1] prose-p:leading-7 prose-li:text-[#CBD5E1] prose-strong:text-white prose-code:text-[#A5B4FC] prose-a:text-[#818CF8]"><ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.markdown || '资料正在转换为 Markdown。'}</ReactMarkdown></article>}</div></aside></div>}
      {toast && <div className={`fixed bottom-6 right-6 z-[70] max-w-md rounded-lg border px-4 py-3 text-sm shadow-2xl ${toast.error ? 'border-[#EF4444]/30 bg-[#3F1117] text-[#FCA5A5]' : 'border-[#10B981]/30 bg-[#10231E] text-[#A7F3D0]'}`}>{toast.text}</div>}
    </div>
  )
}
