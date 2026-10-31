# Phase 03 — Analysis and prompt assembly technical report

- Date: 2026-10-31
- Branch: `dev/v1-phase-03-prompts`
- Owner-approved Phase 02 baseline: `9f88647` (`working ui for editing`)
- Owner/reviewer: project owner; Phase 03 review pending
- Commit state: Phase 03 changes are unstaged and uncommitted
- Recommendation: **READY FOR OWNER REVIEW; NOT YET APPROVED**

## Scope and acceptance

| Check | Status | Evidence |
| --- | --- | --- |
| Explicit per-run analysis authorization | PASS | Unauthorized API request returns 403 before provider invocation |
| Bounded analysis batch | PASS | Request model and service restrict distinct photo IDs to 1–25 |
| Cost preview and cache | PASS | Fake provider test covers billable/cached counts and exact estimate |
| Cache invalidation | PASS | Changed provider configuration signature creates a new run |
| Analysis provenance and raw-response isolation | PASS | Schema retains source/config/model/output/usage; API omits raw response and source hash |
| Editable suggestion, owner instructions, and constraints | PASS | Separate persisted draft fields and UI controls |
| Conflict resolution and semantic consent | PASS | Tests cover preserve/replace conflict and allowance above 3 |
| Versioned editable compiled prompt | PASS | Compile, owner edit, parent/version history, explicit approval, and stale invalidation tests |
| Publication-sized editing contract | PASS | Versioned JPEG/1600px profile is selectable, persisted, snapshotted into prompts, and reserved for immutable Phase 4 derivatives |
| Additional owner-requested presets | PASS | Migration 005 adds five editable choices; existing preset rows remain unchanged; museum preset selection is snapshotted into a compiled prompt |
| Secret isolation | PASS | No credential field or provider secret is present in frontend code/responses |
| Real provider analysis | NOT_RUN | No provider/model/pricing decision or current paid-run authorization; default provider fails closed without a call |
| Owner prompt workflow review | NOT_RUN | Follow `docs/PHASE_03_REVIEW.md` |
| Remote Windows/Linux CI | NOT_RUN | Requires owner commit and push |

## Design and implementation

Migration `003_analysis_prompts.sql` adds analysis provenance, immutable compiled-prompt versions, approved constraints, explicit semantic-change consent, and the adopted analysis-run link. Migration `004_publication_profiles.sql` adds immutable publication profiles, the selected draft profile, complete prompt profile snapshots, and the `publication_inputs` provenance table that Phase 04 will populate. It preserves older prompt history while revoking approval/readiness because those prompt texts predate the publication-input rule. Migration `005_add_review_presets.sql` inserts museum artwork, group photo, night architecture, food, and panoramic scene draft presets without changing the three existing records. Provider raw output stays server-side. Browser prompt snapshots omit the source hash.

The analysis service accepts at most 25 distinct catalog IDs, calculates cached and billable counts before a run, requires an explicit authorization boolean for each execution request, and caches successful results by photo source hash plus provider configuration signature. A force refresh still requires authorization. Provider context excludes precise GPS, raw EXIF, and filesystem paths. The default provider is deliberately unavailable, so this branch cannot accidentally make a live request. Tests inject a deterministic fake provider; they make no network call.

Prompt assembly is deterministic and records policy/compiler versions plus a complete input snapshot. It keeps AI suggestion, owner instruction, approved constraints, preset version, tags, subject, allowance, and consent distinct before assembly. Conflicting preserve/change instructions and allowance above 3 without consent block compilation. Compilation and every owner edit create immutable numbered rows. Approval is explicit and fails when the photo or draft has changed.

The owner selected an original-to-publication-input-to-AI-edit pipeline. `website-standard-v1` is JPEG, sRGB, maximum 1600-pixel long edge, quality 85, preserved aspect ratio, no upscaling, and stripped metadata. This choice follows the Turkey trip site's practical 1600-pixel publication scale while using JPEG so the owner can inspect files locally. The prompt states that the future editing adapter must use only the deterministic derivative and never the original. Phase 03 records this contract; Phase 04 implements and validates image derivation and editing execution.

