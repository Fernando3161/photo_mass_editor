import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { ContactSheet } from './components/ContactSheet'
import { Filmstrip } from './components/Filmstrip'
import { FilterBar, type Filters } from './components/FilterBar'
import { MetadataPanel } from './components/MetadataPanel'
import { PromptPanel } from './components/PromptPanel'
import { ReviewCanvas } from './components/ReviewCanvas'
import type { AnalysisEstimate, CompiledPrompt, Options, PhotoDetail, PhotoSummary, Preset, ReviewForm, ReviewState, SavePayload } from './types'
import './styles.css'

type SaveStatus = 'saved' | 'unsaved' | 'saving' | 'error' | 'recovered'

const emptyOptions: Options = { subjects: [], tags: [], presets: [] }
const defaultFilters: Filters = { query: '', state: 'ALL', subject: '', tag: '', city: '', date: '' }

function formFromPhoto(photo: PhotoDetail): ReviewForm {
  return {
    editorial_description: photo.editorial_description || '',
    city: photo.city || '',
    country: photo.country || '',
    primary_subject: photo.primary_subject || '',
    content_tags: photo.tags.filter((tag) => tag.kind === 'CONTENT').map((tag) => tag.display_name).join(', '),
    condition_tags: photo.tags.filter((tag) => tag.kind === 'CONDITION').map((tag) => tag.display_name).join(', '),
    preset_id: photo.draft.preset_id || '',
    ai_allowance: photo.draft.ai_allowance,
    ai_suggestion_editable: photo.draft.ai_suggestion_editable,
    user_instructions: photo.draft.user_instructions,
    approved_constraints: photo.draft.approved_constraints || '',
    semantic_change_consent: Boolean(photo.draft.semantic_change_consent),
    analysis_run_id: photo.draft.analysis_run_id || null,
    review_state: photo.review_state,
  }
}

function payloadFromForm(form: ReviewForm, revision: number): SavePayload {
  const tags = (value: string) => value.split(',').map((tag) => tag.trim()).filter(Boolean)
  return {
    expected_revision: revision,
    ...form,
    primary_subject: form.primary_subject.trim() || null,
    content_tags: tags(form.content_tags),
    condition_tags: tags(form.condition_tags),
    preset_id: form.preset_id || null,
  }
}

function recoveryKey(id: string) { return `photo-review-draft:${id}` }

