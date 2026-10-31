import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import type { PhotoDetail, PhotoSummary } from '../types'

const summaries: PhotoSummary[] = [
  { id: 'one', original_filename: 'first.jpg', width: 1200, height: 800, capture_datetime_raw: '2024:01:01 10:00:00', camera: 'Test Camera', city: null, country: null, review_state: 'UNREVIEWED', revision: 0, primary_subject: null, thumbnail_url: '/api/photos/one/thumbnail', tags: [] },
  { id: 'two', original_filename: 'second.jpg', width: 800, height: 1200, capture_datetime_raw: '2024:01:02 11:00:00', camera: 'Test Camera', city: null, country: null, review_state: 'UNREVIEWED', revision: 0, primary_subject: null, thumbnail_url: '/api/photos/two/thumbnail', tags: [] },
]

const detail = (summary: PhotoSummary): PhotoDetail => ({
  ...summary,
  original_url: `/api/photos/${summary.id}/original`,
  editorial_description: '', lens: null, orientation: 1, capture_offset: null,
  gps_present: true, source_missing: 0, versions: [],
  draft: { preset_id: null, publication_profile_id: 'website-standard-v1', ai_allowance: 0, ai_suggestion_editable: '', user_instructions: '', approved_constraints: '', semantic_change_consent: 0, analysis_run_id: null, compiled_prompt_stale: 1, draft_revision: 0, saved_at: null },
  prompt_history: [],
})

function mockFetch(saveFails = false, saveGate?: Promise<void>) {
  let catalog = structuredClone(summaries)
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === '/api/photos' && !init) return Response.json(catalog)
    if (url === '/api/options') return Response.json({ subjects: [], tags: [], presets: [{ id: 'natural', version: 1, name: 'Natural', structured_instructions: 'Keep it natural', updated_at: 'now' }], publication_profiles: [{ id: 'website-standard-v1', version: 1, name: 'Website standard', image_format: 'JPEG', file_extension: '.jpg', mime: 'image/jpeg', max_long_edge: 1600, quality: 85, color_space: 'sRGB', preserve_aspect_ratio: 1, allow_upscale: 0, strip_metadata: 1 }] })
    if (url === '/api/photos/one/prompts/compile' && init?.method === 'POST') return Response.json({ id: 'prompt-1', photo_id: 'one', version_number: 1, parent_prompt_id: null, compiled_text: 'Preserve documentary authenticity.', user_modified: 0, approved_for_job: 0, generated_at: 'now', approved_at: null, input_snapshot: {}, publication_profile_id: 'website-standard-v1', publication_profile_snapshot: {} })
    if (url.startsWith('/api/photos/') && init?.method === 'PATCH') {
      if (saveGate) await saveGate
      if (saveFails) return Response.json({ detail: 'Database unavailable' }, { status: 500 })
      const id = url.split('/').pop()!
      const payload = JSON.parse(String(init.body))
      catalog = catalog.map((item) => item.id === id ? { ...item, ...payload, revision: item.revision + 1 } : item)
      const saved = catalog.find((item) => item.id === id)!
      return Response.json({ ...detail(saved), editorial_description: payload.editorial_description, city: payload.city, country: payload.country, primary_subject: payload.primary_subject, review_state: payload.review_state, revision: saved.revision, tags: [], draft: { ...detail(saved).draft, preset_id: payload.preset_id, publication_profile_id: payload.publication_profile_id, ai_allowance: payload.ai_allowance, ai_suggestion_editable: payload.ai_suggestion_editable, user_instructions: payload.user_instructions, approved_constraints: payload.approved_constraints, semantic_change_consent: payload.semantic_change_consent ? 1 : 0, analysis_run_id: payload.analysis_run_id, compiled_prompt_stale: 1, draft_revision: 1, saved_at: 'now' } })
    }
    if (url === '/api/photos/one') return Response.json(detail(catalog[0]))
    if (url === '/api/photos/two') return Response.json(detail(catalog[1]))
    throw new Error(`Unhandled request ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('review workstation', () => {
  beforeEach(() => vi.useRealTimers())
  afterEach(() => vi.unstubAllGlobals())

  it('navigates with the keyboard and exposes an explicit empty edited state', async () => {
    mockFetch()
    render(<App />)
    expect(await screen.findByText('first.jpg')).toBeTruthy()
    expect(screen.getByText('Not edited yet')).toBeTruthy()
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(await screen.findByText('second.jpg')).toBeTruthy()
  })

  it('auto-saves metadata and announces status without relying on color', async () => {
    mockFetch()
    const user = userEvent.setup()
    render(<App />)
    const description = await screen.findByLabelText('Description')
    await user.type(description, 'Quiet morning')
    expect(screen.getByRole('status').textContent).toContain('Unsaved changes')
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('All changes saved'), { timeout: 2500 })
    expect(localStorage.getItem('photo-review-draft:one')).toBeNull()
  })

  it('keeps a failed save locally and recovers it after reload', async () => {
    mockFetch(true)
    const user = userEvent.setup()
    const first = render(<App />)
    const description = await screen.findByLabelText('Description')
    await user.type(description, 'Recover this note')
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Save failed'), { timeout: 2500 })
    expect(localStorage.getItem('photo-review-draft:one')).toContain('Recover this note')
    first.unmount()
    mockFetch(false)
    render(<App />)
    expect(await screen.findByDisplayValue('Recover this note')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Unsaved draft recovered')
  })

  it('queues text entered while a save is in progress instead of losing it', async () => {
    let releaseSave!: () => void
    const saveGate = new Promise<void>((resolve) => { releaseSave = resolve })
    const fetchMock = mockFetch(false, saveGate)
    const user = userEvent.setup()
    render(<App />)
    const description = await screen.findByLabelText('Description')
    await user.type(description, 'A')
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Saving'), { timeout: 2500 })
    await user.type(description, 'B')
    releaseSave()
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('All changes saved'), { timeout: 3000 })
    const saves = fetchMock.mock.calls.filter(([, init]) => init?.method === 'PATCH')
    expect(saves.length).toBe(2)
    expect(JSON.parse(String(saves[1][1]?.body)).editorial_description).toBe('AB')
  })

  it('opens an accessible contact sheet for random access', async () => {
    mockFetch()
    render(<App />)
    await screen.findByText('first.jpg')
    await userEvent.click(screen.getByRole('button', { name: 'Open grid' }))
    const dialog = screen.getByRole('dialog', { name: 'Contact sheet' })
    expect(dialog).toBeTruthy()
    await userEvent.click(within(dialog).getByRole('button', { name: /second.jpg/i }))
    expect(await screen.findByText('second.jpg')).toBeTruthy()
  })

  it('compiles an inspectable prompt preview after the draft is saved', async () => {
    mockFetch()
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText('My additional instructions'), 'Preserve texture')
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain('All changes saved'), { timeout: 2500 })
    await user.click(screen.getByRole('button', { name: 'Compile prompt preview' }))
    expect(await screen.findByDisplayValue('Preserve documentary authenticity.')).toBeTruthy()
    expect(screen.getByText('Version 1 · Pending approval')).toBeTruthy()
  })

  it('shows the exact publication profile used for future AI editing', async () => {
    mockFetch()
    render(<App />)
    expect((await screen.findByLabelText('Publication profile') as HTMLSelectElement).value).toBe('website-standard-v1')
    expect(screen.getByText(/JPEG · max long edge 1600px · quality 85/)).toBeTruthy()
    expect(screen.getByText(/never the original/)).toBeTruthy()
  })
})
