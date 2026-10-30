# Phase 02 — Desktop review UI technical report

- Date: 2026-10-30
- Branch: `dev/v1-phase-02-review-ui`
- Owner-approved Phase 01 baseline: `8ee61fb` (`ph1 reviewed`)
- Owner/reviewer: project owner; approved after manual visual and persistence review
- Owner commit: `9f88647` (`working ui for editing`)
- Recommendation: **APPROVED**; the owner authorized Phase 03

## Scope and acceptance

| Check | Status | Evidence |
| --- | --- | --- |
| Local review API and schema migration | PASS | FastAPI integration tests cover listing, privacy, media, persistence, conflicts, presets, tags, and migration |
| Contact sheet and random access | PASS | Frontend interaction test opens the accessible dialog and selects a distant item |
| Horizontally virtualized filmstrip | PASS | A 200-photo test verifies a bounded rendered window and distant current selection |
| Original/edited comparison state | PASS | Original streams by catalog ID; empty edited pane is explicitly labeled and tested |
| Metadata, optional subject, many tags, conditions, and draft presets | PASS | API persistence tests and UI autosave test |
| Keyboard navigation, filters, review actions, and status | PASS | UI interaction tests, implemented controls, and owner usability review |
| Unsaved-change recovery | PASS | Tests cover failed-save reload recovery and text entered while a save is in flight |
| Precise GPS and internal path privacy | PASS | API test confirms detail output omits coordinates, hashes, EXIF snapshot, and filesystem paths |
| Representative owner catalog import | PASS | Separate ignored Phase 02 catalog imported 20 direct-phone photographs with 0 errors; no Phase 01 evidence catalog was changed |
| Owner visual/usability review | PASS | Owner reported the cleaned 20-photo workstation looks correct and confirmed updates persist |
| Windows/Linux CI matrix | NOT_RUN | Workflow is updated; remote CI cannot run until the owner commits and pushes |

## Implementation

Migration `002_review_ui.sql` adds metadata review state, the review timestamp, three explicitly draft presets, and per-photo review drafts. It does not create analysis runs, compiled prompts, jobs, edits, or exports. Existing catalogs migrate from schema version 1 to 2 and fresh catalogs apply both migrations.

The local FastAPI service owns SQLite and media access. It lists/filter-supporting summaries, returns a privacy-limited detail record, persists metadata and draft fields in one transaction, reports revision conflicts with HTTP 409, updates presets with versions, and serves thumbnail/original bytes by catalog ID. The detail response exposes `gps_present` only; it omits precise coordinates, original paths, managed paths, source hashes, raw EXIF, and thumbnail disk paths. CORS is limited to local Vite development origins. When `frontend/dist` exists, the same local service serves the built workstation.

The React/TypeScript workstation uses a fixed split comparison with a top filmstrip, full contact sheet, filters, keyboard navigation, and a metadata panel. The filmstrip windows its DOM items and scrolls the current selection into view. Autosave waits 700 ms, displays text status, uses an expected revision to reject stale writes, and stores unsaved per-photo form data in local browser storage. Navigation attempts a save first and stays on the current item if saving fails. An edit changes an unreviewed photo to in progress; reviewed state remains an explicit action. Placeholder suggestion and allowance fields are inert metadata in this phase and make no provider call.

The frontend uses exact npm versions and the backend uses direct and transitive Python pins. `scripts/setup_env.py` creates/updates only `.venv`, checks the locked Python packages, requires Node.js 22 or newer, runs `npm ci`, and validates the npm tree. CI recreates this environment on Windows and Linux before Python tests, frontend tests, and the production build.

## Files changed

- Backend: `backend/catalog/migrations/002_review_ui.sql`, `backend/review/`
- Frontend: `frontend/` source, tests, exact package lock, and Vite/TypeScript configuration
- Tests: `tests/test_review_api.py`, schema expectation updates in `tests/test_catalog.py`
- Environment/CI: `requirements.in`, `requirements.lock`, `scripts/setup_env.py`, `.github/workflows/catalog.yml`, `.gitignore`
- Documentation: README, architecture/schema/data/testing/UI/decision documents, Phase 01 closure, Phase 02 review guide, and this report

Private photos, SQLite files, thumbnails, `node_modules`, and built output remain ignored.

## Environment and tests