The review canvas still displays the original photograph at its source resolution. This is intentional for inspection; it is not the generative editing input. The new presets are selectable from the existing database-backed menu. Their conservative draft wording can be edited and versioned by the owner before prompt approval.

The workstation adds cost preview, current-run authorization, suggestion adoption, approved constraints, semantic consent, compiled prompt editing, immutable version history, and approval. It never asks for or stores a provider credential in browser code.

## Files changed

- Schema/backend: migrations `003_analysis_prompts.sql`, `004_publication_profiles.sql`, and `005_add_review_presets.sql`; analysis provider/orchestrator and prompt compiler modules; review API/service extensions
- Frontend: Phase 3 panel, draft consent/constraints, analysis and prompt API/types/state, styling, and UI test
- Tests/CI: `tests/test_analysis_prompts.py`, schema expectation/privacy updates, and Phase 3 workflow naming/branch
- Documentation: README, architecture/schema/data/testing/UI/decision contracts, Phase 2 approval closure, Phase 3 review guide, and this report

Private catalog backups, source photographs, SQLite WAL files, and generated frontend output remain ignored.

## Tests

| Command | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | PASS; 27 tests, 3.382 s |
| `npm --prefix frontend test -- --run` | PASS; 2 files, 8 tests, 7.57 s |
| `npm --prefix frontend run build` | PASS; TypeScript and Vite build, 246.41 kB JS and 10.43 kB CSS before gzip |

During development, schema-version expectations and one frontend assertion were updated for the publication-profile contract. After migration 005, the first full Python run failed two catalog assertions still expecting schema 4; these were corrected to 5, and the second full run passed. The frontend tests and production build passed. No source photo, cloud service, or paid endpoint was used.

## Private catalog migration smoke check

Before upgrading the ignored owner catalog to the publication-profile contract, an integrity-checked SQLite backup was created at `data/phase03-review/backups/catalog-before-publication-profile-20261030T145316Z.sqlite`. Migration advanced schema 3 to 4 while preserving 20 photo rows. All 5 existing drafts were backfilled with `website-standard-v1`; one profile exists and `publication_inputs` correctly remains empty because Phase 03 performs no image processing. `PRAGMA integrity_check` returned `ok` and the foreign-key check returned no errors. An API smoke check returned 20 photos, the JPEG/1600px/quality-85 profile, and the selected profile in photo detail without exposing a source hash. The earlier schema 2-to-3 backup remains at `data/phase03-review/backups/catalog-before-phase03-20261030T144122Z.sqlite`.

Before applying migration 005 to the private catalog, a SQLite backup was created and integrity-checked at `data/phase03-review/backups/catalog-before-preset-expansion-20261031T155845Z.sqlite`. The local catalog advanced from schema 4 to 5 with 20 photo rows and eight presets. All three pre-existing preset records matched the backup byte-for-byte in their selected database fields, and `PRAGMA integrity_check` and `PRAGMA foreign_key_check` passed. These files remain ignored and private.

## Risks and deferred work

- A production analysis provider, exact model, current pricing, credential source, and live response schema remain undecided. These require evidence and explicit owner authorization before any live test.
- Natural-language conflict detection covers known preserve/change targets and explicit semantic consent. It does not prove that every possible instruction is logically consistent.
- Cost estimates come from the configured provider adapter and are estimates, not billing guarantees.
- Prompt approval authorizes a prompt record for a future job; it does not authorize or execute editing. Phase 4 retains its own current-run authorization gate.
- The 1600-pixel JPEG profile is a selected V1 publication target, not a claim that encoded byte size directly determines provider token cost. Exact cost behavior must be measured after a provider is selected.
- Publication derivative generation, EXIF stripping verification, provider-input path enforcement, raw-output retention, and output normalization are Phase 4 work and are not claimed as implemented here.
- The five new preset wordings remain drafts until owner visual and editorial review. Automated checks confirm selection and prompt snapshot behavior; they do not judge photographic quality.

## Handoff

Follow [the Phase 03 owner review](../docs/PHASE_03_REVIEW.md). It creates the backup folder, verifies a SQLite backup before migration, runs all local checks, and reviews compilation/versioning without a real AI call. Do not begin Phase 04 until the owner approves this phase. The owner manually stages and commits accepted changes.
