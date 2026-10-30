# Phase 03 — Analysis and prompt assembly technical report

- Date: 2026-10-30
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
| Secret isolation | PASS | No credential field or provider secret is present in frontend code/responses |
| Real provider analysis | NOT_RUN | No provider/model/pricing decision or current paid-run authorization; default provider fails closed without a call |
| Owner prompt workflow review | NOT_RUN | Follow `docs/PHASE_03_REVIEW.md` |
| Remote Windows/Linux CI | NOT_RUN | Requires owner commit and push |

## Design and implementation

Migration `003_analysis_prompts.sql` adds analysis provenance, immutable compiled-prompt versions, approved constraints, explicit semantic-change consent, and the adopted analysis-run link. Provider raw output stays server-side. Browser prompt snapshots omit the source hash.

The analysis service accepts at most 25 distinct catalog IDs, calculates cached and billable counts before a run, requires an explicit authorization boolean for each execution request, and caches successful results by photo source hash plus provider configuration signature. A force refresh still requires authorization. Provider context excludes precise GPS, raw EXIF, and filesystem paths. The default provider is deliberately unavailable, so this branch cannot accidentally make a live request. Tests inject a deterministic fake provider; they make no network call.

Prompt assembly is deterministic and records policy/compiler versions plus a complete input snapshot. It keeps AI suggestion, owner instruction, approved constraints, preset version, tags, subject, allowance, and consent distinct before assembly. Conflicting preserve/change instructions and allowance above 3 without consent block compilation. Compilation and every owner edit create immutable numbered rows. Approval is explicit and fails when the photo or draft has changed.

The workstation adds cost preview, current-run authorization, suggestion adoption, approved constraints, semantic consent, compiled prompt editing, immutable version history, and approval. It never asks for or stores a provider credential in browser code.

## Files changed

- Schema/backend: migration `003_analysis_prompts.sql`; analysis provider/orchestrator and prompt compiler modules; review API/service extensions
- Frontend: Phase 3 panel, draft consent/constraints, analysis and prompt API/types/state, styling, and UI test
- Tests/CI: `tests/test_analysis_prompts.py`, schema expectation/privacy updates, and Phase 3 workflow naming/branch
- Documentation: README, architecture/schema/data/testing/UI/decision contracts, Phase 2 approval closure, Phase 3 review guide, and this report

Private catalog backups, source photographs, SQLite WAL files, and generated frontend output remain ignored.

## Tests

| Command | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | PASS; 25 tests, 4.015 s |
| `npm --prefix frontend test` | PASS; 2 files, 7 tests, 7.03 s |
| `npm --prefix frontend run build` | PASS; TypeScript and Vite build, 245.47 kB JS and 10.43 kB CSS before gzip |

The first full Python run after migration had three expected schema-version assertion failures, then one repeated idempotency assertion still expected version 2. All were updated to version 3; the final run passed. No source photo, cloud service, or paid endpoint was used.

## Private catalog migration smoke check

Before upgrading the ignored owner catalog, an integrity-checked SQLite backup was created at `data/phase03-review/backups/catalog-before-phase03-20261030T144122Z.sqlite`. Migration advanced schema 2 to 3 while preserving 20 photo rows; `PRAGMA integrity_check` returned `ok` and the foreign-key check returned no errors. A local API smoke check returned 20 photos, omitted source hashes/private coordinates, and returned HTTP 503 with “No analysis provider is configured; no API call was made” for cost preview. No prompt row or analysis run was created by this smoke check.

## Risks and deferred work

- A production analysis provider, exact model, current pricing, credential source, and live response schema remain undecided. These require evidence and explicit owner authorization before any live test.
- Natural-language conflict detection covers known preserve/change targets and explicit semantic consent. It does not prove that every possible instruction is logically consistent.
- Cost estimates come from the configured provider adapter and are estimates, not billing guarantees.
- Prompt approval authorizes a prompt record for a future job; it does not authorize or execute editing. Phase 4 retains its own current-run authorization gate.

## Handoff

Follow [the Phase 03 owner review](../docs/PHASE_03_REVIEW.md). It creates the backup folder, verifies a SQLite backup before migration, runs all local checks, and reviews compilation/versioning without a real AI call. Do not begin Phase 04 until the owner approves this phase. The owner manually stages and commits accepted changes.
