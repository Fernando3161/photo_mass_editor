import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { EditJob, EditPreview, PhotoDetail, PhotoSummary } from '../types'
import { LocalCorrectionPanel } from './LocalCorrectionPanel'
import { BatchPanel } from './BatchPanel'

interface Props {
  photo: PhotoDetail
  visiblePhotoIds: string[]
  batchSelectedIds: string[]
  catalogPhotos: PhotoSummary[]
  batchOpen: boolean
  onBatchOpen: (open: boolean) => void
  selectedVersionId: string | null
  onSelectVersion: (id: string) => void
  onBeforeRun: () => Promise<boolean>
  onRefresh: () => Promise<void>
  onReviewNext: () => Promise<void>
  active: boolean
}

export function EditPanel({ photo, visiblePhotoIds, batchSelectedIds, catalogPhotos, batchOpen, onBatchOpen, selectedVersionId, onSelectVersion, onBeforeRun, onRefresh, onReviewNext, active }: Props) {
  const [engine, setEngine] = useState<'DETERMINISTIC' | 'GENERATIVE'>('DETERMINISTIC')
  const [scope, setScope] = useState<'CURRENT' | 'VISIBLE' | 'SELECTED'>('CURRENT')
  const [preview, setPreview] = useState<EditPreview | null>(null)
  const [authorized, setAuthorized] = useState(false)
  const [budget, setBudget] = useState('0.10')
  const [retryOverride, setRetryOverride] = useState(false)
  const [replaceApproved, setReplaceApproved] = useState(false)
  const [maskId, setMaskId] = useState<string | null>(null)
  const [jobs, setJobs] = useState<EditJob[]>([])
  const [batchId, setBatchId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const submitting = useRef(false)
  const selectedIds = scope === 'CURRENT' ? [photo.id] : scope === 'SELECTED' ? batchSelectedIds.slice(0, 20) : visiblePhotoIds.slice(0, 20)
  const selected = photo.versions.find((version) => version.id === selectedVersionId)
  const hasApproved = photo.versions.some((version) => version.review_status === 'APPROVED')
  const estimatedCost = Number(preview?.estimated_cost_usd)
  const budgetAmount = Number(budget)
  const budgetReady = budget !== '' && Number.isFinite(budgetAmount) &&
    Number.isFinite(estimatedCost) && estimatedCost > 0 && budgetAmount >= estimatedCost
  const runBlocker = busy ? 'Finishing the current action.'
    : !selectedIds.length ? 'Select photos in the contact sheet first.'
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
    setReplaceApproved(false)
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

  const previewRun = async () => {
    if (!(await onBeforeRun())) return
    setBusy(true)
    try {
      setPreview(await api.previewEdits(selectedIds, 'GENERATIVE', {}, maskId, retryOverride, replaceApproved))
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
      const result = await api.runEdits(ids, 'GENERATIVE', {}, Number(budget), retryOverride, maskId, replaceApproved)
      setJobs(result.jobs)
      setBatchId(result.jobs[0]?.batch_id || null)
      setMessage(`${result.jobs.length} job${result.jobs.length === 1 ? '' : 's'} queued. Review every returned version before publication.`)
      setAuthorized(false)
      setReplaceApproved(false)
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

  const review = async (decision: 'APPROVED' | 'REJECTED', next = false) => {
    if (!selected) return
    const reason = decision === 'REJECTED' ? window.prompt('Optional rejection reason', '') : ''
    if (reason === null) return
    setBusy(true)
    try {
      await api.reviewVersion(photo.id, selected.id, decision, reason || '',
        decision === 'APPROVED' && Boolean(selected.replacement_of_version_id))
      await onRefresh()
      setMessage(`Version ${selected.version_number} ${decision.toLowerCase()}.`)
      if (next) await onReviewNext()
    } catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }

  useEffect(() => {
    if (batchOpen || !active) return
    const listener = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || event.repeat || busy || !selected || selected.review_status !== 'PENDING') return
      if (event.target instanceof Element && event.target.closest('input, textarea, select, button, [contenteditable="true"]')) return
      if (event.key.toLowerCase() === 'a') { event.preventDefault(); void review('APPROVED', true) }
      if (event.key.toLowerCase() === 'r') { event.preventDefault(); void review('REJECTED', true) }
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [batchOpen, active, selected, busy, onReviewNext])

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

  const versionReview = <div className="version-review">
    <h4>Immutable versions</h4>
    {photo.versions.length > 0 ? <>
      <div className="version-list">{photo.versions.map((version) => <button type="button" key={version.id} className={version.id === selectedVersionId ? 'is-current' : ''} onClick={() => onSelectVersion(version.id)}>v{version.version_number} · {version.review_status}</button>)}</div>
      {selected && <div className="selected-version-actions">
        <a href={selected.image_url} download={`photo-edit-v${selected.version_number}.jpg`}>Download selected version</a>
        {selected.master_url && <a href={selected.master_url} download={`photo-edit-master-v${selected.version_number}.png`}>Download full-resolution master</a>}
        {selected.rejection_reason && <small>Rejection: {selected.rejection_reason}</small>}
        {selected.review_status === 'SUPERSEDED' && <small>Superseded by version {photo.versions.find((version) => version.id === selected.superseded_by_version_id)?.version_number ?? 'unknown'}.</small>}
        {selected.review_status === 'PENDING' && <div className="review-actions">
          <button type="button" className="button-secondary" disabled={busy} onClick={() => void review('REJECTED')}>Reject selected</button>
          <button type="button" className="button-primary" disabled={busy} onClick={() => void review('APPROVED')}>{selected.replacement_of_version_id ? 'Approve and replace current' : 'Approve selected'}</button>
          <button type="button" className="button-secondary" disabled={busy} onClick={() => void review('REJECTED', true)}>Reject and next (R)</button>
          <button type="button" className="button-primary" disabled={busy} onClick={() => void review('APPROVED', true)}>Approve and next (A)</button>
        </div>}
      </div>}
    </> : <small>No versions yet. A completed local or generative edit will appear here for review.</small>}
    {message && <p role="status">{message}</p>}
  </div>

  return <div className="panel-section edit-panel">
    <div className="edit-panel-header"><div className="section-heading"><div><p className="eyebrow">Controlled editing</p><h3>Editing and versions</h3></div><span className="phase-chip">Owner review</span></div><div className="edit-mode-tools"><button type="button" className="button-secondary" onClick={() => onBatchOpen(!batchOpen)}>{batchOpen ? 'Single photo' : `Batch selection (${batchSelectedIds.length})`}</button>{!batchOpen && <label className="operation-select"><span>Operation</span><select value={engine} onChange={(event) => { setEngine(event.target.value as typeof engine); setPreview(null); setAuthorized(false); setReplaceApproved(false); setMaskId(null) }}><option value="DETERMINISTIC">Local deterministic correction</option><option value="GENERATIVE">Generative image edit</option></select></label>}</div></div>
    {batchOpen && <BatchPanel photo={photo} selectedIds={batchSelectedIds} catalogPhotos={catalogPhotos} onBeforeRun={onBeforeRun} onRefresh={onRefresh} />}
    {!batchOpen && engine === 'DETERMINISTIC' && <LocalCorrectionPanel photo={photo} onBeforeRun={onBeforeRun} onRefresh={onRefresh} reviewArea={versionReview} />}
    {!batchOpen && engine === 'GENERATIVE' && <div className="edit-workbench">
      <section className="edit-control-column" aria-label="Generative edit controls">
        <p>Generative editing uses the immutable JPEG publication input, never the original shown on the left.</p>
        <label><span>Selection</span><select value={scope} onChange={(event) => { setScope(event.target.value as typeof scope); setPreview(null); setAuthorized(false) }}><option value="CURRENT">Current photo</option><option value="SELECTED">First 20 selected photos</option><option value="VISIBLE">First 20 visible photos</option></select></label>
        <p>Provider calls may cost money. Review the estimate and set a planning budget. The budget is an application gate, not an account spending limit.</p>
        <label><span>Run budget in USD</span><input type="number" min="0" step="0.01" value={budget} onChange={(event) => { setBudget(event.target.value); setAuthorized(false) }} /></label>
        {scope === 'CURRENT' && <><a href={`/api/photos/${photo.id}/publication-input`} target="_blank" rel="noreferrer">Open 1600px publication input for mask preparation</a><label><span>Optional transparent PNG mask</span><input type="file" accept="image/png" onChange={(event) => void uploadMask(event.target.files?.[0])} /></label>{maskId && <small>Mask selected: {maskId}</small>}</>}
        <button type="button" className="button-secondary" disabled={busy} onClick={() => void previewRun()}>Preview selected run ({selectedIds.length})</button>
        <label className="consent-row"><input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} /> I authorize this current paid run</label>
        <label className="consent-row"><input type="checkbox" checked={retryOverride} onChange={(event) => { setRetryOverride(event.target.checked); setPreview(null); setAuthorized(false) }} /> Explicitly retry an identical rejected attempt</label>
        {hasApproved && <label className="consent-row"><input type="checkbox" checked={replaceApproved} onChange={(event) => { setReplaceApproved(event.target.checked); setPreview(null); setAuthorized(false) }} /> Create replacements for approved photos in this selection</label>}
        <button type="button" className="button-primary" disabled={runBlocker !== null} aria-describedby="run-readiness" onClick={() => void run()}>Start authorized run</button>
        <small id="run-readiness" className="run-readiness" aria-live="polite">{runBlocker || 'Ready to start the selected run.'}</small>
        {jobs.length > 0 && <details open><summary>Job receipts ({jobs.length})</summary><ol>{jobs.map((job) => <li key={job.id}>{job.photo_id.slice(0, 8)} · {job.engine.toLowerCase()} · {job.status.toLowerCase()}{job.error ? ` · ${job.error}` : ''}{job.actual_cost_usd != null ? ` · ${job.actual_cost_usd} USD reported` : ''}{job.status === 'QUEUED' && <button type="button" className="text-button" onClick={() => void cancel(job.id)}>Cancel queued</button>}</li>)}</ol></details>}
      </section>
      <aside className="edit-preview-column" aria-label="Selected run preview">
        <div className="edit-column-heading"><span>Preview selected run</span><small>Eligibility, prompt and estimated cost</small></div>
        {preview ? <div className="edit-preview"><p>{preview.availability} · {preview.model || 'local'} · estimated {preview.estimated_cost_usd ?? 'unknown'} USD</p><small>{preview.cost_note}</small><details open><summary>Per-photo eligibility and prompts</summary><ol>{preview.items.map((item) => <li key={item.photo_id}>{item.photo_id.slice(0, 8)}: {item.eligible ? `prompt v${item.prompt_version}` : item.reason}{item.prompt_text && <pre>{item.prompt_text}</pre>}</li>)}</ol></details></div> : <div className="edit-preview-stage is-empty"><div className="preview-placeholder"><span aria-hidden="true">◇</span><strong>No run preview yet</strong><p>Choose the selection, then preview eligibility and cost here.</p></div></div>}
        {versionReview}
      </aside>
    </div>}
  </div>
}
