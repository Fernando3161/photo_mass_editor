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

function mockFetch(saveFails = false, saveGate?: Promise<void>, edit?: { preview?: Record<string, unknown>; batchGate?: Promise<void> }) {
  let catalog = structuredClone(summaries)
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === '/api/photos' && !init) return Response.json(catalog)
    if (url === '/api/options') return Response.json({ subjects: [], tags: [], presets: [{ id: 'natural', version: 1, name: 'Natural', structured_instructions: 'Keep it natural', updated_at: 'now' }], publication_profiles: [{ id: 'website-standard-v1', version: 1, name: 'Website standard', image_format: 'JPEG', file_extension: '.jpg', mime: 'image/jpeg', max_long_edge: 1600, quality: 85, color_space: 'sRGB', preserve_aspect_ratio: 1, allow_upscale: 0, strip_metadata: 1 }] })
    if (url.endsWith('/edits')) return Response.json({ jobs: [], versions: [] })
    if (url === '/api/photos/one/prompts/compile' && init?.method === 'POST') return Response.json({ id: 'prompt-1', photo_id: 'one', version_number: 1, parent_prompt_id: null, compiled_text: 'Preserve documentary authenticity.', user_modified: 0, approved_for_job: 0, generated_at: 'now', approved_at: null, input_snapshot: {}, publication_profile_id: 'website-standard-v1', publication_profile_snapshot: {} })
    if (url === '/api/edit/preview' && init?.method === 'POST') return Response.json(edit?.preview || { items: [{ photo_id: 'one', eligible: true, prompt_version: 1, prompt_text: 'Preserve documentary authenticity.' }], engine: 'DETERMINISTIC', model: null, estimated_cost_usd: '0', cost_note: 'Local', availability: 'ready' })
    if (url === '/api/edit/batches' && init?.method === 'POST') {
      if (edit?.batchGate) await edit.batchGate
      return Response.json({ jobs: [{ id: 'job-one', batch_id: 'batch-one', photo_id: 'one', compiled_prompt_id: 'prompt-one', engine: 'DETERMINISTIC', model: null, status: 'QUEUED', error: null, image_version_id: null, estimated_cost_usd: 0, actual_cost_usd: 0, created_at: 'now', started_at: null, completed_at: null }] })
    }
    if (url === '/api/edit/batches/batch-one') return Response.json({ jobs: [{ id: 'job-one', batch_id: 'batch-one', photo_id: 'one', compiled_prompt_id: 'prompt-one', engine: 'DETERMINISTIC', model: null, status: 'SUCCEEDED', error: null, image_version_id: 'version-one', estimated_cost_usd: 0, actual_cost_usd: 0, created_at: 'now', started_at: 'now', completed_at: 'now' }] })
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
    expect(screen.getAllByText(/never the original/).length).toBeGreaterThan(0)
  })

  it('previews an edit and requires current-run authorization before queueing', async () => {
    const fetchMock = mockFetch()
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('first.jpg')
    const start = screen.getByRole('button', { name: 'Start authorized run' }) as HTMLButtonElement
    expect(start.disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: /Preview selected run/ }))
    expect(await screen.findByText(/prompt v1/)).toBeTruthy()
    expect(start.disabled).toBe(true)
    await user.click(screen.getByLabelText('I authorize this current local run'))
    expect(start.disabled).toBe(false)
    await user.click(start)
    await waitFor(() => expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/api/edit/batches' && JSON.parse(String(init?.body)).authorized === true)).toBe(true))
  })

  it('explains missing paid-run requirements and accepts only one submission while pending', async () => {
    let releaseBatch!: () => void
    const batchGate = new Promise<void>((resolve) => { releaseBatch = resolve })
    const fetchMock = mockFetch(false, undefined, { batchGate, preview: {
      items: [{ photo_id: 'one', eligible: true, prompt_version: 1, prompt_text: 'Remove visible people.' }],
      engine: 'GENERATIVE', model: 'gpt-image-2.5-sunburst', estimated_cost_usd: '1.00',
      cost_note: 'Planning estimate only', availability: 'ready',
    } })
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('first.jpg')
    await user.selectOptions(screen.getByLabelText('Operation'), 'GENERATIVE')
    const start = screen.getByRole('button', { name: 'Start authorized run' }) as HTMLButtonElement
    expect(start.disabled).toBe(true)
    expect(screen.getByText('Preview the selected run first.')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: /Preview selected run/ }))
    await screen.findByText(/prompt v1/)
    expect(start.disabled).toBe(true)
    expect(screen.getByText('Enter a budget of at least 1.00 USD using a decimal point.')).toBeTruthy()
    await user.type(screen.getByLabelText('Run budget in USD'), '0.10')
    expect(start.disabled).toBe(true)
    await user.clear(screen.getByLabelText('Run budget in USD'))
    await user.type(screen.getByLabelText('Run budget in USD'), '1.00')
    expect(start.disabled).toBe(true)
    expect(screen.getByText('Check the authorization box for this run.')).toBeTruthy()
    await user.click(screen.getByLabelText('I authorize this current paid run'))
    expect(start.disabled).toBe(false)
    await user.click(start)
    expect(start.disabled).toBe(true)
    await user.click(start)
    expect(fetchMock.mock.calls.filter(([url]) => String(url) === '/api/edit/batches')).toHaveLength(1)
    releaseBatch()
    await waitFor(() => expect(screen.getByText(/1 job queued/)).toBeTruthy())
    expect(start.disabled).toBe(true)
  })
})
