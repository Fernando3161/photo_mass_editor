import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { CatalogSuggestion, LocationPreview, PhotoDetail, VisitedCity } from '../types'

const suggestedFields = ['primary_subject', 'content_tags', 'condition_tags', 'editorial_description', 'preset_id', 'city', 'country']

interface Props {
  photo: PhotoDetail
  visiblePhotoIds: string[]
  beforeMutation: () => Promise<boolean>
  onPhoto: (photo: PhotoDetail) => void
  onCatalogRefresh: () => Promise<void>
  onProvisional?: (suggestion: CatalogSuggestion) => void
}

export function CatalogPrefillPanel({ photo, visiblePhotoIds, beforeMutation, onPhoto, onCatalogRefresh, onProvisional }: Props) {
  const currentPhotoId = useRef(photo.id)
  currentPhotoId.current = photo.id
  const [cities, setCities] = useState<VisitedCity[]>([])
  const [suggestions, setSuggestions] = useState<CatalogSuggestion[]>([])
  const [selectedFields, setSelectedFields] = useState<string[]>(suggestedFields)
  const [cityId, setCityId] = useState('')
  const [city, setCity] = useState('')
  const [country, setCountry] = useState('')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [radius, setRadius] = useState('25')
  const [authorized, setAuthorized] = useState(false)
  const [offline, setOffline] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<LocationPreview | null>(null)
  const [batchId, setBatchId] = useState('')
  const [runResults, setRunResults] = useState<CatalogSuggestion[]>([])
  const [bulkAccepted, setBulkAccepted] = useState<string[]>([])

  useEffect(() => { void api.cities().then(setCities).catch((e: Error) => setError(e.message)) }, [])
  useEffect(() => {
    let active = true
    setSuggestions([])
    void api.suggestions(photo.id).then((items) => { if (active) setSuggestions(items) }).catch((e: Error) => { if (active) setError(e.message) })
    return () => { active = false }
  }, [photo.id])
  useEffect(() => {
    if (!busy) return
    const timer = window.setInterval(() => {
      void api.modelStatus().then((item) => setStatus(item.state === 'downloading'
        ? `Downloading ${item.file}: ${item.total ? Math.round(item.downloaded / item.total * 100) + '%' : `${Math.round(item.downloaded / 1048576)} MB`}`
        : item.state)).catch(() => {})
    }, 1000)
    return () => window.clearInterval(timer)
  }, [busy])

  async function guarded(action: () => Promise<void>) {
    setBusy(true); setError('')
    try { await action() } catch (reason) { setError(reason instanceof Error ? reason.message : 'Catalog action failed') }
    finally { setBusy(false) }
  }

  async function refresh() {
    const items = await api.suggestions(currentPhotoId.current)
    setSuggestions(items)
    await onCatalogRefresh()
  }

  async function run(ids: string[]) {
    await guarded(async () => {
      if (!await beforeMutation()) throw new Error('Save the current draft first')
      const result = await api.runPrefill(ids, offline)
      setRunResults(result.results)
      const current = result.results.find((item) => item.photo_id === photo.id)
      if (ids.length === 1 && current) onProvisional?.(current)
      setAuthorized(false)
      await refresh()
      setStatus(`${result.results.length} local suggestion(s) prepared`)
    })
  }

  async function decide(item: CatalogSuggestion, dismiss = false) {
    await guarded(async () => {
      if (!await beforeMutation()) throw new Error('Save the current draft first')
      const current = await api.getPhoto(photo.id)
      const result = await api.decideSuggestion(item.id, dismiss ? [] : selectedFields, current.revision, dismiss)
      onPhoto(result.photo)
      await refresh()
      setStatus(dismiss ? 'Suggestion dismissed' : 'Selected empty fields accepted')
    })
  }

  async function undo(item: CatalogSuggestion) {
    await guarded(async () => {
      if (!await beforeMutation()) throw new Error('Save the current draft first')
      const result = await api.undoSuggestion(item.id)
      onPhoto(result.photo)
      await refresh()
      setStatus('Suggestion undone')
    })
  }

  async function acceptPreparedBatch() {
    await guarded(async () => {
      if (!await beforeMutation()) throw new Error('Save the current draft first')
      const accepted: string[] = []
      try {
        for (const item of runResults.filter((result) => result.status === 'PENDING')) {
          const current = await api.getPhoto(item.photo_id)
          const result = await api.decideSuggestion(item.id, selectedFields, current.revision)
          if (result.suggestion.status === 'ACCEPTED') accepted.push(item.id)
          if (item.photo_id === photo.id) onPhoto(result.photo)
        }
      } finally {
        setBulkAccepted(accepted)
        await refresh()
      }
      setRunResults([])
      setStatus(`${accepted.length} prepared suggestions accepted. Each can be undone.`)
    })
  }

  async function undoPreparedBatch() {
    await guarded(async () => {
      let undone = 0
      try {
        for (const id of bulkAccepted) {
          const result = await api.undoSuggestion(id)
          if (result.photo.id === photo.id) onPhoto(result.photo)
          undone += 1
        }
      } finally {
        setBulkAccepted(bulkAccepted.slice(undone))
        await refresh()
      }
      setStatus(`${undone} batch acceptances undone`)
    })
  }

  async function addCity() {
    await guarded(async () => {
      const result = await api.createCity({ city, country, latitude: Number(latitude), longitude: Number(longitude), radius_km: Number(radius) })
      setCities(await api.cities()); setCityId(result.id)
      setCity(''); setCountry(''); setLatitude(''); setLongitude('')
      setStatus('Visited city saved privately')
    })
  }

  async function updateSelectedCity() {
    await guarded(async () => {
      await api.updateCity(cityId, { city, country, latitude: Number(latitude), longitude: Number(longitude), radius_km: Number(radius) })
      setCities(await api.cities())
      setStatus('Visited city updated; prior GPS suggestions must be rerun')
    })
  }

  async function removeSelectedCity() {
    await guarded(async () => {
      await api.deleteCity(cityId)
      setCities(await api.cities()); setCityId(''); setPreview(null)
      setStatus('Visited city removed; prior GPS suggestions must be rerun')
    })
  }

  async function previewLocation() {
    await guarded(async () => {
      if (!await beforeMutation()) throw new Error('Save the current draft first')
      setPreview(await api.locationPreview(visiblePhotoIds.slice(0, 20), cityId))
    })
  }

  async function applyLocation() {
    await guarded(async () => {
      const result = await api.locationApply(preview!.items.map((item) => item.photo_id), cityId, Object.fromEntries(preview!.items.map((item) => [item.photo_id, item.revision])))
      setBatchId(result.id || '')
      setPreview(null)
      await refresh()
      onPhoto(await api.getPhoto(photo.id))
      setStatus(`${result.applied_count} empty locations assigned`)
    })
  }

  return <details className="panel-section catalog-prefill">
    <summary><span>Catalog suggestions</span><small>Local only</small></summary>
    <p>Recognition uses a local model on verified thumbnails. Scores are relative. Review every suggestion before accepting it.</p>
    <label className="consent-row"><input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} /> Authorize this local recognition run</label>
    <label className="consent-row"><input type="checkbox" checked={offline} onChange={(event) => setOffline(event.target.checked)} /> Offline: use verified cached model only</label>
    <div className="dialog-actions">
      <button type="button" className="button-secondary" disabled={busy || !authorized} onClick={() => void run([photo.id])}>Suggest current photo</button>
      <button type="button" className="button-secondary" disabled={busy || !authorized || !visiblePhotoIds.length} onClick={() => void run(visiblePhotoIds.slice(0, 20))}>Suggest first {Math.min(visiblePhotoIds.length, 20)} visible</button>
    </div>
    {runResults.length > 1 && <div className="prefill-card"><p>Review these {runResults.length} prepared suggestions before bulk acceptance. Only empty scalar fields and new tags are applied.</p><div className="prefill-table-wrap"><table><thead><tr><th>Photo</th><th>Subject</th><th>Content</th><th>Conditions</th><th>Preset</th><th>Uncertain</th></tr></thead><tbody>{runResults.map((item) => <tr key={item.id}><td>{item.original_filename || item.photo_id}</td><td>{item.proposed.primary_subject || '—'}</td><td>{item.proposed.content_tags.join(', ') || '—'}</td><td>{item.proposed.condition_tags.join(', ') || '—'}</td><td>{item.proposed.preset_id}</td><td>{!item.proposed.primary_subject ? 'Subject' : item.evidence.subject_margin != null && item.evidence.subject_margin < .45 ? 'Close subject scores' : '—'}</td></tr>)}</tbody></table></div><button type="button" className="button-primary" disabled={busy || !selectedFields.length || !runResults.some((item) => item.status === 'PENDING')} onClick={() => void acceptPreparedBatch()}>Accept selected fields in prepared batch</button></div>}
    {bulkAccepted.length > 0 && <button type="button" className="button-secondary" disabled={busy} onClick={() => void undoPreparedBatch()}>Undo {bulkAccepted.length} batch acceptances</button>}
    {suggestions.map((item) => <div className="prefill-card" key={item.id}>
      <small>{item.status} · {item.model_id} · {item.created_at}</small>
      <p><strong>Subject:</strong> {item.proposed.primary_subject || 'Uncertain'} · <strong>Tags:</strong> {[...item.proposed.content_tags, ...item.proposed.condition_tags].join(', ') || 'None'}</p>
      <p><strong>Description:</strong> {item.proposed.editorial_description || 'Uncertain'} · <strong>Preset:</strong> {item.proposed.preset_id}</p>
      {item.evidence.preset_reason && <p><small>{item.evidence.preset_reason}. Local correction recipe: {item.evidence.local_recipe}.</small></p>}
      <p><strong>GPS match:</strong> {item.evidence.location.status}{item.evidence.location.status === 'MATCH' ? ` · ${item.proposed.city}, ${item.proposed.country} · ${item.evidence.location.distance_km} km` : ''}</p>
      <small>Top matches: {item.evidence.top_labels.slice(0, 3).map((entry) => `${entry.label} (${entry.similarity})`).join(' · ')}</small>
      {item.status === 'PENDING' && <><div className="prefill-fields">{suggestedFields.map((field) => <label key={field}><input type="checkbox" checked={selectedFields.includes(field)} onChange={(event) => setSelectedFields(event.target.checked ? [...selectedFields, field] : selectedFields.filter((value) => value !== field))} /> {field.replaceAll('_', ' ')}</label>)}</div><div className="dialog-actions"><button type="button" className="button-primary" disabled={busy} onClick={() => onProvisional?.(item)}>Review in catalog</button><button type="button" className="button-secondary" disabled={busy || !selectedFields.length} onClick={() => void decide(item)}>Accept selected empty fields</button><button type="button" className="button-secondary" disabled={busy} onClick={() => void decide(item, true)}>Dismiss</button></div></>}
      {item.status === 'ACCEPTED' && <button type="button" className="button-secondary" disabled={busy} onClick={() => void undo(item)}>Undo acceptance</button>}
    </div>)}
    <h4>Private visited cities</h4>
    <p>Enter a city center and radius once. Coordinates stay on the server.</p>
    <div className="form-grid"><label><span>City</span><input value={city} onChange={(e) => setCity(e.target.value)} /></label><label><span>Country</span><input value={country} onChange={(e) => setCountry(e.target.value)} /></label><label><span>Latitude</span><input type="number" step="any" value={latitude} onChange={(e) => setLatitude(e.target.value)} /></label><label><span>Longitude</span><input type="number" step="any" value={longitude} onChange={(e) => setLongitude(e.target.value)} /></label><label><span>Radius km</span><input type="number" min="0.1" max="200" step="0.1" value={radius} onChange={(e) => setRadius(e.target.value)} /></label></div>
    <button type="button" className="button-secondary" disabled={busy || !city.trim() || !country.trim() || !latitude || !longitude || Number(radius) <= 0} onClick={() => void addCity()}>Add visited city</button>
    {cityId && <p>To correct the selected city, enter its name, country, coordinates, and radius above again, then update it. Saved coordinates are never returned to the browser.</p>}
    <label><span>Bulk location for empty fields</span><select value={cityId} onChange={(e) => { setCityId(e.target.value); setPreview(null) }}><option value="">Choose a visited city</option>{cities.map((item) => <option key={item.id} value={item.id}>{item.city}, {item.country} ({item.radius_km} km)</option>)}</select></label>
    {cityId && <div className="dialog-actions"><button type="button" className="button-secondary" disabled={busy || !city.trim() || !country.trim() || !latitude || !longitude || Number(radius) <= 0} onClick={() => void updateSelectedCity()}>Update selected city</button><button type="button" className="button-secondary" disabled={busy} onClick={() => void removeSelectedCity()}>Remove selected city</button></div>}
    <button type="button" className="button-secondary" disabled={busy || !cityId || !visiblePhotoIds.length} onClick={() => void previewLocation()}>Preview first {Math.min(visiblePhotoIds.length, 20)} visible</button>
    {preview && <div className="prefill-card"><p>{preview.city}, {preview.country}: {preview.items.filter((item) => item.eligible).length} eligible of {preview.items.length}. Existing locations are skipped.</p><button type="button" className="button-primary" disabled={busy || !preview.items.some((item) => item.eligible)} onClick={() => void applyLocation()}>Apply previewed locations</button></div>}
    {batchId && <button type="button" className="button-secondary" disabled={busy} onClick={() => void guarded(async () => { const result = await api.locationUndo(batchId); setBatchId(''); await refresh(); onPhoto(await api.getPhoto(photo.id)); setStatus(`${result.undone_count} locations undone`) })}>Undo last bulk assignment</button>}
    {status && <p role="status">{status}</p>}
    {error && <p className="error-message" role="alert">{error}</p>}
  </details>
}
