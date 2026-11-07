import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import { ContactSheet } from './components/ContactSheet'
import { Filmstrip } from './components/Filmstrip'
import { FilterBar, type Filters } from './components/FilterBar'
import { MetadataPanel } from './components/MetadataPanel'
import { PromptPanel } from './components/PromptPanel'
import { EditPanel } from './components/EditPanel'
import { ReviewCanvas } from './components/ReviewCanvas'
import { CatalogPrefillPanel } from './components/CatalogPrefillPanel'
import { ExportPanel } from './components/ExportPanel'
import type { AnalysisEstimate, CatalogSuggestion, CompiledPrompt, Options, PhotoDetail, PhotoSummary, Preset, ReviewForm, ReviewState, SavePayload, RefinementEstimate, PromptRefinement, RulePreview } from './types'
import './styles.css'

type SaveStatus = 'saved' | 'unsaved' | 'saving' | 'error' | 'recovered'
type WorkspaceTab = 'details' | 'suggestions' | 'prompt' | 'editing' | 'export'

const emptyOptions: Options = { subjects: [], tags: [], presets: [], publication_profiles: [], cities: [], countries: [] }
const defaultFilters: Filters = { query: '', state: 'ALL', subject: '', tag: '', city: '', date: '' }
const workspaceTabs = [['details', 'Catalog and draft'], ['suggestions', 'Suggestions'], ['prompt', 'Analysis and prompt'], ['editing', 'Editing and versions'], ['export', 'Export']] as const

