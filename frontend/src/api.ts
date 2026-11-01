import type { AnalysisEstimate, AnalysisRun, CatalogSuggestion, CompiledPrompt, EditJob, EditPreview, ImageVersion, LocationPreview, Options, PhotoDetail, PhotoSummary, Preset, SavePayload, VisitedCity } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    const detail = body.detail
    const message = typeof detail === 'string' ? detail : detail?.message || 'Request failed'
    const error = new Error(message)
    Object.assign(error, { status: response.status })
    if (detail?.conflicts) Object.assign(error, { conflicts: detail.conflicts })
    throw error
  }
  return response.json() as Promise<T>
}

export const api = {
  previewExport: () => request<{ target: string; approved_count: number; items: { photo_id: string; version_id: string; width: number; height: number; sha256: string; location_included: boolean }[] }>('/api/export/preview'),
  createExport: () => request<{ export_id: string; directory: string; manifest: string; cost_report: string; item_count: number }>('/api/export', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ authorized: true }),
  }),
  auditExport: () => request<{ referenced_files: number; missing: string[]; changed: string[]; source_issues: string[]; orphaned: string[]; invalid_manifests: string[]; invalid_cost_reports: string[] }>('/api/export/audit'),
  cities: () => request<VisitedCity[]>('/api/catalog/cities'),
  createCity: (payload: { city: string; country: string; latitude: number; longitude: number; radius_km: number }) => request<VisitedCity>('/api/catalog/cities', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }),
  updateCity: (id: string, payload: { city: string; country: string; latitude: number; longitude: number; radius_km: number }) => request<VisitedCity>(`/api/catalog/cities/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  }),
  deleteCity: (id: string) => request<{ deleted: boolean }>(`/api/catalog/cities/${id}`, { method: 'DELETE' }),
  modelStatus: () => request<{ state: string; file: string; downloaded: number; total: number; error: string; cached: boolean }>('/api/catalog/model-status'),
  suggestions: (id: string) => request<CatalogSuggestion[]>(`/api/photos/${id}/catalog-suggestions`),
  runPrefill: (ids: string[], offline: boolean) => request<{ results: CatalogSuggestion[] }>('/api/catalog/suggestions/run', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ photo_ids: ids, authorized: true, offline }),
  }),
  decideSuggestion: (id: string, fields: string[], expectedRevision: number, dismiss = false) => request<{ suggestion: CatalogSuggestion; photo: PhotoDetail }>(`/api/catalog/suggestions/${id}/decide`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ fields, expected_revision: expectedRevision, dismiss }),
  }),
  undoSuggestion: (id: string) => request<{ suggestion: CatalogSuggestion; photo: PhotoDetail }>(`/api/catalog/suggestions/${id}/undo`, { method: 'POST' }),
  locationPreview: (ids: string[], cityId: string) => request<LocationPreview>('/api/catalog/location/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ photo_ids: ids, city_id: cityId }),
  }),
  locationApply: (ids: string[], cityId: string, expectedRevisions: Record<string, number>) => request<LocationPreview>('/api/catalog/location/apply', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ photo_ids: ids, city_id: cityId, authorized: true, expected_revisions: expectedRevisions }),
  }),
  locationUndo: (id: string) => request<{ id: string; undone_count: number }>(`/api/catalog/location/batches/${id}/undo`, { method: 'POST' }),
  listPhotos: () => request<PhotoSummary[]>('/api/photos'),
  getPhoto: (id: string) => request<PhotoDetail>(`/api/photos/${id}`),
  getOptions: () => request<Options>('/api/options'),
  savePhoto: (id: string, payload: SavePayload) => request<PhotoDetail>(`/api/photos/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  savePreset: (preset: Preset) => request<Preset>(`/api/presets/${preset.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: preset.name, structured_instructions: preset.structured_instructions }),
  }),
  estimateAnalysis: (photoIds: string[]) => request<AnalysisEstimate>('/api/analysis/estimate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds }),
  }),
  runAnalysis: (photoIds: string[], authorized: boolean) => request<{ results: AnalysisRun[] }>('/api/analysis/run', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds, authorized }),
  }),
  compilePrompt: (photoId: string) => request<CompiledPrompt>(`/api/photos/${photoId}/prompts/compile`, { method: 'POST' }),
  revisePrompt: (promptId: string, compiledText: string) => request<CompiledPrompt>(`/api/prompts/${promptId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ compiled_text: compiledText }),
  }),
  approvePrompt: (promptId: string) => request<CompiledPrompt>(`/api/prompts/${promptId}/approve`, { method: 'POST' }),
  previewEdits: (photoIds: string[], engine: 'DETERMINISTIC' | 'GENERATIVE', settings: Record<string, number>, maskId: string | null, retryOverride: boolean) => request<EditPreview>('/api/edit/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds, engine, settings, mask_id: maskId, retry_override: retryOverride }),
  }),
  runEdits: (photoIds: string[], engine: 'DETERMINISTIC' | 'GENERATIVE', settings: Record<string, number>, budget: number | null, retryOverride: boolean, maskId: string | null) => request<{ jobs: EditJob[] }>('/api/edit/batches', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds, engine, settings, authorized: true, budget_usd: budget,
      retry_override: retryOverride, mask_id: maskId, request_key: crypto.randomUUID() }),
  }),
  getEdits: (photoId: string) => request<{ jobs: EditJob[]; versions: ImageVersion[] }>(`/api/photos/${photoId}/edits`),
  getEditBatch: (batchId: string) => request<{ jobs: EditJob[] }>(`/api/edit/batches/${batchId}`),
  cancelEditJob: (jobId: string) => request<EditJob>(`/api/edit/jobs/${jobId}/cancel`, { method: 'POST' }),
  reviewVersion: (photoId: string, versionId: string, decision: 'APPROVED' | 'REJECTED', reason: string) => request<ImageVersion>(`/api/photos/${photoId}/versions/${versionId}/review`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, reason }),
  }),
  uploadMask: (photoId: string, file: File) => request<{ id: string; width: number; height: number }>(`/api/photos/${photoId}/masks`, {
    method: 'POST', headers: { 'Content-Type': 'image/png' }, body: file,
  }),
}
