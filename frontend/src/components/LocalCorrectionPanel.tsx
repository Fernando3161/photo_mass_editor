import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '../api'
import type { LocalJob, LocalRecommendation, LocalSettings, PhotoDetail } from '../types'

interface Props {
  photo: PhotoDetail
  onBeforeRun: () => Promise<boolean>
  onRefresh: () => Promise<void>
  reviewArea: ReactNode
}

const controls: Array<[keyof LocalSettings, string, number, number, number]> = [
  ['levels_strength', 'Auto levels strength', 0, 1, .05],
  ['black_point', 'Black point', 0, .2, .005],
  ['white_point', 'White point', .8, 1, .005],
  ['exposure_ev', 'Exposure (EV)', -1, 1, .05],
  ['red_gain', 'Red balance', .85, 1.15, .01],
  ['blue_gain', 'Blue balance', .85, 1.15, .01],
  ['shadow_lift', 'Shadows', 0, .4, .02],
  ['highlight_compression', 'Highlights', 0, .4, .02],
  ['denoise', 'Denoise', 0, 2, 1],
  ['sharpen', 'Sharpen', 0, 1, .05],
  ['straighten_deg', 'Straighten (degrees)', -10, 10, .1],
  ['lens_k1', 'Lens correction', -.12, .12, .005],
  ['perspective_vertical', 'Vertical perspective', -.2, .2, .01],
]

function displayValue(value: number, step: number) {
  if (step >= 1) return String(Math.round(value))
  const decimals = Math.max(0, Math.ceil(-Math.log10(step)))
  return value.toFixed(decimals)
}