function formFromPhoto(photo: PhotoDetail): ReviewForm {
  return {
    editorial_description: photo.editorial_description || '',
    city: photo.city || '',
    country: photo.country || '',
    primary_subject: photo.primary_subject || '',
    content_tags: photo.tags.filter((tag) => tag.kind === 'CONTENT').map((tag) => tag.display_name).join(', '),
    condition_tags: photo.tags.filter((tag) => tag.kind === 'CONDITION').map((tag) => tag.display_name).join(', '),
    preset_id: photo.draft.preset_id || '',
    publication_profile_id: photo.draft.publication_profile_id || 'website-standard-v1',
    ai_allowance: photo.draft.ai_allowance,
    ai_suggestion_editable: photo.draft.ai_suggestion_editable,
    rule_suggestions_enabled: Boolean(photo.draft.rule_suggestions_enabled),
    rule_selected_ids: photo.draft.rule_selected_ids,
    rule_instructions_override: photo.draft.rule_instructions_override,
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

function provisionalForm(saved: ReviewForm, suggestion: CatalogSuggestion): ReviewForm {
  const mergeTags = (existing: string, proposed: string[]) => {
    const values = existing.split(',').map((tag) => tag.trim()).filter(Boolean)
    for (const tag of proposed) if (!values.some((value) => value.toLowerCase() === tag.toLowerCase())) values.push(tag)
    return values.join(', ')
  }
  return { ...saved,
    primary_subject: saved.primary_subject || suggestion.proposed.primary_subject,
    content_tags: mergeTags(saved.content_tags, suggestion.proposed.content_tags),
    condition_tags: mergeTags(saved.condition_tags, suggestion.proposed.condition_tags),
    editorial_description: saved.editorial_description || suggestion.proposed.editorial_description,
    preset_id: saved.preset_id || suggestion.proposed.preset_id,
    city: saved.city || suggestion.proposed.city,
    country: saved.country || suggestion.proposed.country,
  }
}

export default function App() {
  const [photos, setPhotos] = useState<PhotoSummary[]>([])
  const [options, setOptions] = useState<Options>(emptyOptions)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selectedIdRef = useRef<string | null>(null)
  selectedIdRef.current = selectedId
  const [photo, setPhoto] = useState<PhotoDetail | null>(null)
  const [form, setForm] = useState<ReviewForm | null>(null)
  const [filters, setFilters] = useState<Filters>(defaultFilters)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved')
  const [error, setError] = useState('')
  const [gridOpen, setGridOpen] = useState(false)
  const [batchSelectedIds, setBatchSelectedIds] = useState<string[]>([])
  const [batchOpen, setBatchOpen] = useState(false)
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('details')
  const [presetEdit, setPresetEdit] = useState<Preset | null>(null)
  const [loading, setLoading] = useState(true)
  const [analysisEstimate, setAnalysisEstimate] = useState<AnalysisEstimate | null>(null)
  const [analysisAuthorized, setAnalysisAuthorized] = useState(false)
  const [phase3Busy, setPhase3Busy] = useState(false)
  const [prompt, setPrompt] = useState<CompiledPrompt | null>(null)
  const [promptText, setPromptText] = useState('')
  const [provisional, setProvisional] = useState<{ suggestionId: string; form: ReviewForm; reason: string; localRecipe: string } | null>(null)
  const [preparedPreview, setPreparedPreview] = useState<RulePreview | null>(null)
  const [refinementEstimate, setRefinementEstimate] = useState<RefinementEstimate | null>(null)
  const [refinementAuthorized, setRefinementAuthorized] = useState(false)
  const [refinement, setRefinement] = useState<PromptRefinement | null>(null)
  const [refinementText, setRefinementText] = useState('')
  const [refinementHistory, setRefinementHistory] = useState<PromptRefinement[]>([])
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
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
      setSelectedVersionId(loaded.versions.find((item) => item.review_status === 'APPROVED')?.id || loaded.versions.at(-1)?.id || null)
      setForm(nextForm)
      setProvisional(null)
      setPreparedPreview(null)
      const latestPrompt = loaded.prompt_history?.[0] || null
      setPrompt(latestPrompt)
      setPromptText(latestPrompt?.compiled_text || '')
      setAnalysisEstimate(null)
      setAnalysisAuthorized(false)
      setRefinementEstimate(null)
      setRefinementAuthorized(false)
      setRefinement(null)
      setRefinementText('')
      void api.getRefinements(loaded.id).then((items) => {
        if (active) setRefinementHistory(items)
      }).catch(() => { if (active) setRefinementHistory([]) })
      formRef.current = nextForm
      editGeneration.current = 0
      setError('')
    }).catch((reason: Error) => setError(reason.message))
    return () => { active = false }
  }, [selectedId])

  const refreshCurrentPhoto = useCallback(async () => {
    if (!selectedId) return
    const loaded = await api.getPhoto(selectedId)
    setPhoto(loaded)
    setSelectedVersionId(loaded.versions.at(-1)?.id || null)
  }, [selectedId])

  const refreshCatalog = useCallback(async () => {
    const [catalog, loadedOptions] = await Promise.all([api.listPhotos(), api.getOptions()])
    setPhotos(catalog)
    setOptions(loadedOptions)
  }, [])

  const acceptCatalogPhoto = (updated: PhotoDetail) => {
    if (updated.id !== selectedIdRef.current) return
    setPhoto(updated)
    const next = formFromPhoto(updated)
    formRef.current = next
    setForm(next)
    setSaveStatus('saved')
    setProvisional(null)
    setPreparedPreview(null)
    localStorage.removeItem(recoveryKey(updated.id))
    const latestPrompt = updated.prompt_history?.[0] || null
    setPrompt(latestPrompt)
    setPromptText(latestPrompt?.compiled_text || '')
  }

  const filtered = useMemo(() => photos.filter((item) => {
    const query = filters.query.toLowerCase()
    const haystack = [item.original_filename, item.primary_subject, item.city, item.country, ...item.tags.map((tag) => tag.display_name), ...(item.suggested_search_terms || [])].filter(Boolean).join(' ').toLowerCase()
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
      void api.getOptions().then(setOptions).catch(() => {})
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
    if (provisional) {
      setPreparedPreview(null)
      setProvisional({ ...provisional, form: { ...provisional.form, [key]: value } })
      return
    }
    const next = {
      ...form,
      [key]: value,
      review_state: key !== 'review_state' && form.review_state === 'UNREVIEWED' ? 'IN_PROGRESS' : form.review_state,
    }
    setPreparedPreview(null)
    editGeneration.current += 1
    formRef.current = next
    setForm(next)
    setSaveStatus('unsaved')
    setError('')
    localStorage.setItem(recoveryKey(photo.id), JSON.stringify({ baseRevision: photo.revision, form: next }))
  }

  const showProvisional = (suggestion: CatalogSuggestion) => {
    if (!form || suggestion.photo_id !== photo?.id || suggestion.status !== 'PENDING') return
    setPreparedPreview(null)
    setProvisional({ suggestionId: suggestion.id, form: provisionalForm(form, suggestion),
      reason: suggestion.evidence.preset_reason || 'Suggested from visible content and conditions',
      localRecipe: suggestion.evidence.local_recipe || 'natural' })
    setWorkspaceTab('details')
  }

  useEffect(() => {
    const previewForm = provisional?.form || form
    if (!photo || !previewForm) return
    let active = true
    const timer = window.setTimeout(() => {
      void api.previewPrompt(photo.id, payloadFromForm(previewForm, photo.revision))
        .then((result) => { if (active) setPreparedPreview(result) })
        .catch((reason: Error) => { if (active) setPreparedPreview({ proposed_text: '', conflicts: [reason.message], unapproved: true,
          rule_instructions: '', rule_suggestions: { rules: [], selected_ids: [], constraints: '', config_version: 0 } }) })
    }, 250)
    return () => { active = false; window.clearTimeout(timer) }
  }, [provisional, form, photo])

  const acceptAndPrepare = async () => {
    if (!photo || !provisional) return
    try {
      const p = provisional.form
      const result = await api.decideSuggestion(provisional.suggestionId,
        ['primary_subject', 'content_tags', 'condition_tags', 'editorial_description', 'preset_id', 'city', 'country'],
        photo.revision, false, { primary_subject: p.primary_subject, content_tags: payloadFromForm(p, photo.revision).content_tags,
          condition_tags: payloadFromForm(p, photo.revision).condition_tags, editorial_description: p.editorial_description,
          preset_id: p.preset_id, city: p.city, country: p.country })
      acceptCatalogPhoto(result.photo)
      await refreshCatalog()
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Suggestion acceptance failed') }
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

  const refreshRules = () => {
    if (!form || provisional) return
    replaceWithUnsavedForm({ ...form, rule_selected_ids: null, rule_instructions_override: null })
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
      const target = event.target
      if (target instanceof Element && (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.closest('.workspace-tabs'))) return
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
      setRefinementEstimate(null)
      setRefinement(null)
      setRefinementText('')
      setPhoto((current) => current ? { ...current, prompt_history: current.prompt_history.some((item) => item.id === compiled.id) ? current.prompt_history : [compiled, ...current.prompt_history] } : current)
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
      setRefinementEstimate(null)
      setRefinement(null)
      setRefinementText('')
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

  const estimateCurrentRefinement = async () => {
    if (!prompt || promptText !== prompt.compiled_text || !(await saveNow())) return
    setPhase3Busy(true)
    try {
      setRefinementEstimate(await api.estimateRefinement(prompt.id))
      setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Refinement estimate failed') }
    finally { setPhase3Busy(false) }
  }

  const runCurrentRefinement = async () => {
    if (!prompt || !refinementEstimate || !refinementAuthorized || promptText !== prompt.compiled_text ||
        prompt.id !== refinementEstimate.prompt_id || !(await saveNow())) return
    setPhase3Busy(true)
    try {
      const proposal = await api.runRefinement(prompt.id, refinementEstimate.estimated_cost_usd)
      setRefinement(proposal)
      setRefinementText(proposal.adoption_text || proposal.proposed_text || '')
      setRefinementHistory((current) => [proposal, ...current])
      setRefinementAuthorized(false)
      setRefinementEstimate(null)
      setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Refinement failed') }
    finally { setPhase3Busy(false) }
  }

  const adoptCurrentRefinement = async () => {
    if (!refinement || !refinementText.trim()) return
    setPhase3Busy(true)
    try {
      const revised = await api.adoptRefinement(refinement.id, refinementText)
      setPrompt(revised)
      setPromptText(revised.compiled_text)
      setPhoto((current) => current ? { ...current, prompt_history: [revised, ...current.prompt_history] } : current)
      setRefinement(null)
      setRefinementText('')
      setError('')
    } catch (reason) {
      const conflicts = (reason as Error & { conflicts?: string[] }).conflicts
      setError(conflicts?.join(' · ') || (reason instanceof Error ? reason.message : 'Proposal could not be adopted'))
    }
    finally { setPhase3Busy(false) }
  }

  const reviewRefinement = (item: PromptRefinement) => {
    setRefinement(item)
    setRefinementText(item.adoption_text || item.proposed_text || '')
    setError('')
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
      <main className={`workspace ${workspaceTab === 'editing' ? 'is-editing' : ''}`}>
        {photo && form ? <>
          <ReviewCanvas photo={photo} version={photo.versions.find((item) => item.id === selectedVersionId) || null} />
          <section className="work-area" aria-label="Work and editing area">
            <nav className="workspace-tabs" role="tablist" aria-label="Work area sections" onKeyDown={(event) => {
              if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
              event.preventDefault()
              const index = workspaceTabs.findIndex(([key]) => key === workspaceTab)
              const next = workspaceTabs[(index + (event.key === 'ArrowRight' ? 1 : workspaceTabs.length - 1)) % workspaceTabs.length][0]
              setWorkspaceTab(next)
              document.getElementById(`tab-${next}`)?.focus()
            }}>
              {workspaceTabs.map(([key, label]) =>
                <button key={key} type="button" role="tab" id={`tab-${key}`} aria-controls={`pane-${key}`} aria-selected={workspaceTab === key} tabIndex={workspaceTab === key ? 0 : -1} className={workspaceTab === key ? 'is-active' : ''} onClick={() => setWorkspaceTab(key)}>{label}</button>
              )}
            </nav>
            <div className="work-pane work-pane-details" role="tabpanel" id="pane-details" aria-labelledby="tab-details" hidden={workspaceTab !== 'details'}>
              <MetadataPanel photo={photo} form={provisional?.form || form} options={options} onChange={change} onSaveNext={() => void move(1)} onReviewNext={() => void move(1, 'REVIEWED')} onEditPreset={setPresetEdit} provisional={Boolean(provisional)} presetReason={provisional?.reason} localRecipe={provisional?.localRecipe} onAcceptPrepare={() => void acceptAndPrepare()} onDiscard={() => { setProvisional(null); setPreparedPreview(null) }} preparedPreview={preparedPreview} onSavePreparedPrompt={() => void compilePrompt()} onRefreshRules={refreshRules} />
            </div>
            <div className="work-pane" role="tabpanel" id="pane-suggestions" aria-labelledby="tab-suggestions" hidden={workspaceTab !== 'suggestions'}>
              <CatalogPrefillPanel photo={photo} visiblePhotoIds={filtered.map((item) => item.id)} beforeMutation={() => saveNow()} onPhoto={acceptCatalogPhoto} onCatalogRefresh={refreshCatalog} onProvisional={showProvisional} />
            </div>
            <div className="work-pane" role="tabpanel" id="pane-prompt" aria-labelledby="tab-prompt" hidden={workspaceTab !== 'prompt'}>
              <PromptPanel estimate={analysisEstimate} analysisAuthorized={analysisAuthorized} busy={phase3Busy} prompt={prompt} promptText={promptText} promptHistory={photo.prompt_history || []} onEstimate={() => void estimateCurrentAnalysis()} onAuthorized={setAnalysisAuthorized} onRunAnalysis={() => void runCurrentAnalysis()} onCompile={() => void compilePrompt()} onPromptText={setPromptText} onSavePrompt={() => void savePromptVersion()} onApprovePrompt={() => void approveCurrentPrompt()} refinementEstimate={refinementEstimate} refinementAuthorized={refinementAuthorized} refinement={refinement} refinementText={refinementText} refinementHistory={refinementHistory} onEstimateRefinement={() => void estimateCurrentRefinement()} onRefinementAuthorized={setRefinementAuthorized} onRunRefinement={() => void runCurrentRefinement()} onRefinementText={setRefinementText} onReviewRefinement={reviewRefinement} onAdoptRefinement={() => void adoptCurrentRefinement()} />
            </div>
            <div className="work-pane work-pane-editing" role="tabpanel" id="pane-editing" aria-labelledby="tab-editing" hidden={workspaceTab !== 'editing'}>
              <EditPanel photo={photo} visiblePhotoIds={filtered.map((item) => item.id)} batchSelectedIds={batchSelectedIds} catalogPhotos={photos} batchOpen={batchOpen} onBatchOpen={setBatchOpen} selectedVersionId={selectedVersionId} onSelectVersion={setSelectedVersionId} onBeforeRun={() => saveNow()} onRefresh={refreshCurrentPhoto} onReviewNext={() => move(1)} active={workspaceTab === 'editing' && !gridOpen} />
            </div>
            <div className="work-pane" role="tabpanel" id="pane-export" aria-labelledby="tab-export" hidden={workspaceTab !== 'export'}>
              <ExportPanel />
            </div>
          </section>
        </> : <div className="center-message"><p>Select a photo to begin.</p></div>}
      </main>
      <footer className="shortcut-bar"><span><kbd>←</kbd><kbd>→</kbd> Navigate</span><span><kbd>G</kbd> Contact sheet</span><span>Changes save automatically</span></footer>
      {gridOpen && <ContactSheet photos={filtered} selectedIds={batchSelectedIds} onToggle={(id) => setBatchSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])} onSelectVisible={() => setBatchSelectedIds((current) => [...new Set([...current, ...filtered.map((item) => item.id)])])} onClearSelection={() => setBatchSelectedIds([])} onOpenBatch={() => { setGridOpen(false); setWorkspaceTab('editing'); setBatchOpen(true) }} onClose={() => setGridOpen(false)} onSelect={(id) => { void selectPhoto(id); setGridOpen(false) }} />}
      {presetEdit && <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="preset-title"><div className="preset-dialog"><p className="eyebrow">Draft configuration</p><h2 id="preset-title">Edit preset</h2><label><span>Name</span><input value={presetEdit.name} onChange={(event) => setPresetEdit({ ...presetEdit, name: event.target.value })} /></label><label><span>Transparent instructions</span><textarea rows={7} value={presetEdit.structured_instructions} onChange={(event) => setPresetEdit({ ...presetEdit, structured_instructions: event.target.value })} /></label><p>Preset wording is saved locally and versioned. It does not run an edit.</p><div className="dialog-actions"><button className="button-secondary" type="button" onClick={() => setPresetEdit(null)}>Cancel</button><button className="button-primary" type="button" onClick={() => void savePreset()}>Save preset</button></div></div></div>}
    </div>
  )
}
