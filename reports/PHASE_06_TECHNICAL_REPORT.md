# Phase 06 technical report — approved export, audit and usability

- Branch: `dev/v1-phase-06-export`
- Baseline commit: `ef163e1` (`changes to layout`) on the clean Phase 05 branch
- Date: 2026-11-01
- Working tree: all Phase 06 changes unstaged and uncommitted for owner review. The agent did not stage, commit, merge or release.
- Owner acceptance: pending real sample review.

## Scope and acceptance

| Check | Status | Evidence |
| --- | --- | --- |
| Approved-only website collection | PASS on synthetic data | Pending and rejected versions excluded; export requires an owner approval event and a successful job tied to the website profile. |
| No extra website resize | PASS on synthetic data | Export image bytes, SHA-256 and dimensions equal the approved version; only a separate thumbnail is encoded. |
| Privacy and manifest | PASS on synthetic data | Exported JPEG and thumbnail have no EXIF; manifest has no private GPS, raw EXIF, original filename/path, or unconfirmed tags. Editorial city/country appear only when both fields are present. |
| Cost report and file audit | PASS on synthetic data | Editing/analysis estimates, known actuals and unknown counts are separated. Audit detects changed bytes, missing files, malformed manifests and orphan files without deletion. |
| Data recovery | PASS on synthetic data | A pre-migration SQLite backup preserves schema 7; an isolated restore with copied media passes preview and audit. |
| Real owner photo batch, visual quality and publication review | NOT_RUN | Owner must inspect the real approved collection using `docs/PHASE_06_REVIEW.md`. |
| Windows/Linux CI | NOT_RUN remotely | Workflow targets the Phase 06 branch with pinned `.venv` setup; local verification was Windows only. |

## Implementation

Migration `008_exports.sql` records immutable export receipts and per-item approved-version/file identity. `backend/review/export.py` validates the source hash, selected profile and job, owner approval event, approved JPEG hash, dimensions and metadata policy before copying. It publishes a new UUID collection under the catalog's `exports/` folder, with byte-identical website JPEGs, 320 px thumbnails, a JSON manifest and a JSON cost report. No original, approved version or earlier export is overwritten. Failed staging is retained for audit rather than silently deleted. `backend/review/export_cli.py` provides `backup`, `audit`, `preview` and explicit `export --authorized`; the backup uses SQLite's online backup API without first migrating the source. The FastAPI endpoints and the new **Export** tab expose preview, current-run authorization, export, report downloads and read-only audit. CI branch targeting and governing docs were updated. No dependencies, model files or provider settings changed.

The export manifest uses current owner-entered or explicitly accepted editorial city/country when both exist. It includes confirmed tags, reviewed description and subject, approved version ID/hash, dimensions and relative exported paths. It omits precise GPS, raw EXIF, source paths, source filename and unaccepted suggestions. The cost report includes all editing and analysis attempts through export creation, including rejected/failed work, and marks actual amounts that were not reported by a provider as unknown. It is a planning/accounting report, not a spending cap.

## Verification performed

| Command | Result |
| --- | --- |
| `.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve(); print(sys.executable)"` | PASS; selected interpreter was repository `.venv`. |
| `.venv\Scripts\python.exe -m unittest discover -s tests -p test_export.py -v` | PASS after closing synthetic test SQLite connections; 3 Phase 06 tests at that stage. |
| `.venv\Scripts\python.exe -m unittest discover -s tests -q` | PASS final run; 59 tests, including five Phase 06 export tests. |
| `npm test -- --reporter=dot` in `frontend/` | PASS final run; 15 tests across 3 files. |
| `npm run build` in `frontend/` | PASS final run; TypeScript and production Vite build. |
| `.venv\Scripts\python.exe -m backend.review.export_cli --help` | PASS; preview, export, audit and backup commands exposed. |
| `git diff --check` | PASS; only Git LF-to-CRLF notices on this Windows checkout. |

The first full backend run after migration 008 failed five existing schema-version assertions still expecting 7. They now expect 8, and the full suite passed. The first focused export run passed its assertions but Windows temporary-directory cleanup failed because three test SQLite connections were left open by `with connect(...)`; those connections now close explicitly, and the focused and full suites passed. The first frontend run failed one keyboard tab-cycle assertion because Editing now advances to the new Export tab; the test now checks the full cycle and passed. No paid AI call, model download, cloud upload, large batch, real export or destructive cleanup was run. No test source photograph was modified.

## Risks and handoff

The real catalog may contain missing/changed originals or approved outputs that block a complete export; the preview reports the offending ID and refuses a partial collection. Audit can report orphaned or failed staging files but deliberately does not delete them. SQLite backup alone cannot restore generated media or externally referenced originals. Real captions, people, locations, rights and image quality require owner inspection. The Export tab adds one work-area tab; its usability at the owner's exact window size has not been visually accepted. No claim of Phase 06 completion or publication readiness is made from automated checks alone.

The earlier local review server on port 8001 was stopped before handoff so the owner can take a pre-migration SQLite backup before starting Phase 06 code. No real catalog migration was run in this development session.

Follow `docs/PHASE_06_REVIEW.md` from a fresh shell: stop the server, back up the existing SQLite catalog before migration, audit and preview, inspect a varied real sample, authorize one export, compare exported JPEGs with approved versions and inspect manifest/privacy/cost files. Record sample IDs, counts, hashes and visual findings privately. The owner then reviews this unstaged diff and manually stages/commits accepted changes; no merge or release was performed.

After owner feedback, the Phase 06 guide also gained explicit PowerShell and Linux commands to build `frontend/dist`, start the canonical `.venv` review server, open the matching browser URL, and stop it. The guide's `npm --prefix frontend run build` command passed from the repository root on Windows, and the required catalog, `.venv` interpreter, and `frontend/package.json` input checks passed. The server was not started, so no real catalog migration was triggered. Python and frontend tests were not rerun for this documentation-only addition.