Executed locally on Windows with Python 3.13.5 from `.venv` and Node.js 24.14.0.

| Command | Result |
| --- | --- |
| `python scripts/setup_env.py` | PASS; canonical `.venv`, locked Python dependencies, Node 24.14.0, exact npm tree |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | PASS; 19 tests, 1.869 s on the final run |
| `npm --prefix frontend test` | PASS; 2 test files, 6 tests, 5.28 s |
| `npm --prefix frontend run build` | PASS; TypeScript checks and Vite 8.3.5 production build; 238.69 kB JS and 10.10 kB CSS before gzip |
| `git diff --check` | PASS; line-ending conversion warnings only |

Initial failures were corrected and are retained here rather than hidden:

- The first Python run had three failures: two Phase 01 tests still expected schema version 1, and privacy filtering short-circuited after removing latitude so longitude remained. Expectations and explicit field removal were corrected.
- The first UI run had four failures because jsdom does not implement `scrollTo`. The component now uses a compatible fallback. One later UI test used an ambiguous query; it was scoped to the contact-sheet dialog.
- Early builds exposed missing Vite client types, CSS typing, and config typing. The TypeScript configs and Vitest config import were corrected.
- The first setup-script edit had a missing parenthesis and failed immediately. It was corrected before the successful setup run.
- The first 200-photo filmstrip test expected jsdom to emit a browser scroll event automatically and its mock did not satisfy both DOM overloads. The test now emits the event explicitly and the final frontend test/build runs pass.

No automated test called an external service, uploaded a photograph, or generated/edited an image. Automated behavior tests do not establish visual correctness.

## Private sample review and safety

The ignored `data/phase02-review/` and catalog directory were explicitly created. A reference-mode import used the same 20 direct-phone JPEG sources previously reviewed in Phase 01 and reported 20 imported, 0 existing, and 0 errors. This created a separate schema-v2 catalog and thumbnails without changing the Phase 01 evidence catalog. No paid processing, cloud operation, destructive operation, or source mutation was authorized or performed.

A local server was started against this catalog. The available computer-use browser could not be bound because its current URL could not be determined confidently, so automated visual inspection stopped at that safety boundary. No visual PASS is inferred from unit tests. The owner procedure supplies the remaining visual, keyboard, persistence, failed-save recovery, privacy, and before/after source-hash checks.

During owner review, the workstation showed 40 thumbnails for 20 files. Read-only diagnosis found 40 distinct source paths but only 20 content hashes: the initial Phase 2 catalog referenced the Phase 1 review input, then the same bytes were imported from the Phase 2 review input. This is valid ingestion behavior because identical bytes at different paths are retained as duplicate candidates, but it was incorrect review-catalog preparation.

With owner authorization, a timestamped SQLite backup was written under ignored `data/phase02-review/backups/`. The 20 pairs were consolidated transactionally, retaining the records with substantive review metadata, moving any non-conflicting tags/drafts, pointing retained records to the Phase 2 sources, and removing the redundant test records. Final verification found 20 photos, 20 unique hashes, no duplicate links, matching source hashes, no foreign-key errors, and 20 source/thumbnail preflight results `OK`. The guide now warns against importing the same content from a second path and requires checking an existing catalog before import.

## Risks and deferred work

- **Owner follow-up:** broader subjective performance with a full ~200-photo catalog can still be revisited, but the owner accepted the current workstation and persistence behavior.
- **Performance evidence:** the filmstrip has deterministic 200-item windowing coverage, but browser memory and subjective responsiveness on the owner's full catalog are manual checks.
- **Single-user concurrency:** optimistic revisions prevent silent stale overwrites. There is no multi-user merge UI because the product is local and single-user.
- **Draft preset language:** the three initial texts are clearly marked draft and editable; final wording requires owner review before prompt assembly.
- **Phase boundary:** there is no AI analysis, prompt compilation, editing, version approval, or export in Phase 02. The empty edited pane is intentional.

## Reproduction and handoff

Follow [the Phase 02 owner review](../docs/PHASE_02_REVIEW.md) to reproduce the accepted checks. The owner manually committed Phase 02 as `9f88647`, confirmed that updates save correctly after duplicate-catalog cleanup, accepted the current UI, and explicitly authorized Phase 03. Phase 03 branched from that approved commit.
