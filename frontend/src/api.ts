import type { AnalysisEstimate, AnalysisRun, CompiledPrompt, Options, PhotoDetail, PhotoSummary, Preset, SavePayload } from './types'

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
}
