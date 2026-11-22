import { useCallback, useEffect, useState } from 'react'
import { apiDel, apiGet, apiPost, getErrorMessage } from '@/lib/api'
import { useI18n } from '@/lib/i18n'
import { Button } from './ui/button'
import { Input } from './ui/input'

const endpoint = '/api/settings/mcp-connections'
type Connection = { id: string; name: string; tools: string[] }
type Catalog = { url: string; tools: { name: string; title: string }[]; connections: Connection[] }

export default function McpConnections() {
  const { t } = useI18n()
  const [catalog, setCatalog] = useState<Catalog>()
  const [name, setName] = useState('')
  const [selected, setSelected] = useState<string[]>(['knowledge.stats'])
  const [issued, setIssued] = useState<{ id: string; token: string }>()
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => setCatalog(await apiGet<Catalog>(endpoint)), [])
  useEffect(() => { void refresh().catch(e => setError(getErrorMessage(e))) }, [refresh])
  useEffect(() => {
    const clear = () => setIssued(undefined)
    window.addEventListener('szyg:keep-alive-active-changed', clear)
    return () => window.removeEventListener('szyg:keep-alive-active-changed', clear)
  }, [])

  async function update(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try { await action(); await refresh() }
    catch (e) { setError(getErrorMessage(e)) }
    finally { setBusy(false) }
  }

  return <section className="max-w-2xl space-y-5">
    <h2 className="text-lg font-semibold">{t('mcp.title')}</h2>
    <p className="text-sm text-muted-foreground">{t('mcp.help')}</p>
    {error && <div role="alert" className="text-sm text-red-500">{error} <Button variant="ghost" onClick={() => { setError(''); void refresh().catch(e => setError(getErrorMessage(e))) }}>{t('重试')}</Button></div>}
    {catalog && <>
      <label className="block space-y-1 text-sm">MCP URL<Input readOnly value={catalog.url} onFocus={e => e.target.select()} /></label>
      <form className="space-y-4 rounded-xl border bg-card p-5" onSubmit={e => {
        e.preventDefault()
        void update(async () => {
          setCopied(false)
          setIssued(await apiPost<{ id: string; token: string }>(endpoint, { name: name.trim(), tools: selected }))
          setName('')
        })
      }}>
        <label className="block space-y-1 text-sm">{t('mcp.client')}<Input value={name} required maxLength={80} onChange={e => setName(e.target.value)} /></label>
        <fieldset className="space-y-2"><legend className="mb-2 text-sm font-medium">{t('mcp.tools')}</legend>
          {catalog.tools.map(tool => <label key={tool.name} className="flex items-center gap-3 text-sm">
            <input type="checkbox" checked={selected.includes(tool.name)} onChange={e => setSelected(
              e.target.checked ? [...selected, tool.name] : selected.filter(item => item !== tool.name)
            )} /><span>{t(`mcp.${tool.name}`)}</span>
          </label>)}
        </fieldset>
        <Button type="submit" disabled={busy || !name.trim() || !selected.length}>{t('mcp.issue')}</Button>
      </form>
      {issued && <div className="space-y-2">
        <label className="block space-y-1 text-sm">{t('mcp.secret')}
          <Input readOnly spellCheck={false} autoComplete="off" value={issued.token} onFocus={e => e.target.select()} />
        </label>
        <Button variant="outline" onClick={async () => {
          try { await navigator.clipboard.writeText(issued.token); setCopied(true) }
          catch (e) { setError(getErrorMessage(e)) }
        }}>{t(copied ? 'mcp.copied' : 'mcp.copy')}</Button>
      </div>}
      {catalog.connections.map(connection => <div key={connection.id} className="flex items-center gap-3 border-b py-3">
        <div className="min-w-0 flex-1"><p className="break-words text-sm font-medium">{connection.name}</p>
          <p className="text-xs leading-5 text-muted-foreground">{connection.tools.map(tool => t(`mcp.${tool}`)).join(' · ')}</p>
        </div>
        <Button variant="outline" disabled={busy} onClick={() => void update(async () => {
          await apiDel(endpoint + '/' + connection.id)
          if (issued?.id === connection.id) setIssued(undefined)
        })}>{t('mcp.revoke')}</Button>
      </div>)}
    </>}
  </section>
}
