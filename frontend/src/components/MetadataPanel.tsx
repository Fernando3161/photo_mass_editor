import type { ReactNode } from 'react'
import type { Options, PhotoDetail, Preset, ReviewForm } from '../types'

interface Props {
  photo: PhotoDetail
  form: ReviewForm
  options: Options
  onChange: <K extends keyof ReviewForm>(key: K, value: ReviewForm[K]) => void
  onReviewNext: () => void
  onSaveNext: () => void
  onEditPreset: (preset: Preset) => void
  promptPanel?: ReactNode
}

export function MetadataPanel({ photo, form, options, onChange, onReviewNext, onSaveNext, onEditPreset, promptPanel }: Props) {
  const selectedPreset = options.presets.find((preset) => preset.id === form.preset_id)
  return (
    <aside className="metadata-panel" aria-label="Photo metadata editor">
      <div className="panel-section compact">
        <p className="eyebrow">Catalog record</p>
        <h2 title={photo.original_filename}>{photo.original_filename}</h2>
        <dl className="facts">
          <div><dt>Captured</dt><dd>{photo.capture_datetime_raw || 'Unknown'}</dd></div>
          <div><dt>Camera</dt><dd>{photo.camera || 'Unknown'}</dd></div>
          <div><dt>Lens</dt><dd>{photo.lens || 'Not recorded'}</dd></div>
          <div><dt>Location</dt><dd>{photo.gps_present ? 'Private GPS present' : 'No GPS'}{photo.city ? ` · ${photo.city}` : ''}</dd></div>
        </dl>
      </div>

      <div className="panel-section form-grid">
        <label><span>Review status</span><select value={form.review_state} onChange={(event) => onChange('review_state', event.target.value as ReviewForm['review_state'])}><option value="UNREVIEWED">Unreviewed</option><option value="IN_PROGRESS">In progress</option><option value="REVIEWED">Reviewed</option></select></label>
        <label><span>Primary subject</span><input list="subject-options" value={form.primary_subject} onChange={(event) => onChange('primary_subject', event.target.value)} placeholder="Optional" /><datalist id="subject-options">{options.subjects.map((subject) => <option key={subject.id} value={subject.display_name} />)}</datalist></label>
        <label><span>Content tags</span><input value={form.content_tags} onChange={(event) => onChange('content_tags', event.target.value)} placeholder="architecture, street, sculpture" /><small>Separate tags with commas</small></label>
        <label><span>Condition tags</span><input value={form.condition_tags} onChange={(event) => onChange('condition_tags', event.target.value)} placeholder="night, backlit, haze" /></label>
        <label className="span-two"><span>Description</span><textarea value={form.editorial_description} onChange={(event) => onChange('editorial_description', event.target.value)} rows={3} /></label>
        <label><span>City</span><input value={form.city} onChange={(event) => onChange('city', event.target.value)} /></label>
        <label><span>Country</span><input value={form.country} onChange={(event) => onChange('country', event.target.value)} /></label>
      </div>

      <div className="panel-section form-grid">
        <div className="span-two section-heading"><div><p className="eyebrow">Preparation</p><h3>Editing draft</h3></div><span className="phase-chip">Editable</span></div>
        <label className="span-two"><span>Draft preset</span><div className="field-with-action"><select value={form.preset_id} onChange={(event) => onChange('preset_id', event.target.value)}><option value="">No preset</option>{options.presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}</option>)}</select>{selectedPreset && <button type="button" className="text-button" onClick={() => onEditPreset(selectedPreset)}>Edit preset</button>}</div>{selectedPreset && <small>{selectedPreset.structured_instructions}</small>}</label>
        <label className="span-two range-label"><span>AI allowance: {form.ai_allowance}</span><input type="range" min="0" max="10" value={form.ai_allowance} onChange={(event) => onChange('ai_allowance', Number(event.target.value))} /><small>Application policy only. Values above 3 require explicit semantic-change consent.</small></label>
        <label className="span-two consent-row"><input type="checkbox" checked={form.semantic_change_consent} onChange={(event) => onChange('semantic_change_consent', event.target.checked)} /> I explicitly allow semantic changes for this draft</label>
        <label className="span-two"><span>AI suggested corrections</span><textarea value={form.ai_suggestion_editable} onChange={(event) => onChange('ai_suggestion_editable', event.target.value)} rows={3} placeholder="No analysis result adopted" /></label>
        <label className="span-two"><span>My additional instructions</span><textarea value={form.user_instructions} onChange={(event) => onChange('user_instructions', event.target.value)} rows={3} placeholder="Optional notes for a later editing run" /></label>
        <label className="span-two"><span>Approved constraints</span><textarea value={form.approved_constraints} onChange={(event) => onChange('approved_constraints', event.target.value)} rows={3} placeholder="Example: keep the sky unchanged; preserve faces" /></label>
      </div>

      {promptPanel}

      <div className="panel-actions">
        <button type="button" className="button-secondary" onClick={onSaveNext}>Save & next</button>
        <button type="button" className="button-primary" onClick={onReviewNext}>Mark reviewed & next</button>
      </div>
    </aside>
  )
}
