# Logical database schema — Phase 00 contract

Phase 01 now implements SQLite migration `001_catalog.sql` for `photos`, `subjects`, `tags`, `photo_tags`, `image_versions`, and `review_events`. This document remains the full logical domain model; analysis, prompt, job, batch, mask, and export tables await their phases. Use UUID primary keys and UTC timestamps; retain original EXIF times with original offset when known.

## Entity tables
- `photos`: id, original_filename, original_path, managed_original_path(nullable), sha256, mime, width, height, imported_at, capture_datetime_raw, capture_offset(nullable), camera/lens, original_exif_json, source_missing(bool), primary_subject_id(nullable), editorial_description, city/country(nullable), private_lat/lon(nullable), revision.
- `subjects`: id, slug, display_name; main subject optional, one per photo.
- `tags`: id, slug, display_name, kind (CONTENT | CONDITION | OTHER).
- `photo_tags`: photo_id, tag_id, source (AI|USER), user_confirmed, confidence(nullable), UNIQUE(photo_id,tag_id); user edits override AI, without deleting observation history.
- `analysis_runs`: id, photo_id, source_hash, model, template_version, raw/sanitized output, suggested_primary, suggested_tags, suggested_edits, status, cost/usage(nullable), analyzed_at. Analysis is opt-in and cached by source/config signature.
- `review_drafts`: id, photo_id, revision, preset_id, ai_allowance(0..10), ai_suggestion_editable, user_instructions, conditions_override, updated_at, saved_at, compiled_prompt_stale.
- `presets`: id, version, name, structured instructions; three initially configurable presets, contents not frozen without review.
- `compiled_prompts`: id, photo_id, draft_revision, policy_version, compiler_model(nullable), compiled_text, user_modified(bool), approved_for_job(bool), generated_at; input snapshots retained.
- `edit_jobs`: id, batch_id(nullable), photo_id, compiled_prompt_id, source_hash, engine, model(nullable), operation_config_json, mask_id(nullable), status (QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELLED), timestamps, errors, cost/usage, idempotency_key.
- `image_versions`: id, photo_id, job_id(nullable), version_number, path, sha256, width, height, created_at, review_status (PENDING|APPROVED|REJECTED), reviewed_at(nullable), rejection_reason(nullable). Originals never appear as generated versions.
- `masks`: id, photo_id, file_path, sha256, width, height, created_at, associated_prompt_id(nullable).
- `batches`: id, name, filter_snapshot_json, created_at, initiated_at(nullable), status; `batch_items`: batch_id, photo_id, job_id(nullable), selection_reason.
- `exports`: id, created_at, target, manifest_path, privacy_policy_version, status; `export_items`: export_id, photo_id, image_version_id, derivative_path, derivative_sha256.

## Required integrity rules
Unique per-photo version_number, per-file checksums, foreign keys ON. At most ONE current approved version per photo (enforce transactionally or partial unique index). Approval is an explicit atomic change and can revoke prior approval with an audit event; cannot change image bytes. Add `review_events` with actor, timestamp, previous/next state, version_id, optional note for durable approval history. Prompt revisions never silently rewrite executed job inputs.

## Derived state
Photo overall status is derived, not a lossy single enum: import readiness, analysis state, draft state, pending jobs and current approved version. A generated successful output starts PENDING; it is not APPROVED. Default retry selection = eligible photos with no approved version, excluding running/queued jobs; previously rejected identical config requires explicit override or changed prompt. Failed jobs retain errors and attempts.

## Migration discipline
Phase 01 produces actual SQL migration(s) and fixture tests for import/reload/renaming/duplicates/review-history; no schema implementation in Phase 00. Sensitive metadata is subject to privacy/export rules.
