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
  publication_profile_id: string
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
  versions: ImageVersion[]
  prompt_history: CompiledPrompt[]
}

export interface ImageVersion {
  id: string
  version_number: number
  review_status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'SUPERSEDED'
  created_at: string
  width: number
  height: number
  reviewed_at: string | null
  rejection_reason: string | null
  replacement_of_version_id: string | null
  superseded_by_version_id: string | null
  superseded_at: string | null
  image_url: string
  master_url?: string | null
  engine?: 'DETERMINISTIC' | 'GENERATIVE' | null
}

export interface LocalSettings {
  preset_id: string
  levels_strength: number
  black_point: number
  white_point: number
  exposure_ev: number
  red_gain: number
  blue_gain: number
  shadow_lift: number
  highlight_compression: number
  denoise: number
  sharpen: number
  straighten_deg: number
  lens_k1: number
  perspective_vertical: number
  crop: [number, number, number, number]
}

export interface LocalRecommendation {
  photo_id: string
  photo_revision: number
  preset_id: string
  preset_name: string
  presets: Array<{ id: string; name: string }>
  analysis_version: string
  measurements: { luminance_p01: number; luminance_median: number; luminance_p99: number; geometry_note: string; white_balance_note: string }
  settings: LocalSettings
}

export interface LocalJob {
  id: string
  photo_id: string
  recipe_id: string
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
  image_version_id: string | null
  master_width: number | null
  master_height: number | null
  error: string | null
  replacement_of_version_id: string | null
}

export interface EditJob {
  id: string
  batch_id: string
  photo_id: string
  compiled_prompt_id: string
  engine: 'DETERMINISTIC' | 'GENERATIVE'
  model: string | null
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'
  error: string | null
  image_version_id: string | null
  estimated_cost_usd: number | null
  actual_cost_usd: number | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  replacement_of_version_id: string | null
}

export interface EditPreview {
  items: Array<{ photo_id: string; eligible: boolean; reason?: string; prompt_id?: string; prompt_version?: number; prompt_text?: string; replacement_of_version_id?: string | null }>
  engine: 'DETERMINISTIC' | 'GENERATIVE'
  model: string | null
  estimated_cost_usd: string | null
  cost_note: string
  availability: string
}

export interface Preset {
  id: string
  version: number
  name: string
  structured_instructions: string
  updated_at: string
}

export interface PublicationProfile {
  id: string
  version: number
  name: string
  image_format: 'JPEG' | 'PNG'
  file_extension: string
  mime: string
  max_long_edge: number
  quality: number | null
  color_space: string
  preserve_aspect_ratio: number
  allow_upscale: number
  strip_metadata: number
}

export interface Options {
  subjects: Array<{ id: string; slug: string; display_name: string }>
  tags: Tag[]
  presets: Preset[]
  publication_profiles: PublicationProfile[]
  cities: string[]
  countries: string[]
}

export interface ReviewForm {
  editorial_description: string
  city: string
  country: string
  primary_subject: string
  content_tags: string
  condition_tags: string
  preset_id: string
  publication_profile_id: string
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
  publication_profile_id: string
  ai_allowance: number
  ai_suggestion_editable: string
  user_instructions: string
  approved_constraints: string
  semantic_change_consent: boolean
  analysis_run_id: string | null
  review_state: ReviewState
}

export interface VisitedCity { id: string; city: string; country: string; radius_km: number; revision: number }
export interface CatalogSuggestion {
  id: string; photo_id: string; status: 'PENDING' | 'ACCEPTED' | 'DISMISSED' | 'UNDONE'
  created_at: string; model_id: string; model_revision: string; cached?: boolean
  original_filename?: string
  proposed: { primary_subject: string; content_tags: string[]; condition_tags: string[]; editorial_description: string; preset_id: string; city: string; country: string }
  evidence: { top_labels: Array<{ label: string; similarity: number }>; location: { status: string; distance_km: number | null }; warning: string }
  applied: { fields: string[] } | null
}

export interface LocationPreview {
  id?: string; city: string; country: string
  items: Array<{ photo_id: string; eligible: boolean; reason: string; revision: number }>
  applied_count?: number
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
  publication_profile_id: string
  publication_profile_snapshot: PublicationProfile
}
