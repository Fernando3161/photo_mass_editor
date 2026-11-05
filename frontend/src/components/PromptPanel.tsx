import type { AnalysisEstimate, CompiledPrompt, RefinementEstimate, PromptRefinement } from '../types'

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
  refinementEstimate: RefinementEstimate | null
  refinementAuthorized: boolean
  refinement: PromptRefinement | null
  refinementText: string
  refinementHistory: PromptRefinement[]
  onEstimateRefinement: () => void
  onRefinementAuthorized: (value: boolean) => void
  onRunRefinement: () => void
  onRefinementText: (value: string) => void
  onReviewRefinement: (value: PromptRefinement) => void
  onAdoptRefinement: () => void
}

export function PromptPanel(props: Props) {
  return (
    <div className="panel-section form-grid prompt-panel">
      <div className="span-two section-heading"><div><p className="eyebrow">Preparation</p><h3>Analysis and final prompt</h3></div><span className="phase-chip">Opt-in</span></div>
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
      {props.prompt && <div className="span-two panel-section">
        <h4>Optional text refinement</h4>
        <p>Send the current prompt text to OpenAI for an editable proposal. No photograph is sent. The deterministic prompt remains available if refinement fails.</p>
        <button type="button" className="button-secondary" disabled={props.busy || props.promptText !== props.prompt.compiled_text} onClick={props.onEstimateRefinement}>Preview text cost</button>
        {props.refinementEstimate && <p role="status">{props.refinementEstimate.model} · planning estimate ${props.refinementEstimate.estimated_cost_usd} USD. {props.refinementEstimate.note}</p>}
        <label className="consent-row"><input type="checkbox" checked={props.refinementAuthorized} onChange={(event) => props.onRefinementAuthorized(event.target.checked)} /> I authorize this paid text request</label>
        <button type="button" className="button-primary" disabled={props.busy || !props.refinementAuthorized || !props.refinementEstimate || props.promptText !== props.prompt.compiled_text || props.refinementEstimate.prompt_id !== props.prompt.id} onClick={props.onRunRefinement}>Request proposal</button>
      </div>}
      {props.refinement?.status === 'SUCCEEDED' && <div className="span-two panel-section">
        <h4>Proposed prompt</h4>
        <p>Compare with the deterministic baseline before adopting. Adopting creates a pending version; image editing still needs prompt approval and separate run authorization.</p>
        <p>Original AI proposal (saved unchanged):</p>
        <pre className="prompt-proposal">{props.refinement.proposed_text}</pre>
        {props.refinement.restored_requirements > 0 && <p role="status">{props.refinement.restored_requirements} required preservation or profile rule(s) were restored in the draft below. Review them before adopting.</p>}
        <label><span>Adoption draft (editable)</span><textarea rows={12} value={props.refinementText} onChange={(event) => props.onRefinementText(event.target.value)} /></label>
        <button type="button" className="button-secondary" disabled={props.busy || !props.refinementText.trim()} onClick={props.onAdoptRefinement}>Adopt as new version</button>
      </div>}
      {props.refinementHistory.length > 0 && <details className="span-two"><summary>Refinement history ({props.refinementHistory.length})</summary><ol>{props.refinementHistory.map((item) => <li key={item.id}>{item.created_at} · {item.model} · {item.status}{item.error ? ` · ${item.error}` : ''}{item.status === 'SUCCEEDED' && <button type="button" className="button-secondary" disabled={props.busy} onClick={() => props.onReviewRefinement(item)}>Review proposal</button>}</li>)}</ol></details>}
      {props.promptHistory.length > 0 && <details className="span-two"><summary>Prompt history ({props.promptHistory.length})</summary><ol>{props.promptHistory.map((item) => <li key={item.id}>v{item.version_number} · {item.user_modified ? 'owner edited' : 'compiled'} · {item.approved_for_job ? 'approved' : 'not approved'}</li>)}</ol></details>}
    </div>
  )
}
