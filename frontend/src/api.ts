import type { AnalysisEstimate, AnalysisRun, CatalogSuggestion, CompiledPrompt, EditJob, EditPreview, ImageVersion, LocalJob, LocalRecommendation, LocalSettings, LocalBatchPreview, LocalBatchStatus, NamedLocalRecipe, PreparedPrompt, PromptBatchPreview, LocationPreview, Options, PhotoDetail, PhotoSummary, Preset, SavePayload, VisitedCity, RefinementEstimate, PromptRefinement } from './types'

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
  localRecommendation: (photoId: string, presetId?: string) => request<LocalRecommendation>(`/api/photos/${photoId}/local-recommendation${presetId ? `?preset_id=${encodeURIComponent(presetId)}` : ''}`),
  localPreview: async (photoId: string, settings: LocalSettings, signal?: AbortSignal): Promise<Blob> => {
    const response = await fetch(`/api/photos/${photoId}/local-preview`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings }), signal })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(typeof body.detail === 'string' ? body.detail : 'Local preview failed')
    }
    return response.blob()
  },
  runLocal: (photoId: string, settings: LocalSettings, expectedRevision: number, retryOverride: boolean, replaceApproved: boolean) => request<LocalJob>(`/api/photos/${photoId}/local-edits`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings, expected_revision: expectedRevision, retry_override: retryOverride, replace_approved: replaceApproved, request_key: crypto.randomUUID() }),
  }),
  localJobs: (photoId: string) => request<{ jobs: LocalJob[] }>(`/api/photos/${photoId}/local-edits`),
  localJob: (jobId: string) => request<LocalJob>(`/api/local/jobs/${jobId}`),
  namedLocalRecipes: () => request<NamedLocalRecipe[]>('/api/local/recipes'),
  saveNamedLocalRecipe: (name: string, settings: LocalSettings) => request<NamedLocalRecipe>('/api/local/recipes', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, settings }),
  }),
  previewLocalBatch: (photoIds: string[], recipeId: string | null, overrides: Record<string, LocalSettings>, retryOverride: boolean, replaceApproved: boolean) => request<LocalBatchPreview>('/api/local/batches/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ photo_ids: photoIds, recipe_id: recipeId, overrides, retry_override: retryOverride, replace_approved: replaceApproved }),
  }),
  runLocalBatch: (photoIds: string[], recipeId: string | null, overrides: Record<string, LocalSettings>, retryOverride: boolean, replaceApproved: boolean, previewSignature: string) => request<LocalBatchStatus>('/api/local/batches', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ photo_ids: photoIds, recipe_id: recipeId, overrides, retry_override: retryOverride, replace_approved: replaceApproved, preview_signature: previewSignature, request_key: crypto.randomUUID(), authorized: true }),
  }),
  localBatch: (id: string) => request<LocalBatchStatus>(`/api/local/batches/${id}`),
  recentLocalBatches: () => request<LocalBatchStatus[]>('/api/local/batches/recent'),
  cancelLocalBatch: (id: string) => request<LocalBatchStatus>(`/api/local/batches/${id}/cancel`, { method: 'POST' }),
  previewPromptBatch: (photoIds: string[], sharedInstruction: string) => request<PromptBatchPreview>('/api/prompt-batches/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ photo_ids: photoIds, shared_instruction: sharedInstruction }),
  }),
  compilePromptBatch: (photoIds: string[], sharedInstruction: string, signature: string, acknowledgedIds: string[]) => request<{ prompts: PreparedPrompt[] }>('/api/prompt-batches/compile', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ photo_ids: photoIds, shared_instruction: sharedInstruction, preview_signature: signature, acknowledged_ids: acknowledgedIds }),
  }),
  approvePromptBatch: (prompts: PreparedPrompt[]) => request<{ prompts: CompiledPrompt[] }>('/api/prompt-batches/approve', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected: Object.fromEntries(prompts.map((prompt) => [prompt.id, prompt.approval_hash])) }),
  }),
  previewExport: () => request<{ target: string; approved_count: number; items: { photo_id: string; version_id: string; width: number; height: number; sha256: string; location_included: boolean }[] }>('/api/export/preview'),
  recentExports: () => request<{ export_id: string; created_at: string; item_count: number; directory_path: string }[]>('/api/export/history'),
  createExport: () => request<{ export_id: string; directory: string; directory_path: string; manifest: string; cost_report: string; item_count: number }>('/api/export', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ authorized: true }),
  }),
  openExportFolder: (exportId: string) => request<{ opened: boolean }>(`/api/export/${exportId}/open-folder`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Local-Action': 'open-export-folder' }, body: '{}',
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
  estimateRefinement: (promptId: string) => request<RefinementEstimate>(`/api/prompts/${promptId}/refinement/estimate`, { method: 'POST' }),
  runRefinement: (promptId: string, budget: string) => request<PromptRefinement>(`/api/prompts/${promptId}/refinement/run`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ authorized: true, budget_usd: budget }),
  }),
  getRefinements: (photoId: string) => request<PromptRefinement[]>(`/api/photos/${photoId}/prompt-refinements`),
  adoptRefinement: (refinementId: string, compiledText: string) => request<CompiledPrompt>(`/api/prompt-refinements/${refinementId}/adopt`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ compiled_text: compiledText }),
  }),
  previewEdits: (photoIds: string[], engine: 'DETERMINISTIC' | 'GENERATIVE', settings: Record<string, number>, maskId: string | null, retryOverride: boolean, replaceApproved: boolean) => request<EditPreview>('/api/edit/preview', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds, engine, settings, mask_id: maskId, retry_override: retryOverride, replace_approved: replaceApproved }),
  }),
  runEdits: (photoIds: string[], engine: 'DETERMINISTIC' | 'GENERATIVE', settings: Record<string, number>, budget: number | null, retryOverride: boolean, maskId: string | null, replaceApproved: boolean) => request<{ jobs: EditJob[] }>('/api/edit/batches', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_ids: photoIds, engine, settings, authorized: true, budget_usd: budget,
      retry_override: retryOverride, replace_approved: replaceApproved, mask_id: maskId, request_key: crypto.randomUUID() }),
  }),
  getEdits: (photoId: string) => request<{ jobs: EditJob[]; versions: ImageVersion[] }>(`/api/photos/${photoId}/edits`),
  getEditBatch: (batchId: string) => request<{ jobs: EditJob[] }>(`/api/edit/batches/${batchId}`),
  cancelEditJob: (jobId: string) => request<EditJob>(`/api/edit/jobs/${jobId}/cancel`, { method: 'POST' }),
  reviewVersion: (photoId: string, versionId: string, decision: 'APPROVED' | 'REJECTED', reason: string, replaceApproved: boolean) => request<ImageVersion>(`/api/photos/${photoId}/versions/${versionId}/review`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision, reason, replace_approved: replaceApproved }),
  }),
  uploadMask: (photoId: string, file: File) => request<{ id: string; width: number; height: number }>(`/api/photos/${photoId}/masks`, {
    method: 'POST', headers: { 'Content-Type': 'image/png' }, body: file,
  }),
}
