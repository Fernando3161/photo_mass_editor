# Logical database schema — Phase 04 implementation and later contract

Phase 01 implements the catalog base. Phase 02 adds metadata review state, presets, and drafts. Phase 03 migrations `003_analysis_prompts.sql`, `004_publication_profiles.sql`, and `005_add_review_presets.sql` add analysis/prompt provenance, the versioned publication-input contract, and five additional owner-requested draft presets. Phase 04 migration `006_editing_jobs.sql` adds masks, job/batch receipts, and generated-version provenance. Export tables await Phase 05. Use UUID primary keys and UTC timestamps; retain original EXIF times with original offset when known.

## Entity tables
- `photos`: id, original_filename, original_path, managed_original_path(nullable), sha256, mime, width, height, imported_at, capture_datetime_raw, capture_offset(nullable), camera/lens, original_exif_json, source_missing(bool), primary_subject_id(nullable), editorial_description, city/country(nullable), private_lat/lon(nullable), revision.
- `subjects`: id, slug, display_name; main subject optional, one per photo.
- `tags`: id, slug, display_name, kind (CONTENT | CONDITION | OTHER).
- `photo_tags`: photo_id, tag_id, source (AI|USER), user_confirmed, confidence(nullable), UNIQUE(photo_id,tag_id); user edits override AI, without deleting observation history.
- `analysis_runs` (Phase 03): id, photo_id, source_hash, provider/model/template/config signature, raw/sanitized output, suggested primary/tags/edits, status, estimate/actual cost, currency, usage, error, analyzed_at. Successful analysis is cached by source/config signature.
- `review_drafts` (Phase 02/03): id, photo_id(unique), revision, preset, publication-profile ID, allowance, editable suggestion, owner instructions, approved constraints, semantic consent, adopted analysis ID, timestamps, and compiled-prompt stale flag.
- `publication_profiles` (Phase 03): immutable versioned format, extension/MIME, maximum long edge, quality, color space, aspect/upscale/metadata rules, and active state. `website-standard-v1` is JPEG, 1600-pixel maximum long edge, quality 85, sRGB, aspect preserved, no upscale, metadata stripped.
- `publication_inputs` (Phase 03 schema; populated in Phase 04): photo/profile/source hash, derived path/hash/dimensions/format/MIME, encoder settings, status, and creation time. The uniqueness key prevents silently replacing the same source/profile derivation.
- `presets` (Phase 02/03): id, version, name, structured_instructions, updated_at. Three editable draft presets are seeded in Phase 02; Phase 03 adds museum artwork, group photo, night architecture, food, and panoramic scene. Every owner edit increments the version; migration 005 leaves existing preset rows untouched.
- `compiled_prompts` (Phase 03): immutable numbered versions with parent ID, source/photo/draft revisions, policy/compiler versions, publication-profile ID and full snapshot, complete input snapshot, compiled text, owner-modified flag, explicit approval, and timestamps.
- `edit_jobs` (Phase 04): id, batch_id, photo_id, compiled_prompt_id, publication_input_id/hash, engine, model, settings JSON, mask ID, signature, request key, status (QUEUED|RUNNING|SUCCEEDED|FAILED|CANCELLED), raw path/hash, resulting version ID, timestamps, error, cost/usage, and authorization time. Generative adapters receive the publication-input path, never the original path.
- `image_versions` (Phase 01 base, populated in Phase 04): id, photo_id, job_id, publication_input_id, version_number, path, sha256, MIME, width, height, created_at, review_status (PENDING|APPROVED|REJECTED), reviewed_at, rejection_reason. Originals never appear as generated versions.
- `masks` (Phase 04): id, photo ID, publication-input ID, private PNG path/hash, width/height, creation time. An uploaded mask must contain both transparent and opaque pixels and match the derivative dimensions.
- `edit_batches` (Phase 04): id, selection snapshot, engine, status, authorized time, planning budget. Each item is a separate `edit_jobs` row.
- `exports`: id, created_at, target, manifest_path, privacy_policy_version, status; `export_items`: export_id, photo_id, image_version_id, derivative_path, derivative_sha256.

`private_lat` and `private_lon` are populated only from complete, valid EXIF GPS coordinates and direction references. Missing or invalid N/S or E/W references leave both fields null; the importer does not guess a hemisphere. `city` and `country` are optional editorial fields and are not inferred or reverse-geocoded. Phase 02 API details expose only a `gps_present` boolean, not the private values or raw EXIF.

## Required integrity rules
Unique per-photo version_number, per-file checksums, foreign keys ON. At most ONE approved version per photo is enforced by a partial unique index. Approval is an explicit atomic change recorded in `review_events`; it cannot change image bytes. Promotion of a different version over an already approved result is not available yet. Prompt revisions never silently rewrite executed job inputs. A job is ineligible unless its publication input source hash and profile match its approved prompt snapshot.

## Derived state
Photo overall status is derived, not a lossy single enum: import readiness, analysis state, draft state, pending jobs and current approved version. A generated successful output starts PENDING; it is not APPROVED. Default retry selection = eligible photos with no approved version, excluding running/queued jobs; previously rejected identical config requires explicit override or changed prompt. Failed jobs retain errors and attempts.

## Migration discipline
Migrations are ordered, transactional SQL files recorded in `schema_migrations`. Tests cover fresh schema creation, upgrading an existing Phase 01 catalog, repeated startup, and persistence. Sensitive metadata remains subject to privacy/export rules.
