import { useEffect, useState, type ReactNode } from 'react'
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
  const hasApproved = photo.versions.some((version) => version.review_status === 'APPROVED')

  useEffect(() => {
    let active = true
    setRecommendation(null)
    setSettings(null)
    setMessage('')
    setRetryOverride(false)
    setReplaceApproved(false)
    void api.localRecommendation(photo.id).then((result) => {
      if (active) { setRecommendation(result); setSettings(result.settings) }
    }).catch((error: Error) => { if (active) setMessage(error.message) })
    void api.localJobs(photo.id).then((result) => { if (active) setJobs(result.jobs) })
      .catch((error: Error) => { if (active) setMessage(error.message) })
    return () => { active = false }
  }, [photo.id])

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

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const change = (key: keyof LocalSettings, value: number) => {
    if (!settings) return
    setSettings({ ...settings, [key]: value })
    setPreviewUrl(null)
  }

  const choosePreset = async (presetId: string) => {
    setBusy(true)
    try {
      const result = await api.localRecommendation(photo.id, presetId)
      setRecommendation(result)
      setSettings(result.settings)
      setPreviewUrl(null)
      setMessage('Recommended settings loaded.')
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }

  const preview = async () => {
    if (!settings) return
    setBusy(true)
    try {
      const blob = await api.localPreview(photo.id, settings)
      setPreviewUrl(URL.createObjectURL(blob))
      setMessage('Local preview ready. The final master renders at source resolution.')
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
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
            setSettings({ ...settings, crop })
            setPreviewUrl(null)
          }} /></label>
        })}</div></details>
        <div className="edit-button-row"><button type="button" className="button-secondary" disabled={busy} onClick={() => { setSettings(recommendation.settings); setPreviewUrl(null) }}>Reset</button><button type="button" className="button-secondary" disabled={busy} onClick={() => void preview()}>Preview local correction</button></div>
        <label className="consent-row"><input type="checkbox" checked={retryOverride} onChange={(event) => setRetryOverride(event.target.checked)} /> Retry an identical rejected recipe</label>
        {hasApproved && <label className="consent-row"><input type="checkbox" checked={replaceApproved} onChange={(event) => setReplaceApproved(event.target.checked)} /> Create a replacement for the approved version</label>}
        <button type="button" className="button-primary" disabled={busy || (hasApproved && !replaceApproved) || jobs.some((job) => job.status === 'QUEUED' || job.status === 'RUNNING')} onClick={() => void run()}>{hasApproved ? 'Create replacement version' : 'Create local version'}</button>
        {hasApproved && !replaceApproved && <small>The current approval stays active until you create, inspect, and explicitly approve a replacement.</small>}
      </>}
      {message && <p role="status">{message}</p>}
      {jobs.length > 0 && <details><summary>Local job receipts ({jobs.length})</summary><ol>{jobs.map((job) => <li key={job.id}>{job.status.toLowerCase()} · {job.id.slice(0, 8)}{job.error ? ` · ${job.error}` : ''}</li>)}</ol></details>}
    </section>
    <aside className="edit-preview-column" aria-label="Local correction preview">
      <div className="edit-column-heading"><span>Preview local correction</span><small>Preview · final renders at source resolution</small></div>
      <div className={`edit-preview-stage ${previewUrl ? '' : 'is-empty'}`}>{previewUrl ? <img className="local-preview-image" src={previewUrl} alt="Preview of local correction" /> : <div className="preview-placeholder"><span aria-hidden="true">◇</span><strong>No preview yet</strong><p>Adjust the bars, then preview the correction here.</p></div>}</div>
      {reviewArea}
    </aside>
  </div>
}
