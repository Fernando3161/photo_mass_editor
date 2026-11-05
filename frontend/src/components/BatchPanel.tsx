import { useEffect, useState } from 'react'
import { api } from '../api'
import type { LocalBatchPreview, LocalBatchStatus, LocalSettings, NamedLocalRecipe, PhotoDetail, PhotoSummary, PreparedPrompt, PromptBatchPreview } from '../types'

interface Props {
  photo: PhotoDetail
  selectedIds: string[]
  catalogPhotos: PhotoSummary[]
  onBeforeRun: () => Promise<boolean>
  onRefresh: () => Promise<void>
}

const fineTuneControls: Array<[keyof LocalSettings, string, number, number, number]> = [
  ['levels_strength', 'Levels', 0, 1, .05], ['black_point', 'Black point', 0, .2, .005],
  ['white_point', 'White point', .8, 1, .005], ['red_gain', 'Red balance', .85, 1.15, .01],
  ['blue_gain', 'Blue balance', .85, 1.15, .01], ['shadow_lift', 'Shadows', 0, .4, .02],
  ['highlight_compression', 'Highlights', 0, .4, .02], ['denoise', 'Denoise', 0, 2, 1],
  ['sharpen', 'Sharpen', 0, 1, .05],
]

export function BatchPanel({ photo, selectedIds, catalogPhotos, onBeforeRun, onRefresh }: Props) {
  const [mode, setMode] = useState<'LOCAL' | 'PROMPTS'>('LOCAL')
  const [recipes, setRecipes] = useState<NamedLocalRecipe[]>([])
  const [recipeId, setRecipeId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [overrides, setOverrides] = useState<Record<string, LocalSettings>>({})
  const [localPreview, setLocalPreview] = useState<LocalBatchPreview | null>(null)
  const [previewValid, setPreviewValid] = useState(false)
  const [localAuthorized, setLocalAuthorized] = useState(false)
  const [batch, setBatch] = useState<LocalBatchStatus | null>(null)
  const [retryOverride, setRetryOverride] = useState(false)
  const [replaceApproved, setReplaceApproved] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [promptPreview, setPromptPreview] = useState<PromptBatchPreview | null>(null)
  const [acknowledged, setAcknowledged] = useState<string[]>([])
  const [prepared, setPrepared] = useState<PreparedPrompt[]>([])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const idsKey = selectedIds.join(',')

  useEffect(() => {
    void api.namedLocalRecipes().then(setRecipes).catch((error: Error) => setMessage(error.message))
    void api.recentLocalBatches().then((recent) => { if (recent.length) setBatch(recent[0]) }).catch((error: Error) => setMessage(error.message))
  }, [])
  useEffect(() => { setLocalPreview(null); setPreviewValid(false); setLocalAuthorized(false); setPromptPreview(null); setPrepared([]); setAcknowledged([]) }, [idsKey])
  useEffect(() => {
    if (!batch || batch.status !== 'RUNNING') return
    const timer = window.setInterval(() => {
      void api.localBatch(batch.id).then(async (updated) => {
        setBatch(updated)
        if (updated.status !== 'RUNNING') await onRefresh()
      }).catch((error: Error) => setMessage(error.message))
    }, 1200)
    return () => window.clearInterval(timer)
  }, [batch?.id, batch?.status, onRefresh])

  const guarded = async (action: () => Promise<void>) => {
    setBusy(true)
    try { setMessage(''); await action() }
    catch (error) { setMessage((error as Error).message) }
    finally { setBusy(false) }
  }
  const invalidate = () => { setPreviewValid(false); setLocalAuthorized(false); setPromptPreview(null); setPrepared([]); setAcknowledged([]) }
  const saveRecipe = () => void guarded(async () => {
    const recommendation = await api.localRecommendation(photo.id)
    const saved = await api.saveNamedLocalRecipe(name, recommendation.settings)
    setRecipes((current) => [...current, saved].sort((a, b) => a.name.localeCompare(b.name)))
    setRecipeId(saved.id)
    setName('')
    invalidate()
  })
  const previewLocal = () => void guarded(async () => {
    if (!(await onBeforeRun())) return
    setLocalPreview(await api.previewLocalBatch(selectedIds, recipeId, overrides, retryOverride, replaceApproved))
    setPreviewValid(true)
    setLocalAuthorized(false)
  })
  const runLocal = () => void guarded(async () => {
    if (!localPreview || !previewValid || !localAuthorized || !localPreview.eligible_count || !(await onBeforeRun())) return
    try {
      const result = await api.runLocalBatch(selectedIds, recipeId, overrides, retryOverride, replaceApproved, localPreview.signature)
      setBatch(result)
    } finally {
      setPreviewValid(false)
      setLocalAuthorized(false)
    }
  })
  const overrideRecommended = (id: string) => void guarded(async () => {
    const recommendation = await api.localRecommendation(id)
    setOverrides((current) => ({ ...current, [id]: recommendation.settings }))
    setPreviewValid(false)
    setLocalAuthorized(false)
  })
  const updateOverride = (id: string, base: LocalSettings, key: keyof LocalSettings, value: number) => {
    setOverrides((current) => ({ ...current, [id]: { ...(current[id] || base), [key]: value } }))
    setPreviewValid(false)
    setLocalAuthorized(false)
  }
  const previewPrompts = () => void guarded(async () => {
    if (!(await onBeforeRun())) return
    setPromptPreview(await api.previewPromptBatch(selectedIds, instruction))
    setPrepared([])
    setAcknowledged([])
  })
  const compilePrompts = () => void guarded(async () => {
    if (!promptPreview || !(await onBeforeRun())) return
    try {
      const result = await api.compilePromptBatch(selectedIds, instruction, promptPreview.signature, acknowledged)
      setPrepared(result.prompts)
      await onRefresh()
    } finally { setPromptPreview(null); setAcknowledged([]) }
  })
  const approvePrompts = () => void guarded(async () => {
    if (!prepared.length) return
    await api.approvePromptBatch(prepared)
    setPrepared([])
    setMessage('Selected prompts approved. A paid image run still needs its own preview and authorization.')
    await onRefresh()
  })
  const eligiblePrompts = promptPreview?.items.filter((item) => item.eligible) || []

  return <div className="batch-panel edit-workbench">
    <section className="edit-control-column" aria-label="Batch controls">
      <h4>Selected photos ({selectedIds.length})</h4>
      <small>Select photos in the contact sheet. Local processing creates pending versions; each requires visual review.</small>
      <label><span>Batch task</span><select value={mode} onChange={(event) => { setMode(event.target.value as typeof mode); setLocalAuthorized(false); setPreviewValid(false) }}><option value="LOCAL">Local corrections</option><option value="PROMPTS">Generative prompt preparation</option></select></label>
      {mode === 'LOCAL' ? <>
        <label><span>Recipe</span><select value={recipeId || ''} onChange={(event) => { setRecipeId(event.target.value || null); setLocalPreview(null); setOverrides({}); invalidate() }}><option value="">Each photo's recommendation</option>{recipes.map((recipe) => <option key={recipe.id} value={recipe.id}>{recipe.name}</option>)}</select></label>
        <label><span>Save current photo's recommendation as a named recipe</span><input value={name} maxLength={80} onChange={(event) => setName(event.target.value)} /></label>
        <button className="button-secondary" type="button" disabled={busy || !name.trim()} onClick={saveRecipe}>Save named recipe</button>
        <label className="consent-row"><input type="checkbox" checked={retryOverride} onChange={(event) => { setRetryOverride(event.target.checked); invalidate() }} /> Retry identical rejected recipes</label>
        <label className="consent-row"><input type="checkbox" checked={replaceApproved} onChange={(event) => { setReplaceApproved(event.target.checked); invalidate() }} /> Create replacements for approved photos</label>
        <button className="button-secondary" type="button" disabled={busy || !selectedIds.length} onClick={previewLocal}>Preview local batch</button>
        <label className="consent-row"><input type="checkbox" checked={localAuthorized} disabled={!previewValid} onChange={(event) => setLocalAuthorized(event.target.checked)} /> I authorize this local batch run</label>
        <button className="button-primary" type="button" disabled={busy || !previewValid || !localAuthorized || !localPreview?.eligible_count} onClick={runLocal}>Apply recipe to eligible selection</button>
        {batch?.status === 'RUNNING' && <button className="button-secondary" type="button" onClick={() => void guarded(async () => setBatch(await api.cancelLocalBatch(batch.id)))}>Cancel queued items</button>}
        {batch && <p role="status">Batch {batch.id.slice(0, 8)}: {batch.status.toLowerCase()} · {batch.jobs.filter((job) => job.status === 'SUCCEEDED').length} succeeded · {batch.jobs.filter((job) => job.status === 'FAILED').length} failed · {batch.jobs.filter((job) => job.status === 'CANCELLED').length} cancelled. Pending versions still need approval.</p>}
      </> : <>
        <label><span>Optional shared instruction</span><textarea rows={4} value={instruction} maxLength={2000} onChange={(event) => { setInstruction(event.target.value); setPromptPreview(null); setPrepared([]) }} /></label>
        <button className="button-secondary" type="button" disabled={busy || !selectedIds.length} onClick={previewPrompts}>Preview per-photo prompt diffs</button>
        <button className="button-secondary" type="button" disabled={busy || !eligiblePrompts.length || acknowledged.length !== eligiblePrompts.length} onClick={compilePrompts}>Compile acknowledged prompts</button>
        {prepared.length > 0 && <button className="button-primary" type="button" disabled={busy} onClick={approvePrompts}>Approve these {prepared.length} prompts</button>}
        <small>Prompt approval does not authorize an image edit, semantic change, or publication.</small>
      </>}
      {message && <p role="status">{message}</p>}
    </section>
    <aside className="edit-preview-column batch-results" aria-label="Batch preview">
      <div className="edit-column-heading"><span>Before-run summary</span><small>Review each photo before continuing</small></div>
      {mode === 'LOCAL' && localPreview && <div className="edit-preview">
        <p>{localPreview.eligible_count} eligible · {localPreview.items.length - localPreview.eligible_count} skipped {previewValid ? '' : '· preview changed, refresh required'}</p>
        <div className="batch-grid">{localPreview.items.map((item) => {
          const summary = catalogPhotos.find((candidate) => candidate.id === item.photo_id)
          const settings = item.settings
          return <div className="batch-card" key={item.photo_id}>
            {summary && <img src={summary.thumbnail_url} alt="" loading="lazy" />}
            <strong>{summary?.original_filename || item.photo_id.slice(0, 8)}</strong>
            <small>{item.eligible ? `${settings?.preset_id} · ${item.operations?.join(', ') || 'no change'} · ${item.output_targets?.join(' + ')}` : `Skipped: ${item.reason}`}</small>
            {item.eligible && settings && <div className="batch-item-actions">
              <button type="button" className="text-button" onClick={() => overrideRecommended(item.photo_id)}>Use recommendation</button>
              <label>Exposure override <input aria-label={`Exposure override ${item.photo_id}`} type="number" min={-1} max={1} step={0.05} value={overrides[item.photo_id]?.exposure_ev ?? settings.exposure_ev} onChange={(event) => updateOverride(item.photo_id, settings, 'exposure_ev', Number(event.target.value))} /></label>
              <details><summary>Fine tune this photo</summary><div className="batch-tune-grid">{fineTuneControls.map(([key, label, min, max, step]) => <label key={key}>{label}<input aria-label={`${label} override ${item.photo_id}`} type="number" min={min} max={max} step={step} value={overrides[item.photo_id]?.[key] as number ?? settings[key] as number} onChange={(event) => updateOverride(item.photo_id, settings, key, Number(event.target.value))} /></label>)}</div></details>
            </div>}
          </div>
        })}</div>
      </div>}
      {mode === 'LOCAL' && batch && <div className="edit-preview"><h4>Item receipts</h4><ol>{batch.jobs.map((job) => <li key={job.id}>{job.photo_id.slice(0, 8)} · {job.status.toLowerCase()}{job.error ? ` · ${job.error}` : ''}</li>)}</ol></div>}
      {mode === 'PROMPTS' && promptPreview && <div className="edit-preview"><ol>{promptPreview.items.map((item) => <li key={item.photo_id}><strong>{item.photo_id.slice(0, 8)}</strong> · {item.eligible ? `profile ${item.profile_id}, allowance ${item.allowance}, semantic consent ${item.semantic_change_consent ? 'yes' : 'no'}` : `Skipped: ${item.reason}`}{item.eligible && <><details><summary>Previous and proposed prompt</summary><h4>Previous</h4><pre>{item.previous_text || 'No prior prompt'}</pre><h4>Proposed</h4><pre>{item.proposed_text}</pre></details><label className="consent-row"><input type="checkbox" checked={acknowledged.includes(item.photo_id)} onChange={(event) => setAcknowledged((current) => event.target.checked ? [...current, item.photo_id] : current.filter((id) => id !== item.photo_id))} /> I reviewed this photo's prompt diff</label></>}</li>)}</ol></div>}
      {mode === 'PROMPTS' && prepared.length > 0 && <div className="edit-preview"><h4>Compiled versions awaiting approval</h4><ol>{prepared.map((prompt) => <li key={prompt.id}>{prompt.photo_id.slice(0, 8)} · v{prompt.version_number}<pre>{prompt.compiled_text}</pre></li>)}</ol></div>}
    </aside>
  </div>
}
