import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { EditJob, EditPreview, PhotoDetail } from '../types'

interface Props {
  photo: PhotoDetail
  visiblePhotoIds: string[]
  selectedVersionId: string | null
  onSelectVersion: (id: string) => void
  onBeforeRun: () => Promise<boolean>
  onRefresh: () => Promise<void>
}

export function EditPanel({ photo, visiblePhotoIds, selectedVersionId, onSelectVersion, onBeforeRun, onRefresh }: Props) {
  const [engine, setEngine] = useState<'DETERMINISTIC' | 'GENERATIVE'>('DETERMINISTIC')
  const [scope, setScope] = useState<'CURRENT' | 'VISIBLE'>('CURRENT')
  const [settings, setSettings] = useState({ exposure: 1, contrast: 1, color: 1, sharpness: 1, denoise: 0 })
  const [preview, setPreview] = useState<EditPreview | null>(null)
  const [authorized, setAuthorized] = useState(false)
  const [budget, setBudget] = useState('')
  const [retryOverride, setRetryOverride] = useState(false)
  const [maskId, setMaskId] = useState<string | null>(null)
  const [jobs, setJobs] = useState<EditJob[]>([])
  const [batchId, setBatchId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const submitting = useRef(false)
  const selectedIds = scope === 'CURRENT' ? [photo.id] : visiblePhotoIds.slice(0, 20)
  const selected = photo.versions.find((version) => version.id === selectedVersionId)
  const estimatedCost = Number(preview?.estimated_cost_usd)
  const budgetAmount = Number(budget)
  const budgetReady = engine !== 'GENERATIVE' || (budget !== '' && Number.isFinite(budgetAmount) &&
    Number.isFinite(estimatedCost) && estimatedCost > 0 && budgetAmount >= estimatedCost)
  const runBlocker = busy ? 'Finishing the current action.'
    : !preview ? 'Preview the selected run first.'
    : preview.availability !== 'ready' ? `Provider is ${preview.availability}. Check the preview details.`
    : !preview.items.some((item) => item.eligible) ? 'No selected photo is eligible. Check the preview details.'
    : !budgetReady ? `Enter a budget of at least ${preview.estimated_cost_usd ?? 'the displayed estimate'} USD using a decimal point.`
    : !authorized ? 'Check the authorization box for this run.'
    : null

  useEffect(() => {
    setPreview(null)
    setAuthorized(false)
    setMaskId(null)
    setBatchId(null)
    setMessage('')
    void api.getEdits(photo.id).then((result) => setJobs(result.jobs)).catch((error: Error) => setMessage(error.message))
  }, [photo.id])

  useEffect(() => {
    if (!batchId) return
    const timer = window.setInterval(() => {
      void api.getEditBatch(batchId).then(async (result) => {
        setJobs(result.jobs)
        if (result.jobs.every((job) => !['QUEUED', 'RUNNING'].includes(job.status))) {
          window.clearInterval(timer)
          await onRefresh()
        }
      }).catch((error: Error) => setMessage(error.message))
    }, 1200)
    return () => window.clearInterval(timer)
  }, [batchId, onRefresh])

  const changeSetting = (key: keyof typeof settings, value: number) => {
    setSettings((current) => ({ ...current, [key]: value }))
    setPreview(null)
    setAuthorized(false)
  }

  const previewRun = async () => {
    if (!(await onBeforeRun())) return
    setBusy(true)
    try {
      setPreview(await api.previewEdits(selectedIds, engine, engine === 'DETERMINISTIC' ? settings : {}, maskId, retryOverride))
      setMessage('')
      setAuthorized(false)
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }

  const run = async () => {
    if (!preview || runBlocker || submitting.current) return
    submitting.current = true
    setBusy(true)
    try {
      if (!(await onBeforeRun())) {
        setMessage('Save the current draft, then preview and authorize the run again.')
        setPreview(null)
        setAuthorized(false)
        return
      }
      const ids = preview.items.filter((item) => item.eligible).map((item) => item.photo_id)
      const result = await api.runEdits(ids, engine, engine === 'DETERMINISTIC' ? settings : {},
        engine === 'GENERATIVE' ? Number(budget) : null, retryOverride, maskId)
      setJobs(result.jobs)
      setBatchId(result.jobs[0]?.batch_id || null)
      setMessage(`${result.jobs.length} job${result.jobs.length === 1 ? '' : 's'} queued. Review every returned version before publication.`)
      setAuthorized(false)
      setPreview(null)
    } catch (error) {
      setMessage(`${(error as Error).message} Check job receipts before previewing or retrying.`)
      setPreview(null)
      setAuthorized(false)
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  const review = async (decision: 'APPROVED' | 'REJECTED') => {
    if (!selected) return
    const reason = decision === 'REJECTED' ? window.prompt('Optional rejection reason', '') : ''
    if (reason === null) return
    setBusy(true)
    try {
      await api.reviewVersion(photo.id, selected.id, decision, reason || '')
      await onRefresh()
      setMessage(`Version ${selected.version_number} ${decision.toLowerCase()}.`)
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }

  const uploadMask = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    try {
      const saved = await api.uploadMask(photo.id, file)
      setMaskId(saved.id)
      setPreview(null)
      setAuthorized(false)
      setMessage(`Mask saved for the ${saved.width} × ${saved.height} publication input. A mask guides the model; it cannot guarantee unchanged protected pixels.`)
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }

  const cancel = async (jobId: string) => {
    try {
      const updated = await api.cancelEditJob(jobId)
      setJobs((current) => current.map((job) => job.id === jobId ? updated : job))
      setMessage('Queued job cancelled. A running provider call cannot be stopped reliably.')
    } catch (error) { setMessage((error as Error).message) }
  }

  return <div className="panel-section edit-panel">
    <div className="section-heading"><div><p className="eyebrow">Phase 4</p><h3>Editing and versions</h3></div><span className="phase-chip">Owner review</span></div>
    <p>Editing uses the immutable JPEG publication input, never the original shown on the left. New outputs start pending.</p>
    <label><span>Operation</span><select value={engine} onChange={(event) => { setEngine(event.target.value as typeof engine); setPreview(null); setAuthorized(false); setMaskId(null) }}><option value="DETERMINISTIC">Local deterministic correction</option><option value="GENERATIVE">Generative image edit</option></select></label>
    <label><span>Selection</span><select value={scope} onChange={(event) => { setScope(event.target.value as typeof scope); setPreview(null); setAuthorized(false) }}><option value="CURRENT">Current photo</option><option value="VISIBLE">First 20 visible photos</option></select></label>
    {engine === 'DETERMINISTIC' && <div className="edit-settings">{(Object.keys(settings) as Array<keyof typeof settings>).map((key) => <label key={key}><span>{key}</span><input type="number" min="0" max={key === 'denoise' ? '5' : '2'} step="0.05" value={settings[key]} onChange={(event) => changeSetting(key, Number(event.target.value))} /></label>)}</div>}
    {engine === 'GENERATIVE' && <>
      <p>Provider calls may cost money. Review the estimate and set a planning budget. The budget is an application gate, not an account spending limit.</p>
      <label><span>Run budget in USD</span><input type="number" min="0" step="0.01" value={budget} onChange={(event) => { setBudget(event.target.value); setAuthorized(false) }} /></label>
      {scope === 'CURRENT' && <><a href={`/api/photos/${photo.id}/publication-input`} target="_blank" rel="noreferrer">Open 1600px publication input for mask preparation</a><label><span>Optional transparent PNG mask</span><input type="file" accept="image/png" onChange={(event) => void uploadMask(event.target.files?.[0])} /></label>{maskId && <small>Mask selected: {maskId}</small>}</>}
    </>}
    <button type="button" className="button-secondary" disabled={busy} onClick={() => void previewRun()}>Preview selected run ({selectedIds.length})</button>
    {preview && <div className="edit-preview"><p>{preview.availability} · {preview.model || 'local'} · estimated {preview.estimated_cost_usd ?? 'unknown'} USD</p><small>{preview.cost_note}</small><details><summary>Per-photo eligibility and prompts</summary><ol>{preview.items.map((item) => <li key={item.photo_id}>{item.photo_id.slice(0, 8)}: {item.eligible ? `prompt v${item.prompt_version}` : item.reason}{item.prompt_text && <pre>{item.prompt_text}</pre>}</li>)}</ol></details></div>}
    <label className="consent-row"><input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} /> I authorize this current {engine === 'GENERATIVE' ? 'paid' : 'local'} run</label>
    <label className="consent-row"><input type="checkbox" checked={retryOverride} onChange={(event) => { setRetryOverride(event.target.checked); setPreview(null); setAuthorized(false) }} /> Explicitly retry an identical rejected attempt</label>
    <button type="button" className="button-primary" disabled={runBlocker !== null} aria-describedby="run-readiness" onClick={() => void run()}>Start authorized run</button>
    <small id="run-readiness" className="run-readiness" aria-live="polite">{runBlocker || 'Ready to start the selected run.'}</small>
    {message && <p role="status">{message}</p>}
    {jobs.length > 0 && <details open><summary>Job receipts ({jobs.length})</summary><ol>{jobs.map((job) => <li key={job.id}>{job.photo_id.slice(0, 8)} · {job.engine.toLowerCase()} · {job.status.toLowerCase()}{job.error ? ` · ${job.error}` : ''}{job.actual_cost_usd != null ? ` · ${job.actual_cost_usd} USD reported` : ''}{job.status === 'QUEUED' && <button type="button" className="text-button" onClick={() => void cancel(job.id)}>Cancel queued</button>}</li>)}</ol></details>}
    {photo.versions.length > 0 && <div className="version-review"><h4>Immutable versions</h4><div className="version-list">{photo.versions.map((version) => <button type="button" key={version.id} className={version.id === selectedVersionId ? 'is-current' : ''} onClick={() => onSelectVersion(version.id)}>v{version.version_number} · {version.review_status}</button>)}</div>{selected && <><a href={selected.image_url} download={`photo-edit-v${selected.version_number}.jpg`}>Download selected version</a>{selected.rejection_reason && <small>Rejection: {selected.rejection_reason}</small>}{selected.review_status === 'PENDING' && <div className="review-actions"><button type="button" className="button-secondary" disabled={busy} onClick={() => void review('REJECTED')}>Reject selected</button><button type="button" className="button-primary" disabled={busy} onClick={() => void review('APPROVED')}>Approve selected</button></div>}</>}</div>}
  </div>
}
