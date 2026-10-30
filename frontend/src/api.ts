import type { Options, PhotoDetail, PhotoSummary, Preset, SavePayload } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    const error = new Error(body.detail || 'Request failed')
    Object.assign(error, { status: response.status })
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
}
