# Logical database schema — Phase 03 implementation and later contract

Phase 01 implements the catalog base. Phase 02 adds metadata review state, presets, and drafts. Phase 03 migration `003_analysis_prompts.sql` adds `analysis_runs`, `compiled_prompts`, approved constraints, semantic-change consent, and the adopted analysis link. Job, batch, mask, and export tables await later phases. Use UUID primary keys and UTC timestamps; retain original EXIF times with original offset when known.

## Entity tables
- `photos`: id, original_filename, original_path, managed_original_path(nullable), sha256, mime, width, height, imported_at, capture_datetime_raw, capture_offset(nullable), camera/lens, original_exif_json, source_missing(bool), primary_subject_id(nullable), editorial_description, city/country(nullable), private_lat/lon(nullable), revision.
- `subjects`: id, slug, display_name; main subject optional, one per photo.
- `tags`: id, slug, display_name, kind (CONTENT | CONDITION | OTHER).
- `photo_tags`: photo_id, tag_id, source (AI|USER), user_confirmed, confidence(nullable), UNIQUE(photo_id,tag_id); user edits override AI, without deleting observation history.
- `analysis_runs` (Phase 03): id, photo_id, source_hash, provider/model/template/config signature, raw/sanitized output, suggested primary/tags/edits, status, estimate/actual cost, currency, usage, error, analyzed_at. Successful analysis is cached by source/config signature.
- `review_drafts` (Phase 02/03): id, photo_id(unique), revision, preset, allowance, editable suggestion, owner instructions, approved constraints, semantic consent, adopted analysis ID, timestamps, and compiled-prompt stale flag.
- `presets` (Phase 02): id, version, name, structured_instructions, updated_at. Three editable draft presets are seeded; every edit increments the version.
- `compiled_prompts` (Phase 03): immutable numbered versions with parent ID, source/photo/draft revisions, policy/compiler versions, complete input snapshot, compiled text, owner-modified flag, explicit approval, and timestamps.
- `edit_jobs`: id, batch_id(nullable), photo_id, compiled_prompt_id, source_hash, engine, model(nullable), operation_config_json, mask_id(nullable), status (QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELLED), timestamps, errors, cost/usage, idempotency_key.
- `image_versions`: id, photo_id, job_id(nullable), version_number, path, sha256, width, height, created_at, review_status (PENDING|APPROVED|REJECTED), reviewed_at(nullable), rejection_reason(nullable). Originals never appear as generated versions.
- `masks`: id, photo_id, file_path, sha256, width, height, created_at, associated_prompt_id(nullable).
- `batches`: id, name, filter_snapshot_json, created_at, initiated_at(nullable), status; `batch_items`: batch_id, photo_id, job_id(nullable), selection_reason.
- `exports`: id, created_at, target, manifest_path, privacy_policy_version, status; `export_items`: export_id, photo_id, image_version_id, derivative_path, derivative_sha256.

`private_lat` and `private_lon` are populated only from complete, valid EXIF GPS coordinates and direction references. Missing or invalid N/S or E/W references leave both fields null; the importer does not guess a hemisphere. `city` and `country` are optional editorial fields and are not inferred or reverse-geocoded. Phase 02 API details expose only a `gps_present` boolean, not the private values or raw EXIF.

## Required integrity rules
Unique per-photo version_number, per-file checksums, foreign keys ON. At most ONE current approved version per photo (enforce transactionally or partial unique index). Approval is an explicit atomic change and can revoke prior approval with an audit event; cannot change image bytes. Add `review_events` with actor, timestamp, previous/next state, version_id, optional note for durable approval history. Prompt revisions never silently rewrite executed job inputs.

## Derived state
Photo overall status is derived, not a lossy single enum: import readiness, analysis state, draft state, pending jobs and current approved version. A generated successful output starts PENDING; it is not APPROVED. Default retry selection = eligible photos with no approved version, excluding running/queued jobs; previously rejected identical config requires explicit override or changed prompt. Failed jobs retain errors and attempts.

## Migration discipline
Migrations are ordered, transactional SQL files recorded in `schema_migrations`. Tests cover fresh schema creation, upgrading an existing Phase 01 catalog, repeated startup, and persistence. Sensitive metadata remains subject to privacy/export rules.
