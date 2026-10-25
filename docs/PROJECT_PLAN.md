# Phase-gated development plan

Each phase uses one dedicated branch, tests, an acceptance gate, a report, and owner review before merge. Feature tasks may use smaller PRs. Start subsequent phase from the last approved baseline—not an unreviewed branch.

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
Add opt-in AI suggestion generation (bounded batch; cached), image-observation provenance, editable suggestion field, user field, constraint resolver and versioned compiled prompt; preview before paid editing. Tests: API mocks, permission, prompt conflicts, cost estimate, cache, invalidation. Acceptance: user approves or edits compiled prompt; no secret exposed client-side.

## Phase 04 — Editing engine and versioning
Branch: `dev/v1-phase-04-processing`.
Deterministic edits, optional masks and AI adapter, queued jobs, retries, immutable versions, comparisons, approve/reject, job receipts. Tests: original hashes, failure recovery, idempotency, review transitions, concurrency, mocked API, opt-in limited live tests. Acceptance: successful attempt ≠ approval, rejected retained, approved never overwritten, default batch skips approved photos.

## Phase 05 — Export, audit and usability
Branch: `dev/v1-phase-05-export`.
Approved-only export pipeline, EXIF/privacy handling, web derivatives and metadata manifest, cost report, acceptance walk-through with real sample photo batch, cleanup audit. Tests: privacy, export version identity, manifest validity, image dimensions, data recovery. Acceptance: reproducible approved website collection and clear handoff.

## Phase reviews
Every phase report records branch/commit, changed files, acceptance PASS/FAIL/NOT_RUN, evidence, test commands, risks, deferred heavy operations, and next-phase recommendation. Block progression on unresolved original integrity or privacy problems.
