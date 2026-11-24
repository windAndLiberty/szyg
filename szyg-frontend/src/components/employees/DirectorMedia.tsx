import { useEffect, useRef, useState, type ReactNode, type Dispatch, type SetStateAction } from 'react'
import { Download, FileImage, FileMusic, Film } from 'lucide-react'
import { apiGet, getErrorMessage, getToken } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

export type EmployeeAsset = { url: string; name: string; kind: 'video' | 'image' | 'audio' }
const maxAttachments = 8
const managedFile = /^\/api\/media\/files\/(video|audio|image)\/([^/\\?#<>\x00-\x1f]+)$/

function localAsset(url: string) {
  const match = url.match(managedFile)
  if (!match) return null
  try {
    const name = decodeURIComponent(match[2])
    if (!name || /[/\\\x00-\x1f]/.test(name) || name === '.' || name === '..') return null
    return { url: '/api/media/files/' + match[1] + '/' + encodeURIComponent(name), name, kind: match[1] as EmployeeAsset['kind'] }
  } catch { return null }
}

export function useEmployeeMedia(enabled: boolean, assets: EmployeeAsset[], setAssets: Dispatch<SetStateAction<EmployeeAsset[]>>) {
  const { t } = useI18n()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const request = useRef<AbortController | null>(null)
  useEffect(() => {
    if (!enabled) setBusy(false)
    return () => { request.current?.abort(); request.current = null }
  }, [enabled])
  async function add(files: File[]) {
    if (!enabled || !files.length || request.current) return
    if (assets.length + files.length > maxAttachments) {
      setError(t('composer.mediaLimit', {count:maxAttachments}))
      return
    }
    const controller = new AbortController()
    request.current = controller
    setError('')
    setBusy(true)
    try {
      for (const file of files) {
        const data = new FormData()
        data.append('file', file)
        const token = getToken()
        const response = await fetch('/api/media/conversation-assets', { method: 'POST', body: data, signal: controller.signal,
          headers: token ? {Authorization: 'Bearer ' + token} : {} })
        const result = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : t('director.importFailed'))
        const asset = localAsset(String(result.url))
        if (!asset) throw new Error(t('director.importFailed'))
        if (!controller.signal.aborted) setAssets(current => current.some(item => item.url === asset.url) ? current : [...current, { ...asset, name: file.name }])
      }
    } catch (reason) {
      if (!controller.signal.aborted) setError(getErrorMessage(reason, t('director.importFailed')))
    } finally {
      if (request.current === controller) request.current = null
      if (!controller.signal.aborted) setBusy(false)
    }
  }
  function message(text: string) {
    if (!assets.length) return text
    const references = assets.map(asset => {
      const name = asset.name.replace(/[\r\n\[\]\\]/g, ' ')
      return '[' + name + '](' + asset.url + ')'
    })
    return [text.trim(), t('director.attached') + '\n' + references.join('\n')].filter(Boolean).join('\n\n')
  }
  return { assets, busy, error, add, message,
    remove: (url: string) => setAssets(items => items.filter(item => item.url !== url)), clear: () => { setAssets([]); setError('') } }
}

export function EmployeeMediaMessage({ text }: { text: string }) {
  const pieces: ReactNode[] = []
  const outputs = new Map<string, EmployeeAsset>()
  const references = /!?\[([^\]\n]{1,255})\]\((\/api\/media\/files\/(?:video|audio|image)\/[^/\\?#<>\n)]+)\)|(?<![\w/:.])(\/api\/media\/files\/(?:video|audio|image)\/[^\s/\\?#<>"'()[\]，。；、]+?\.(?:mp4|mov|webm|mkv|m4v|avi|png|jpe?g|gif|webp|bmp|wav|mp3|m4a|aac|ogg|flac))(?=$|[^\w%-])/giu
  let offset = 0
  for (const match of text.matchAll(references)) {
    const asset = localAsset(match[2] || match[3])
    if (!asset) continue
    const label = match[1] || asset.name
    pieces.push(text.slice(offset, match.index))
    pieces.push(<a key={match.index} className="text-accent-ink underline underline-offset-2" href={asset.url} download={asset.name}>{label}</a>)
    if (!outputs.has(asset.url)) outputs.set(asset.url, {...asset, name:label})
    offset = match.index + match[0].length
  }
  pieces.push(text.slice(offset))
  return <>{pieces}
    {Array.from(outputs.values()).map(asset => <DirectorAssetPreview key={asset.url} url={asset.url} label={asset.name}/>)}
  </>
}

export function DirectorAssetPreview({url, label}: {url: string; label?: string}) {
  const { t } = useI18n()
  const asset = localAsset(url)
  if (!asset) return null
  const name = label || asset.name
  return <figure className="my-2 w-full max-w-lg overflow-hidden rounded-xl border border-border">
    {asset.kind === 'video' ? <video src={asset.url} aria-label={name} controls playsInline preload="metadata" className="max-h-80 w-full bg-black"/>
      : asset.kind === 'audio' ? <audio src={asset.url} aria-label={name} controls preload="none" className="w-full"/>
      : <img src={asset.url} alt={name} loading="lazy" className="max-h-72 w-full object-contain"/>}
    <figcaption className="flex items-center gap-2 px-3 py-2 text-xs">
      {asset.kind === 'video' ? <Film size={14}/> : asset.kind === 'audio' ? <FileMusic size={14}/> : <FileImage size={14}/>}
      <span className="min-w-0 flex-1 truncate">{name}</span>
      <a href={asset.url} download aria-label={t('director.download', {name:asset.name})} title={t('director.download', {name:asset.name})}
        className="rounded p-1 hover:bg-muted"><Download size={15}/></a>
    </figcaption>
  </figure>
}

export function DirectorRuntimeInfo() {
  const { t } = useI18n()
  const [status, setStatus] = useState<'checking' | 'ready' | 'missing' | 'unavailable'>('checking')
  const [revision, setRevision] = useState('main')
  const upstream = 'https://github.com/OpenMontageInc/OpenMontage'
  useEffect(() => {
    let current = true
    void apiGet<{ready: boolean; installed: boolean; revision?: string}>('/api/director/capabilities')
      .then(result => {
        if (!current) return
        setStatus(result.ready ? 'ready' : result.installed ? 'unavailable' : 'missing')
        if (result.revision && /^[a-f0-9]{40}$/.test(result.revision)) setRevision(result.revision)
      })
      .catch(() => { if (current) setStatus('unavailable') })
    return () => { current = false }
  }, [])
  const label = { checking:'settings.loading', ready:'director.ready', missing:'director.installHelp', unavailable:'director.checkFailed' }[status]
  return <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-6 py-5 text-xs text-muted-foreground">
    <span role="status">{t(label)}</span>
    <a className="ml-auto underline underline-offset-2" target="_blank" rel="noreferrer"
      href={upstream + '/tree/' + revision}>OpenMontage</a>
    <a className="underline underline-offset-2" target="_blank" rel="noreferrer"
      href={upstream + '/blob/' + revision + '/LICENSE'}>AGPL-3.0</a>
  </div>
}
