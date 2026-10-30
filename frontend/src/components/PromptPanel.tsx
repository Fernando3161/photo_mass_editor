import type { AnalysisEstimate, CompiledPrompt } from '../types'

interface Props {
  estimate: AnalysisEstimate | null
  analysisAuthorized: boolean
  busy: boolean
  prompt: CompiledPrompt | null
  promptText: string
  promptHistory: CompiledPrompt[]
  onEstimate: () => void
  onAuthorized: (value: boolean) => void
  onRunAnalysis: () => void
  onCompile: () => void
  onPromptText: (value: string) => void
  onSavePrompt: () => void
  onApprovePrompt: () => void
}

export function PromptPanel(props: Props) {
  return (
    <div className="panel-section form-grid prompt-panel">
      <div className="span-two section-heading"><div><p className="eyebrow">Phase 3</p><h3>Analysis and final prompt</h3></div><span className="phase-chip">Opt-in</span></div>
      <div className="span-two analysis-controls">
        <button type="button" className="button-secondary" onClick={props.onEstimate} disabled={props.busy}>Preview analysis cost</button>
        {props.estimate && <p role="status">{props.estimate.photo_count} photo · {props.estimate.cached_count} cached · {props.estimate.billable_count} billable · {props.estimate.estimated_cost} {props.estimate.currency} · {props.estimate.provider}/{props.estimate.model}</p>}
        <label className="consent-row"><input type="checkbox" checked={props.analysisAuthorized} onChange={(event) => props.onAuthorized(event.target.checked)} /> I authorize analysis for this current run</label>
        <button type="button" className="button-primary" disabled={props.busy || !props.analysisAuthorized || !props.estimate} onClick={props.onRunAnalysis}>Run analysis for current photo</button>
        <small>Authorization applies only to this click. Provider credentials remain server-side. Cached results do not create another provider call.</small>
      </div>
      <div className="span-two prompt-actions">
        <button type="button" className="button-secondary" disabled={props.busy} onClick={props.onCompile}>Compile prompt preview</button>
        {props.prompt && <span>Version {props.prompt.version_number}{props.prompt.approved_for_job ? ' · Approved' : ' · Pending approval'}</span>}
      </div>
      {props.prompt && <>
        <label className="span-two"><span>Compiled prompt</span><textarea rows={12} value={props.promptText} onChange={(event) => props.onPromptText(event.target.value)} /></label>
        <div className="span-two panel-actions">
          <button type="button" className="button-secondary" disabled={props.busy || props.promptText.trim() === props.prompt.compiled_text.trim()} onClick={props.onSavePrompt}>Save as new version</button>
          <button type="button" className="button-primary" disabled={props.busy || props.promptText.trim() !== props.prompt.compiled_text.trim() || Boolean(props.prompt.approved_for_job)} onClick={props.onApprovePrompt}>Approve current prompt</button>
        </div>
        <small className="span-two">Every save creates an immutable version. Changing photo metadata or the editing draft makes approval stale.</small>
      </>}
      {props.promptHistory.length > 0 && <details className="span-two"><summary>Prompt history ({props.promptHistory.length})</summary><ol>{props.promptHistory.map((item) => <li key={item.id}>v{item.version_number} · {item.user_modified ? 'owner edited' : 'compiled'} · {item.approved_for_job ? 'approved' : 'not approved'}</li>)}</ol></details>}
    </div>
  )
}
