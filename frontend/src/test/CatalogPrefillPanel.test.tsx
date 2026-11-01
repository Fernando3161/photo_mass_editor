import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CatalogPrefillPanel } from '../components/CatalogPrefillPanel'
import type { CatalogSuggestion, PhotoDetail } from '../types'

const calls = vi.hoisted(() => ({ run: vi.fn(), decide: vi.fn(), undo: vi.fn() }))
const suggestion: CatalogSuggestion = {
  id: 'suggestion-1', photo_id: 'photo-1', status: 'PENDING', created_at: 'now', model_id: 'local-clip', model_revision: 'pinned',
  proposed: { primary_subject: 'opera house', content_tags: ['opera house'], condition_tags: [], editorial_description: 'Travel photograph of opera house.', preset_id: 'architecture-clarity', city: '', country: '' },
  evidence: { top_labels: [{ label: 'an opera house', similarity: 31 }], location: { status: 'NO_GPS', distance_km: null }, warning: 'Review visually' }, applied: null,
}
let items: CatalogSuggestion[] = []
vi.mock('../api', () => ({ api: {
  cities: async () => [], suggestions: async () => items, modelStatus: async () => ({ state: 'ready', file: '', downloaded: 0, total: 0, error: '', cached: true }),
  runPrefill: calls.run, decideSuggestion: calls.decide, undoSuggestion: calls.undo,
  getPhoto: async () => ({ id: 'photo-1', revision: 0 }),
  listPhotos: async () => [], getOptions: async () => ({}),
} }))

const photo = { id: 'photo-1', revision: 0 } as PhotoDetail

describe('local catalog prefill panel', () => {
  beforeEach(() => {
    items = []
    calls.run.mockReset().mockImplementation(async () => { items = [suggestion]; return { results: [suggestion] } })
    calls.decide.mockReset().mockImplementation(async () => { items = [{ ...suggestion, status: 'ACCEPTED' }]; return { suggestion: items[0], photo } })
    calls.undo.mockReset().mockImplementation(async () => { items = [{ ...suggestion, status: 'UNDONE' }]; return { suggestion: items[0], photo } })
  })

  it('requires local-run authorization and supports field acceptance and undo', async () => {
    const user = userEvent.setup()
    const onPhoto = vi.fn()
    render(<CatalogPrefillPanel photo={photo} visiblePhotoIds={['photo-1']} beforeMutation={async () => true} onPhoto={onPhoto} onCatalogRefresh={async () => {}} />)
    const start = screen.getByRole('button', { name: 'Suggest current photo' }) as HTMLButtonElement
    expect(start.disabled).toBe(true)
    await user.click(screen.getByLabelText('Authorize this local recognition run'))
    await user.click(start)
    await screen.findByRole('button', { name: 'Accept selected empty fields' })
    expect(calls.run).toHaveBeenCalledWith(['photo-1'], false)
    await user.click(screen.getByRole('button', { name: 'Accept selected empty fields' }))
    await waitFor(() => expect(calls.decide).toHaveBeenCalledWith('suggestion-1', expect.arrayContaining(['primary_subject']), 0, false))
    expect(onPhoto).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Undo acceptance' }))
    await waitFor(() => expect(calls.undo).toHaveBeenCalledWith('suggestion-1'))
  })
})
