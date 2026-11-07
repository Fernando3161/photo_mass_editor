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
  rule_suggestions_enabled: true, rule_selected_ids: null, rule_instructions_override: null,
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
      preparedPreview: { proposed_text: 'Preserve documentary authenticity. Observed tags: architecture, people.', conflicts: [], unapproved: true,
        rule_instructions: '', rule_suggestions: { rules: [], selected_ids: [], constraints: '', config_version: 1 } },
      onSavePreparedPrompt, onRefreshRules: vi.fn() }
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

  it('lets the owner select, edit, disable, and refresh rule suggestions', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const onRefreshRules = vi.fn()
    const preview = { proposed_text: 'Preserve documentary authenticity.', conflicts: [], unapproved: true,
      rule_instructions: 'Improve architectural illumination.', rule_suggestions: { selected_ids: ['architecture-light'], constraints: 'Preserve geometry.', config_version: 1,
        rules: [
          { id: 'architecture-light', name: 'Architectural lighting', target: 'instruction' as const, instruction: 'Improve architectural illumination.', optional: false, requires_consent: false, selected: true },
          { id: 'architecture-remove-people', name: 'Remove incidental people', target: 'instruction' as const, instruction: 'Remove incidental people.', optional: true, requires_consent: true, selected: false },
        ] } }
    render(<MetadataPanel photo={photo} form={form} options={options} onChange={onChange} onReviewNext={vi.fn()} onSaveNext={vi.fn()}
      onEditPreset={vi.fn()} onRefreshRules={onRefreshRules} preparedPreview={preview} />)
    expect(screen.getAllByText(/Preserve geometry/).length).toBeGreaterThan(0)
    await user.click(screen.getByLabelText(/Remove incidental people/))
    expect(onChange).toHaveBeenCalledWith('rule_selected_ids', ['architecture-light', 'architecture-remove-people'])
    await user.clear(screen.getByLabelText('Generated instructions'))
    await user.type(screen.getByLabelText('Generated instructions'), 'Keep the light natural.')
    expect(onChange).toHaveBeenCalledWith('rule_instructions_override', expect.any(String))
    await user.click(screen.getByLabelText('Use rule-based suggestions for this photo'))
    expect(onChange).toHaveBeenCalledWith('rule_suggestions_enabled', false)
    await user.click(screen.getByRole('button', { name: 'Refresh suggestions from tags' }))
    expect(onRefreshRules).toHaveBeenCalledOnce()
  })
})
