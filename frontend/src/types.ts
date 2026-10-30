export type ReviewState = 'UNREVIEWED' | 'IN_PROGRESS' | 'REVIEWED'

export interface Tag {
  id: string
  slug: string
  display_name: string
  kind: 'CONTENT' | 'CONDITION' | 'OTHER'
  source?: 'AI' | 'USER'
  user_confirmed?: number
}

export interface PhotoSummary {
  id: string
  original_filename: string
  width: number
  height: number
  capture_datetime_raw: string | null
  camera: string | null
  city: string | null
  country: string | null
  review_state: ReviewState
  revision: number
  primary_subject: string | null
  thumbnail_url: string
  tags: Tag[]
}

export interface ReviewDraft {
  preset_id: string | null
  ai_allowance: number
  ai_suggestion_editable: string
  user_instructions: string
  approved_constraints: string
  semantic_change_consent: number
  analysis_run_id: string | null
  compiled_prompt_stale: number
  draft_revision: number
  saved_at: string | null
}

export interface PhotoDetail extends PhotoSummary {
  original_url: string
  editorial_description: string | null
  lens: string | null
  orientation: number | null
  capture_offset: string | null
  gps_present: boolean
  source_missing: number
  draft: ReviewDraft
  versions: Array<{ id: string; version_number: number; review_status: string; created_at: string }>
  prompt_history: CompiledPrompt[]
}

export interface Preset {
  id: string
  version: number
  name: string
  structured_instructions: string
  updated_at: string
}

export interface Options {
  subjects: Array<{ id: string; slug: string; display_name: string }>
  tags: Tag[]
  presets: Preset[]
}

export interface ReviewForm {
  editorial_description: string
  city: string
  country: string
  primary_subject: string
  content_tags: string
  condition_tags: string
  preset_id: string
  ai_allowance: number
  ai_suggestion_editable: string
  user_instructions: string
  approved_constraints: string
  semantic_change_consent: boolean
  analysis_run_id: string | null
  review_state: ReviewState
}

export interface SavePayload {
  expected_revision: number
  editorial_description: string
  city: string
  country: string
  primary_subject: string | null
  content_tags: string[]
  condition_tags: string[]
  preset_id: string | null
  ai_allowance: number
  ai_suggestion_editable: string
  user_instructions: string
  approved_constraints: string
  semantic_change_consent: boolean
  analysis_run_id: string | null
  review_state: ReviewState
}

export interface AnalysisEstimate {
  photo_count: number
  cached_count: number
  billable_count: number
  estimated_cost: string
  currency: string
  provider: string
  model: string
  template_version: string
  max_batch: number
}

export interface AnalysisRun {
  id: string
  photo_id: string
  provider: string
  model: string
  suggested_primary: string | null
  suggested_tags: Array<{ display_name: string; kind: 'CONTENT' | 'CONDITION'; confidence?: number }>
  suggested_edits: string
  cached: boolean
  actual_cost: number | null
}

export interface CompiledPrompt {
  id: string
  photo_id: string
  version_number: number
  parent_prompt_id: string | null
  compiled_text: string
  user_modified: number
  approved_for_job: number
  generated_at: string
  approved_at: string | null
  input_snapshot: Record<string, unknown>
}
