# Phase-gated development plan

Each phase uses one dedicated branch, tests, an acceptance gate, a report, and owner review before merge. Agents leave changes unstaged and uncommitted; the owner manually stages and commits after review. Automatic commits are forbidden. Feature tasks may use smaller PRs after owner commits. Start subsequent phase from the last approved baseline—not an unreviewed branch.

## Phase 00 — Foundation and specifications
Branch: `dev/v1-phase-00-foundation`. Implementation/API calls: forbidden.
Deliverables: root AGENTS.md; PROJECT_OBJECTIVES, PROJECT_PLAN, DEVELOPMENT_WORKFLOW, REPOSITORY_ARCHITECTURE, DATA_AND_ARTIFACTS, DATABASE_SCHEMA, IMAGE_EDITING_POLICY, UI_WORKFLOW, TESTING_AND_ACCEPTANCE, TECHNICAL_REPORT_TEMPLATE; Phase 00 report.
Acceptance: documents internally consistent, cross-references checked, risks/gaps made explicit, owner approves scope/architecture; no runtime implementation. Report documents what could not be tested.

## Phase 01 — Catalog ingestion
Branch: `dev/v1-phase-01-catalog`.
Build backend skeleton, SQLite migrations, safe original import/reference, EXIF/GPS extraction, checksums, thumbnails, duplicates, indexing/preflight. Tests: corrupt file, path conflict, duplicate, restart, missing GPS, multi-format, original integrity, migrations. Acceptance: sample dataset reloads with stable IDs and no original file mutation.

## Phase 02 — Desktop review UI
Branch: `dev/v1-phase-02-review-ui`.
Build contact sheet, virtualized filmstrip, dual compare viewer, metadata editor, primary subject/tags/condition tags, auto-save status, keyboard navigation, filters and presets; placeholder suggestions. Tests: navigation, persistence, unsaved-change recovery, accessibility and status. Acceptance: user can review ~200 photos efficiently without opening each on a separate page.

## Phase 03 — Analysis and prompt assembly
Branch: `dev/v1-phase-03-prompts`.
Add opt-in AI suggestion generation (bounded batch; cached), image-observation provenance, editable suggestion field, user field, constraint resolver, selected versioned publication profile, and versioned compiled prompt; preview before paid editing. Tests: API mocks, permission, prompt conflicts, cost estimate, cache, profile snapshot, invalidation. Acceptance: user approves or edits a compiled prompt tied to an exact publication profile; no secret exposed client-side.

## Phase 04 — Editing engine and versioning
Branch: `dev/v1-phase-04-processing`.
Generate and validate immutable publication inputs before any generative request; the initial profile is JPEG/sRGB, maximum 1600-pixel long edge, quality 85, preserved aspect ratio, no upscaling, and stripped metadata. Add deterministic edits, optional masks and AI adapter, queued jobs, retries, immutable raw attempts and normalized publication versions, comparisons, approve/reject, and job receipts. Tests: original hashes, exact input profile, proof that provider input is the derivative rather than the original, failure recovery, idempotency, review transitions, concurrency, mocked API, and opt-in limited live tests. Acceptance: successful attempt ≠ approval, rejected retained, approved never overwritten, default batch skips approved photos.

## Phase 05 — Local catalog prefill and location suggestions
Branch: `dev/v1-phase-05-catalog-prefill`. Start from the owner-approved Phase 04 baseline after the owner commits accepted work. This phase is local metadata enrichment, not image editing or export.

Implementation is on this branch for owner review. The private ~20-photo pilot and visual labeling acceptance remain pending; follow [the Phase 05 review guide](PHASE_05_REVIEW.md) and [technical report](../reports/PHASE_05_TECHNICAL_REPORT.md). Do not treat automated test success as owner approval.

Prefill reviewable suggestions for primary subject, content and condition tags, a short draft editorial description, and draft preset using existing EXIF/filename data, deterministic image measurements, and a locally executed image-recognition model. Draft descriptions may use observed tags and confirmed location, but must not invent an exact landmark; exact subject names require owner confirmation. Suggestions must be tied to the source hash, model/version, candidate-label set, settings, and time. Show the evidence and allow per-photo correction plus bounded bulk accept/undo. Never overwrite non-empty owner-entered or owner-confirmed fields. Keep `My additional instructions`, approved constraints, semantic-change consent, prompt approval, edit authorization, and generated-version approval under explicit owner control; a detected person is not an instruction to remove that person. No external AI API is required or called for this phase.

Location prefill uses the private EXIF GPS already stored by ingestion and an owner-maintained, private visited-cities list with city, country, representative coordinates, and matching radius. Choose a city only when the nearest candidate is within its radius and clearly better than alternatives; otherwise show an ambiguous or unmatched suggestion. Existing textual location metadata may be considered only as a labeled fallback, never as more reliable than confirmed owner data. Photos without GPS need a quick bounded bulk city/country assignment with preview and undo; do not guess location from image appearance. Keep precise GPS and the visited-cities list private. Export only owner-confirmed editorial city/country in Phase 06.

Dependency and model setup is part of Phase 05 implementation and acceptance. Select a CPU-capable local inference stack verified on supported Windows and Linux Python versions; declare every new direct Python package in `requirements.in`, pin the complete resolved environment in `requirements.lock`, and extend the existing cross-platform `scripts/setup_env.py` rather than adding an alternative environment or ad hoc `pip` commands. The normal setup must install and verify those packages inside `.venv`. A separate, pinned model manifest records model ID, immutable revision, license, expected files/hashes, and cache location. The application must automatically fetch missing model files on first local-recognition use, show progress/failure, verify them, and reuse an ignored local cache; no manual browser download or file placement is required. Offer an automated setup-script prefetch option for offline use. Offline recognition must use only verified cached files and must not contact a model host. Update CI for the new phase branch; CI uses the same locked package setup with synthetic fixtures and a fake recognizer, not a large model download. Model and package compatibility, license, and download size must be documented before implementation is accepted.

Tests: valid/invalid/missing GPS, city radius and ambiguity, no-GPS bulk assignment, owner override preservation, suggestion provenance/cache invalidation, model-download verification and offline failure, prompt staleness after accepted metadata changes, no paid or external image upload, original hash stability, Windows/Linux setup, and UI review/undo. Pilot on a varied owner-selected sample of about 20 photos before offering a 200-photo run; measure suggestion errors and leave uncertain fields blank for review. Acceptance: the owner can prefill and correct the catalog without repetitive per-photo typing or manual dependency/model downloads, while no suggestion silently becomes an approved prompt, paid request, approved version, or publishable location.

## Phase 06 — Export, audit and usability
Branch: `dev/v1-phase-06-export`.
Implementation is on this branch for owner review. The real sample export and visual/privacy acceptance remain pending; follow [the Phase 06 review guide](PHASE_06_REVIEW.md) and [technical report](../reports/PHASE_06_TECHNICAL_REPORT.md).
Approved-only export pipeline, EXIF/privacy handling, thumbnails and any target-specific derivatives, metadata manifest, cost report, acceptance walk-through with a real sample photo batch, and cleanup audit. The approved website image should already match its publication profile, so export must not silently perform another quality-changing resize. Export only confirmed editorial city/country, never private precise GPS by default. Tests: privacy, export version identity, manifest validity, image dimensions, data recovery. Acceptance: reproducible approved website collection and clear handoff.

## Phase reviews
Every phase report records the branch and baseline commit, notes that new changes await the owner's manual commit, and records changed files, acceptance PASS/FAIL/NOT_RUN, evidence, test commands, risks, deferred heavy operations, and next-phase recommendation. Block progression on unresolved original integrity or privacy problems.
