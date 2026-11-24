import { useEffect, useRef, useState } from 'react'
import { getErrorMessage, getToken } from '@/lib/api'
import { useI18n } from '@/lib/i18n'

const sampleRate = 16_000
const limitSeconds = 120

async function toVoiceWav(recording: Blob) {
  const context = new OfflineAudioContext(1, 1, sampleRate)
  const decoded = await context.decodeAudioData(await recording.arrayBuffer())
  const length = Math.min(decoded.length, limitSeconds * sampleRate)
  const wav = new DataView(new ArrayBuffer(44 + length * 2))
  const write = (offset: number, word: string) => {
    for (let i = 0; i < word.length; i++) wav.setUint8(offset + i, word.charCodeAt(i))
  }
  write(0, 'RIFF')
  wav.setUint32(4, 36 + length * 2, true)
  write(8, 'WAVE')
  write(12, 'fmt ')
  wav.setUint32(16, 16, true)
  wav.setUint16(20, 1, true)
  wav.setUint16(22, 1, true)
  wav.setUint32(24, sampleRate, true)
  wav.setUint32(28, sampleRate * 2, true)
  wav.setUint16(32, 2, true)
  wav.setUint16(34, 16, true)
  write(36, 'data')
  wav.setUint32(40, length * 2, true)
  const channels = Array.from({length: decoded.numberOfChannels}, (_, i) => decoded.getChannelData(i))
  for (let i = 0; i < length; i++) {
    let sum = 0
    for (const channel of channels) sum += channel[i]
    const sample = Math.max(-1, Math.min(1, sum / channels.length))
    wav.setInt16(44 + i * 2, sample < 0 ? sample * 32768 : sample * 32767, true)
  }
  return new Blob([wav.buffer], {type: 'audio/wav'})
}

async function transcribe(recording: Blob, signal: AbortSignal): Promise<string> {
  const token = getToken()
  const response = await fetch('/api/media/dictation/' + crypto.randomUUID(), {
    method: 'POST',
    headers: { 'Content-Type': 'audio/wav', ...(token ? {Authorization: 'Bearer ' + token} : {}) },
    body: await toVoiceWav(recording), signal,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok || !data.text) throw new Error(typeof data.detail === 'string' ? data.detail : '')
  return data.text
}

type VoiceState = 'idle' | 'requesting' | 'recording' | 'transcribing'
export function useDictation(active: boolean, onText: (text: string) => void) {
  const { t } = useI18n()
  const [state, setState] = useState<VoiceState>('idle')
  const [error, setError] = useState('')
  const [seconds, setSeconds] = useState(0)
  const activeJob = useRef<AbortController | null>(null)
  const mic = useRef<MediaRecorder | null>(null)
  const onTextRef = useRef(onText)
  onTextRef.current = onText

  function discard() {
    activeJob.current?.abort()
    activeJob.current = null
    const recorder = mic.current
    mic.current = null
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    recorder?.stream.getTracks().forEach(track => track.stop())
  }

  function cancel() {
    discard()
    setError('')
    setState('idle')
  }

  useEffect(() => {
    if (!active) cancel()
    const hide = () => { if (document.hidden) cancel() }
    document.addEventListener('visibilitychange', hide)
    return () => { document.removeEventListener('visibilitychange', hide); discard() }
  }, [active])

  useEffect(() => {
    if (state !== 'recording') return
    const start = Date.now()
    const clock = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 250)
    const cutoff = window.setTimeout(() => { if (mic.current?.state === 'recording') mic.current.stop() }, limitSeconds * 1000)
    return () => { clearInterval(clock); clearTimeout(cutoff) }
  }, [state])

  async function toggle() {
    if (mic.current?.state === 'recording') { mic.current.stop(); return }
    if (activeJob.current || !active) return
    setError('')
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError(t('composer.micUnsupported')); return
    }
    const job = new AbortController()
    activeJob.current = job
    setState('requesting')
    let stream: MediaStream | undefined
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1, echoCancellation:true},video:false})
      if (job.signal.aborted) { stream.getTracks().forEach(track => track.stop()); return }
      const recorder = new MediaRecorder(stream)
      mic.current = recorder
      const chunks: Blob[] = []
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data) }
      recorder.onerror = () => { if (!job.signal.aborted) { cancel(); setError(t('composer.micFailed')) } }
      recorder.onstop = async () => {
        recorder.stream.getTracks().forEach(track => track.stop())
        if (job.signal.aborted) return
        mic.current = null
        setState('transcribing')
        try {
          const text = await transcribe(new Blob(chunks, {type:recorder.mimeType}), job.signal)
          if (!job.signal.aborted) onTextRef.current(text)
        } catch (reason) {
          if (!job.signal.aborted) setError(getErrorMessage(reason, t('composer.transcriptionFailed')))
        } finally {
          if (!job.signal.aborted) { activeJob.current = null; setState('idle') }
        }
      }
      recorder.start()
      setSeconds(0)
      setState('recording')
    } catch (reason) {
      stream?.getTracks().forEach(track => track.stop())
      if (!job.signal.aborted) {
        cancel()
        setError(t(reason instanceof DOMException && reason.name === 'NotAllowedError' ? 'composer.micDenied' : 'composer.micFailed'))
      }
    }
  }
  return {state, seconds, error, toggle, cancel, clearError: () => setError('')}
}
