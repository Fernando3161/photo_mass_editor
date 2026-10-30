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
  review_state: ReviewState
}