export function LocalCorrectionPanel({ photo, onBeforeRun, onRefresh, reviewArea }: Props) {
  const [recommendation, setRecommendation] = useState<LocalRecommendation | null>(null)
  const [settings, setSettings] = useState<LocalSettings | null>(null)
  const [jobs, setJobs] = useState<LocalJob[]>([])
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [retryOverride, setRetryOverride] = useState(false)
  const [replaceApproved, setReplaceApproved] = useState(false)
  const [livePreview, setLivePreview] = useState(true)
  const [previewState, setPreviewState] = useState<'IDLE' | 'SCHEDULED' | 'LOADING' | 'READY' | 'ERROR'>('IDLE')
  const previewTimer = useRef<number | null>(null)
  const previewController = useRef<AbortController | null>(null)
  const previewSequence = useRef(0)
  const latestPreviewSettings = useRef<LocalSettings | null>(null)
  const lastPreviewStarted = useRef(0)
  const livePreviewRef = useRef(true)
  const previewUrlRef = useRef<string | null>(null)
  const hasApproved = photo.versions.some((version) => version.review_status === 'APPROVED')

  const schedulePreview = useCallback((next: LocalSettings, immediate = false) => {
    latestPreviewSettings.current = next
    previewSequence.current += 1
    if (!livePreviewRef.current && !immediate) return
    if (previewTimer.current !== null) {
      if (!immediate) return
      window.clearTimeout(previewTimer.current)
      previewTimer.current = null
    }
    const elapsed = performance.now() - lastPreviewStarted.current
    const delay = immediate ? 0 : Math.max(0, 150 - elapsed)
    setPreviewState(delay ? 'SCHEDULED' : 'LOADING')
    previewTimer.current = window.setTimeout(() => {
      previewTimer.current = null
      const target = latestPreviewSettings.current
      if (!target) return
      previewController.current?.abort()
      const controller = new AbortController()
      previewController.current = controller
      const sequence = previewSequence.current
      lastPreviewStarted.current = performance.now()
      setPreviewState('LOADING')
      void api.localPreview(photo.id, target, controller.signal).then(async (blob) => {
        if (sequence !== previewSequence.current) return
        const nextUrl = URL.createObjectURL(blob)
        const candidate = new Image()
        candidate.src = nextUrl
        if (typeof candidate.decode === 'function') await candidate.decode().catch(() => {})
        if (sequence !== previewSequence.current) {
          URL.revokeObjectURL(nextUrl)
          return
        }
        setPreviewUrl((current) => {
          if (current) URL.revokeObjectURL(current)
          previewUrlRef.current = nextUrl
          return nextUrl
        })
        setPreviewState('READY')
      }).catch((error: Error) => {
        if (error.name === 'AbortError' || sequence !== previewSequence.current) return
        setPreviewState('ERROR')
        setMessage(error.message)
      })
    }, delay)
  }, [photo.id])

  useEffect(() => {
    let active = true
    setRecommendation(null)
    setSettings(null)
    setMessage('')
    setRetryOverride(false)
    setReplaceApproved(false)
    setLivePreview(true)
    livePreviewRef.current = true
    latestPreviewSettings.current = null
    lastPreviewStarted.current = 0
    if (previewTimer.current !== null) window.clearTimeout(previewTimer.current)
    previewTimer.current = null
    previewController.current?.abort()
    previewController.current = null
    previewSequence.current += 1
    setPreviewState('IDLE')
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current)
      previewUrlRef.current = null
      return null
    })
    void api.localRecommendation(photo.id).then((result) => {
      if (active) {
        setRecommendation(result)
        setSettings(result.settings)
        schedulePreview(result.settings, true)
      }
    }).catch((error: Error) => { if (active) setMessage(error.message) })
    void api.localJobs(photo.id).then((result) => { if (active) setJobs(result.jobs) })
      .catch((error: Error) => { if (active) setMessage(error.message) })
    return () => {
      active = false
      if (previewTimer.current !== null) window.clearTimeout(previewTimer.current)
      previewTimer.current = null
      previewController.current?.abort()
      previewController.current = null
      previewSequence.current += 1
    }
  }, [photo.id, schedulePreview])

  useEffect(() => {
    if (!jobs.some((job) => job.status === 'QUEUED' || job.status === 'RUNNING')) return
    const timer = window.setInterval(() => {
      void api.localJobs(photo.id).then(async (result) => {
        setJobs(result.jobs)
        if (result.jobs.every((job) => job.status !== 'QUEUED' && job.status !== 'RUNNING')) {
          await onRefresh()
          setMessage(result.jobs[0]?.status === 'SUCCEEDED' ? 'Local version ready for visual review.' : result.jobs[0]?.error || 'Local job finished.')
        }
      }).catch((error: Error) => setMessage(error.message))
    }, 1200)
    return () => window.clearInterval(timer)
  }, [jobs, photo.id, onRefresh])

  useEffect(() => () => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    previewUrlRef.current = null
  }, [])

  const change = (key: keyof LocalSettings, value: number) => {
    if (!settings) return
    const next = { ...settings, [key]: value }
    setSettings(next)
    schedulePreview(next)
  }

  const choosePreset = async (presetId: string) => {
    setBusy(true)
    try {
      const result = await api.localRecommendation(photo.id, presetId)
      setRecommendation(result)
      setSettings(result.settings)
      schedulePreview(result.settings, true)
      setMessage('Recommended settings loaded.')
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }

  const toggleLivePreview = (enabled: boolean) => {
    setLivePreview(enabled)
    livePreviewRef.current = enabled
    if (enabled && settings) {
      schedulePreview(settings, true)
      return
    }
    if (previewTimer.current !== null) window.clearTimeout(previewTimer.current)
    previewTimer.current = null
    previewController.current?.abort()
    previewController.current = null
    previewSequence.current += 1
    setPreviewState(previewUrl ? 'READY' : 'IDLE')
  }

  const run = async () => {
    if (!settings || !recommendation || busy) return
    setBusy(true)
    try {
      if (!(await onBeforeRun())) { setMessage('Save the current draft before creating a local version.'); return }
      const current = await api.localRecommendation(photo.id, settings.preset_id)
      setRecommendation(current)
      const job = await api.runLocal(photo.id, settings, current.photo_revision, retryOverride, replaceApproved)
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)])
      setReplaceApproved(false)
      setMessage('Local correction queued. The new version requires visual approval.')
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="local-corrections edit-workbench">
    <section className="edit-control-column" aria-label="Local correction controls">
      <p>Recommended local corrections are preloaded for this photo. They process the source at full resolution and create a pending version.</p>
      {recommendation && settings && <>
        <label><span>Correction preset</span><select value={settings.preset_id} disabled={busy} onChange={(event) => void choosePreset(event.target.value)}>{recommendation.presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}</select></label>
        <small>{recommendation.measurements.white_balance_note} {recommendation.measurements.geometry_note}</small>
        <div className="edit-settings">{controls.map(([key, label, min, max, step]) => <label className="correction-slider" key={key}><span className="slider-heading"><span>{label}</span><output>{displayValue(settings[key] as number, step)}</output></span><input aria-label={label} type="range" min={min} max={max} step={step} value={settings[key] as number} onChange={(event) => change(key, Number(event.target.value))} /></label>)}</div>
        <details><summary>Crop</summary><div className="crop-sliders">{(['Left', 'Top', 'Right', 'Bottom'] as const).map((label, index) => {
          const limits = index === 0 ? [0, (settings.crop[2] - .5) * 100]
            : index === 1 ? [0, (settings.crop[3] - .5) * 100]
              : index === 2 ? [(settings.crop[0] + .5) * 100, 100]
                : [(settings.crop[1] + .5) * 100, 100]
          return <label className="correction-slider" key={label}><span className="slider-heading"><span>{label}</span><output>{Math.round(settings.crop[index] * 100)}%</output></span><input aria-label={`${label} crop`} type="range" min={Math.round(limits[0])} max={Math.round(limits[1])} step="1" value={Math.round(settings.crop[index] * 100)} onChange={(event) => {
            const crop = [...settings.crop] as LocalSettings['crop']
            crop[index] = Number(event.target.value) / 100
            const next = { ...settings, crop }
            setSettings(next)
            schedulePreview(next)
          }} /></label>
        })}</div></details>
        <label className="consent-row"><input type="checkbox" checked={livePreview} onChange={(event) => toggleLivePreview(event.target.checked)} /> Live preview while adjusting</label>
        <div className="edit-button-row"><button type="button" className="button-secondary" disabled={busy} onClick={() => { setSettings(recommendation.settings); schedulePreview(recommendation.settings, true) }}>Reset</button><button type="button" className="button-secondary" disabled={busy || !settings} onClick={() => settings && schedulePreview(settings, true)}>Refresh preview</button></div>
        <label className="consent-row"><input type="checkbox" checked={retryOverride} onChange={(event) => setRetryOverride(event.target.checked)} /> Retry an identical rejected recipe</label>
        {hasApproved && <label className="consent-row"><input type="checkbox" checked={replaceApproved} onChange={(event) => setReplaceApproved(event.target.checked)} /> Create a replacement for the approved version</label>}
        <button type="button" className="button-primary" disabled={busy || (hasApproved && !replaceApproved) || jobs.some((job) => job.status === 'QUEUED' || job.status === 'RUNNING')} onClick={() => void run()}>{hasApproved ? 'Create replacement version' : 'Create local version'}</button>
        {hasApproved && !replaceApproved && <small>The current approval stays active until you create, inspect, and explicitly approve a replacement.</small>}
      </>}
      {message && <p role="status">{message}</p>}
      {jobs.length > 0 && <details><summary>Local job receipts ({jobs.length})</summary><ol>{jobs.map((job) => <li key={job.id}>{job.status.toLowerCase()} · {job.id.slice(0, 8)}{job.error ? ` · ${job.error}` : ''}</li>)}</ol></details>}
    </section>
    <aside className="edit-preview-column" aria-label="Local correction preview">
      <div className="edit-column-heading"><span>Preview local correction</span><small aria-live="polite">{previewState === 'LOADING' || previewState === 'SCHEDULED' ? 'Updating…' : livePreview ? 'Live preview · final renders at source resolution' : 'Manual preview · final renders at source resolution'}</small></div>
      <div className={`edit-preview-stage ${previewUrl ? '' : 'is-empty'} ${previewState === 'LOADING' || previewState === 'SCHEDULED' ? 'is-updating' : ''}`} aria-busy={previewState === 'LOADING' || previewState === 'SCHEDULED'}>{previewUrl ? <img className="local-preview-image" src={previewUrl} alt="Preview of local correction" /> : <div className="preview-placeholder"><span aria-hidden="true">◇</span><strong>{previewState === 'LOADING' || previewState === 'SCHEDULED' ? 'Preparing live preview' : 'No preview yet'}</strong><p>Move a correction slider to render the local preview automatically.</p></div>}</div>
      {reviewArea}
    </aside>
  </div>
}
