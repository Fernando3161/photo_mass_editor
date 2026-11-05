import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MetadataPanel } from '../components/MetadataPanel'
import type { Options, PhotoDetail, ReviewForm } from '../types'

const photo = { id: 'one', original_filename: 'synthetic.jpg', draft: {}, tags: [] } as unknown as PhotoDetail
const form: ReviewForm = {
  editorial_description: 'Daytime travel photograph of building.', city: '', country: '', primary_subject: 'building',
  content_tags: 'architecture, people', condition_tags: 'daytime', preset_id: 'architecture-clarity',
  publication_profile_id: 'website-standard-v1', ai_allowance: 0, ai_suggestion_editable: '',
  user_instructions: '', approved_constraints: '', semantic_change_consent: false, analysis_run_id: null,
  review_state: 'UNREVIEWED',
}
const options: Options = { subjects: [], tags: [], cities: [], countries: [], presets: [{ id: 'architecture-clarity', version: 1, name: 'Architecture clarity', structured_instructions: 'Preserve geometry.', updated_at: 'now' }], publication_profiles: [] }

describe('provisional catalog form', () => {
  it('shows editable suggestions and an unapproved prompt before acceptance', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const onAcceptPrepare = vi.fn()
    const onSavePreparedPrompt = vi.fn()
    const props = { photo, form, options, onChange, onReviewNext: vi.fn(), onSaveNext: vi.fn(), onEditPreset: vi.fn(),
      provisional: true, onAcceptPrepare, onDiscard: vi.fn(),
      preparedPreview: { proposed_text: 'Preserve documentary authenticity. Observed tags: architecture, people.', conflicts: [], unapproved: true },
      onSavePreparedPrompt }
    const { rerender } = render(<MetadataPanel {...props} />)
    expect(screen.getByText(/Nothing is saved until you accept/)).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Save & next' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByLabelText('Primary subject') as HTMLInputElement).value).toBe('building')
    expect(screen.getByText(/Observed tags: architecture, people/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Accept & prepare' }))
    expect(onAcceptPrepare).toHaveBeenCalledOnce()
    expect(onSavePreparedPrompt).not.toHaveBeenCalled()
    rerender(<MetadataPanel {...props} provisional={false} />)
    await user.click(screen.getByRole('button', { name: 'Save unapproved prompt version' }))
    expect(onSavePreparedPrompt).toHaveBeenCalledOnce()
  })
})