export default function App() {
  const [photos, setPhotos] = useState<PhotoSummary[]>([])
  const [options, setOptions] = useState<Options>(emptyOptions)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [photo, setPhoto] = useState<PhotoDetail | null>(null)
  const [form, setForm] = useState<ReviewForm | null>(null)
  const [filters, setFilters] = useState<Filters>(defaultFilters)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved')
  const [error, setError] = useState('')
  const [gridOpen, setGridOpen] = useState(false)
  const [presetEdit, setPresetEdit] = useState<Preset | null>(null)
  const [loading, setLoading] = useState(true)
  const [analysisEstimate, setAnalysisEstimate] = useState<AnalysisEstimate | null>(null)
  const [analysisAuthorized, setAnalysisAuthorized] = useState(false)
  const [phase3Busy, setPhase3Busy] = useState(false)
  const [prompt, setPrompt] = useState<CompiledPrompt | null>(null)
  const [promptText, setPromptText] = useState('')
  const editGeneration = useRef(0)
  const formRef = useRef<ReviewForm | null>(null)
  const saveInFlight = useRef(false)

  useEffect(() => {
    Promise.all([api.listPhotos(), api.getOptions()])
      .then(([catalog, loadedOptions]) => {
        setPhotos(catalog)
        setOptions(loadedOptions)
        setSelectedId(catalog[0]?.id || null)
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedId) { setPhoto(null); setForm(null); return }
    let active = true
    api.getPhoto(selectedId).then((loaded) => {
      if (!active) return
      let nextForm = formFromPhoto(loaded)
      const recovered = localStorage.getItem(recoveryKey(loaded.id))
      if (recovered) {
        try {
          const parsed = JSON.parse(recovered) as { baseRevision: number; form: ReviewForm }
          if (parsed.baseRevision === loaded.revision) {
            nextForm = parsed.form
            setSaveStatus('recovered')
          } else {
            localStorage.removeItem(recoveryKey(loaded.id))
            setSaveStatus('saved')
          }
        } catch {
          localStorage.removeItem(recoveryKey(loaded.id))
        }
      } else {
        setSaveStatus('saved')
      }
      setPhoto(loaded)
      setForm(nextForm)
      const latestPrompt = loaded.prompt_history?.[0] || null
      setPrompt(latestPrompt)
      setPromptText(latestPrompt?.compiled_text || '')
      setAnalysisEstimate(null)
      setAnalysisAuthorized(false)
      formRef.current = nextForm
      editGeneration.current = 0
      setError('')
    }).catch((reason: Error) => setError(reason.message))
    return () => { active = false }
  }, [selectedId])

  const filtered = useMemo(() => photos.filter((item) => {
    const query = filters.query.toLowerCase()
    const haystack = [item.original_filename, item.primary_subject, item.city, item.country, ...item.tags.map((tag) => tag.display_name)].filter(Boolean).join(' ').toLowerCase()
    return (!query || haystack.includes(query))
      && (filters.state === 'ALL' || item.review_state === filters.state)
      && (!filters.subject || item.primary_subject === filters.subject)
      && (!filters.tag || item.tags.some((tag) => tag.display_name === filters.tag))
      && (!filters.city || item.city === filters.city)
      && (!filters.date || (item.capture_datetime_raw || '').startsWith(filters.date.replace('-', ':')))
  }), [filters, photos])

  const saveNow = useCallback(async (overrideState?: ReviewState): Promise<boolean> => {
    if (!photo || !form || (saveStatus === 'saved' && !overrideState)) return true
    if (saveInFlight.current) return false
    const nextForm = overrideState ? { ...form, review_state: overrideState } : form
    if (overrideState && overrideState !== form.review_state) {
      editGeneration.current += 1
      formRef.current = nextForm
      setForm(nextForm)
      localStorage.setItem(recoveryKey(photo.id), JSON.stringify({ baseRevision: photo.revision, form: nextForm }))
    }
    const savingGeneration = editGeneration.current
    saveInFlight.current = true
    setSaveStatus('saving')
    try {
      const saved = await api.savePhoto(photo.id, payloadFromForm(nextForm, photo.revision))
      setPhoto(saved)
      const latestPrompt = saved.prompt_history?.[0] || null
      setPrompt(latestPrompt)
      setPromptText(latestPrompt?.compiled_text || '')
      setPhotos((current) => current.map((item) => item.id === saved.id ? {
        ...item,
        city: saved.city,
        country: saved.country,
        primary_subject: saved.primary_subject,
        review_state: saved.review_state,
        revision: saved.revision,
        tags: saved.tags,
      } : item))
      if (editGeneration.current === savingGeneration) {
        const savedForm = formFromPhoto(saved)
        formRef.current = savedForm
        setForm(savedForm)
        localStorage.removeItem(recoveryKey(photo.id))
        setSaveStatus('saved')
      } else {
        const pending = formRef.current
        if (pending) localStorage.setItem(recoveryKey(photo.id), JSON.stringify({ baseRevision: saved.revision, form: pending }))
        setSaveStatus('unsaved')
      }
      setError('')
      return true
    } catch (reason) {
      setSaveStatus('error')
      setError(reason instanceof Error ? reason.message : 'Save failed')
      return false
    } finally {
      saveInFlight.current = false
    }
  }, [form, photo, saveStatus])

  useEffect(() => {
    if (!photo || !form || !['unsaved', 'recovered'].includes(saveStatus)) return
    const timer = window.setTimeout(() => { void saveNow() }, 700)
    return () => window.clearTimeout(timer)
  }, [form, photo, saveNow, saveStatus])

  const change = <K extends keyof ReviewForm>(key: K, value: ReviewForm[K]) => {
    if (!form || !photo) return
    const next = {
      ...form,
      [key]: value,
      review_state: key !== 'review_state' && form.review_state === 'UNREVIEWED' ? 'IN_PROGRESS' : form.review_state,
    }
    editGeneration.current += 1
    formRef.current = next
    setForm(next)
    setSaveStatus('unsaved')
    setError('')
    localStorage.setItem(recoveryKey(photo.id), JSON.stringify({ baseRevision: photo.revision, form: next }))
  }

  const replaceWithUnsavedForm = (next: ReviewForm) => {
    if (!photo) return
    editGeneration.current += 1
    formRef.current = next
    setForm(next)
    setSaveStatus('unsaved')
    setError('')
    localStorage.setItem(recoveryKey(photo.id), JSON.stringify({ baseRevision: photo.revision, form: next }))
  }

  const move = useCallback(async (delta: number, state?: ReviewState) => {
    if (!(await saveNow(state))) return
    const source = filtered.length ? filtered : photos
    const index = source.findIndex((item) => item.id === selectedId)
    if (index < 0 || !source.length) return
    const next = Math.min(source.length - 1, Math.max(0, index + delta))
    setSelectedId(source[next].id)
  }, [filtered, photos, saveNow, selectedId])

  const selectPhoto = useCallback(async (id: string) => {
    if (id === selectedId) return
    if (await saveNow()) setSelectedId(id)
  }, [saveNow, selectedId])

  const nextUnreviewed = useCallback(async () => {
    if (!(await saveNow())) return
    const index = photos.findIndex((item) => item.id === selectedId)
    const ordered = [...photos.slice(index + 1), ...photos.slice(0, Math.max(index + 1, 0))]
    const next = ordered.find((item) => item.review_state !== 'REVIEWED')
    if (next) setSelectedId(next.id)
  }, [photos, saveNow, selectedId])

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      if (event.key === 'ArrowLeft') { event.preventDefault(); void move(-1) }
      if (event.key === 'ArrowRight') { event.preventDefault(); void move(1) }
      if (event.key.toLowerCase() === 'g') setGridOpen(true)
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [move])

  const savePreset = async () => {
    if (!presetEdit) return
    try {
      const saved = await api.savePreset(presetEdit)
      setOptions((current) => ({ ...current, presets: current.presets.map((preset) => preset.id === saved.id ? saved : preset) }))
      if (form?.preset_id === saved.id) {
        setPrompt((current) => current ? { ...current, approved_for_job: 0, approved_at: null } : current)
        setPhoto((current) => current ? { ...current, prompt_history: current.prompt_history.map((item) => ({ ...item, approved_for_job: 0, approved_at: null })) } : current)
      }
      setPresetEdit(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Preset save failed')
    }
  }

  const estimateCurrentAnalysis = async () => {
    if (!photo) return
    setPhase3Busy(true)
    try {
      setAnalysisEstimate(await api.estimateAnalysis([photo.id]))
      setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Analysis estimate failed')
    } finally { setPhase3Busy(false) }
  }

  const runCurrentAnalysis = async () => {
    if (!photo || !form || !analysisAuthorized) return
    setPhase3Busy(true)
    try {
      const result = await api.runAnalysis([photo.id], true)
      const run = result.results[0]
      const mergeTags = (current: string, kind: 'CONTENT' | 'CONDITION') => {
        const values = [...current.split(',').map((value) => value.trim()).filter(Boolean),
          ...run.suggested_tags.filter((tag) => tag.kind === kind).map((tag) => tag.display_name)]
        return [...new Set(values)].join(', ')
      }
      replaceWithUnsavedForm({
        ...form,
        primary_subject: form.primary_subject || run.suggested_primary || '',
        content_tags: mergeTags(form.content_tags, 'CONTENT'),
        condition_tags: mergeTags(form.condition_tags, 'CONDITION'),
        ai_suggestion_editable: form.ai_suggestion_editable || run.suggested_edits,
        analysis_run_id: run.id,
      })
      setAnalysisAuthorized(false)
      setAnalysisEstimate(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Analysis failed')
    } finally { setPhase3Busy(false) }
  }

  const compilePrompt = async () => {
    if (!photo || !(await saveNow())) return
    setPhase3Busy(true)
    try {
      const compiled = await api.compilePrompt(photo.id)
      setPrompt(compiled)
      setPromptText(compiled.compiled_text)
      setPhoto((current) => current ? { ...current, prompt_history: [compiled, ...current.prompt_history] } : current)
      setError('')
    } catch (reason) {
      const conflicts = (reason as Error & { conflicts?: string[] }).conflicts
      setError(conflicts?.join(' · ') || (reason instanceof Error ? reason.message : 'Prompt compilation failed'))
    } finally { setPhase3Busy(false) }
  }

  const savePromptVersion = async () => {
    if (!prompt) return
    setPhase3Busy(true)
    try {
      const revised = await api.revisePrompt(prompt.id, promptText)
      setPrompt(revised)
      setPromptText(revised.compiled_text)
      setPhoto((current) => current ? { ...current, prompt_history: [revised, ...current.prompt_history] } : current)
      setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Prompt save failed') }
    finally { setPhase3Busy(false) }
  }

  const approveCurrentPrompt = async () => {
    if (!prompt) return
    setPhase3Busy(true)
    try {
      const approved = await api.approvePrompt(prompt.id)
      setPrompt(approved)
      setPhoto((current) => current ? { ...current, prompt_history: current.prompt_history.map((item) => item.id === approved.id ? approved : { ...item, approved_for_job: 0 }) } : current)
      setError('')
    } catch (reason) {
      const conflicts = (reason as Error & { conflicts?: string[] }).conflicts
      setError(conflicts?.join(' · ') || (reason instanceof Error ? reason.message : 'Prompt approval failed'))
    } finally { setPhase3Busy(false) }
  }

  const statusText = saveStatus === 'saved' ? 'All changes saved' : saveStatus === 'saving' ? 'Saving changes…' : saveStatus === 'error' ? 'Save failed — draft kept locally' : saveStatus === 'recovered' ? 'Unsaved draft recovered' : 'Unsaved changes'

  if (loading) return <main className="center-message"><span className="loader" /><p>Opening local catalog…</p></main>
  if (error && !photos.length) return <main className="center-message error-message"><h1>Catalog unavailable</h1><p>{error}</p></main>
  if (!photos.length) return <main className="center-message"><h1>No photos in this catalog</h1><p>Import photos with the Phase 1 catalog command, then reload this page.</p></main>

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">PM</span><div><strong>Photo Mass Editor</strong><small>Local review workstation</small></div></div>
        <div className={`save-status status-${saveStatus}`} role="status" aria-live="polite"><span aria-hidden="true" />{statusText}</div>
        <div className="top-actions"><button type="button" className="text-button" onClick={() => void nextUnreviewed()}>Next unreviewed</button><span>{filtered.findIndex((item) => item.id === selectedId) + 1 || '—'} / {filtered.length}</span><button type="button" className="icon-button" onClick={() => void move(-1)} aria-label="Previous photo">←</button><button type="button" className="icon-button" onClick={() => void move(1)} aria-label="Next photo">→</button></div>
      </header>
      <FilterBar filters={filters} onChange={setFilters} photos={photos} resultCount={filtered.length} onGrid={() => setGridOpen(true)} />
      <Filmstrip photos={filtered} selectedId={selectedId} onSelect={(id) => void selectPhoto(id)} />
      <main className="workspace">
        {photo && form ? <><ReviewCanvas photo={photo} /><MetadataPanel photo={photo} form={form} options={options} onChange={change} onSaveNext={() => void move(1)} onReviewNext={() => void move(1, 'REVIEWED')} onEditPreset={setPresetEdit} promptPanel={<PromptPanel estimate={analysisEstimate} analysisAuthorized={analysisAuthorized} busy={phase3Busy} prompt={prompt} promptText={promptText} promptHistory={photo.prompt_history || []} onEstimate={() => void estimateCurrentAnalysis()} onAuthorized={setAnalysisAuthorized} onRunAnalysis={() => void runCurrentAnalysis()} onCompile={() => void compilePrompt()} onPromptText={setPromptText} onSavePrompt={() => void savePromptVersion()} onApprovePrompt={() => void approveCurrentPrompt()} />} /></> : <div className="center-message"><p>Select a photo to begin.</p></div>}
      </main>
      <footer className="shortcut-bar"><span><kbd>←</kbd><kbd>→</kbd> Navigate</span><span><kbd>G</kbd> Contact sheet</span><span>Changes save automatically</span></footer>
      {gridOpen && <ContactSheet photos={filtered} onClose={() => setGridOpen(false)} onSelect={(id) => { void selectPhoto(id); setGridOpen(false) }} />}
      {presetEdit && <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="preset-title"><div className="preset-dialog"><p className="eyebrow">Draft configuration</p><h2 id="preset-title">Edit preset</h2><label><span>Name</span><input value={presetEdit.name} onChange={(event) => setPresetEdit({ ...presetEdit, name: event.target.value })} /></label><label><span>Transparent instructions</span><textarea rows={7} value={presetEdit.structured_instructions} onChange={(event) => setPresetEdit({ ...presetEdit, structured_instructions: event.target.value })} /></label><p>Preset wording is saved locally and versioned. It does not run an edit.</p><div className="dialog-actions"><button className="button-secondary" type="button" onClick={() => setPresetEdit(null)}>Cancel</button><button className="button-primary" type="button" onClick={() => void savePreset()}>Save preset</button></div></div></div>}
    </div>
  )
}
