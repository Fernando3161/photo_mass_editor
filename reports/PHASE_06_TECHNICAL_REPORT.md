# Phase 06 technical report — approved export, audit and usability

- Branch: `dev/v1-phase-06-export`
- Baseline commit: `ef163e1` (`changes to layout`) on the clean Phase 05 branch
- Date: 2026-11-01
- Working tree: the owner's earlier Phase 06 work is committed at `a592fa7`; the subsequent canonical-layout changes are unstaged and uncommitted for owner review. The agent did not stage, commit, merge or release.
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

Migration `008_exports.sql` records immutable export receipts and per-item approved-version/file identity. `backend/review/export.py` validates the source hash, selected profile and job, owner approval event, approved JPEG hash, dimensions and metadata policy before copying. It publishes a new UUID collection under `data/exports/` for the canonical catalog, with byte-identical website JPEGs, 320 px thumbnails, a JSON manifest and a JSON cost report. No original, approved version or earlier export is overwritten. Failed staging is retained for audit rather than silently deleted. `backend/review/export_cli.py` provides `backup`, `audit`, `preview` and explicit `export --authorized`; the backup uses SQLite's online backup API without first migrating the source. The FastAPI endpoints and the new **Export** tab expose preview, current-run authorization, export, report downloads and read-only audit. CI branch targeting and governing docs were updated. No dependencies, model files or provider settings changed.

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

At the initial Phase 06 handoff, the local review server on port 8001 was stopped for a pre-migration backup. The later canonical-layout migration and verification are recorded below.

Follow `docs/PHASE_06_REVIEW.md` from a fresh shell: stop the server, back up the existing SQLite catalog before migration, audit and preview, inspect a varied real sample, authorize one export, compare exported JPEGs with approved versions and inspect manifest/privacy/cost files. Record sample IDs, counts, hashes and visual findings privately. The owner then reviews this unstaged diff and manually stages/commits accepted changes; no merge or release was performed.

After owner feedback, the Phase 06 guide gained explicit PowerShell and Linux commands to build `frontend/dist`, start the `.venv` review server, open the matching browser URL, and stop it. The guide's `npm --prefix frontend run build` command passed from the repository root on Windows. The later canonical-layout work changed those commands to use `data/catalog`.

## Canonical data layout and export usability correction

The owner identified that exporting beneath `data/phase04-review/catalog` carried a development path into the final product. The canonical operational root now has `data/input`, `data/catalog`, `data/exports`, `data/backups`, `data/evidence`, and `data/models`. Application and CLI defaults use `data/catalog`; internal derivatives remain relative to that catalog, while approved collections resolve to the sibling `data/exports`. Legacy catalog exports remain readable through their old root. `scripts/migrate_data_layout.py` first inspects the source, then on `--apply` writes a timestamped SQLite backup, copies every source image and recorded artifact with SHA-256 verification, updates the 20 original paths in the copied database, publishes the new catalog last, and runs a full audit and approved-version preview. It never deletes or renames the old phase directories. The existing owner export collection was copied to the canonical exports folder; no new paid edit or image export was run during migration.

The Export tab now displays the full local directory path as a prominent control. Clicking it calls a local endpoint restricted to a completed export record and opens that folder in File Explorer on Windows or the system file manager on Linux. Manifest and cost-report links have high-contrast styling, spacing, and visible focus states. The backend accepts the folder action only with its explicit local-action header and never accepts an arbitrary browser-supplied filesystem path.

A read-only recent-exports endpoint and tab section keep the owner's existing export available after a browser refresh. The frontend can open that folder and download its reports without creating another collection. After the final build, the canonical port-8000 server was restarted with no active edit jobs. `GET /api/export/history` returned the migrated four-image collection under `data/exports`, and the root page served the new frontend bundle.

Actual migration on this Windows workspace: the read-only plan found 20 photos, all 20 original files beneath the former Phase 04 input, 39 catalog artifact files, one existing export with 10 files, and no external originals. The copy created `data/backups/catalog-before-layout-20261101T205644Z-fc7b135b.sqlite`. The canonical audit found 49 referenced files, zero missing, changed, source, orphan, manifest, or cost-report issues. The canonical preview found the same four approved versions. The legacy catalog and input still exist for recovery. A subsequent live API check on the canonical server at port 8000 returned 20 photos, four approved versions, the existing four-item manifest, HTTP 200 for the page, and zero audit issues. A live explicit folder-open request returned `opened: true`. Before switching servers, the old catalog had no QUEUED or RUNNING edit jobs; its port-8000 process was stopped, and the canonical server was started on port 8000.

After stopping the old server, a read-only comparison checked all 21 application tables between old and canonical SQLite databases, normalizing only the intended `photos.original_path` rebase. It found no row mismatches. This check limits the risk of edits having landed in the legacy catalog during the transition.

Verification after this correction: `.venv\Scripts\python.exe -m unittest discover -s tests -q` passed 61 tests; `npm test -- --reporter=dot` passed 15 frontend tests; `npm run build` passed. Synthetic tests cover moving a catalog with an existing export, rebasing a referenced original into `data/input`, preserving source hashes, routing a new export to `data/exports`, requiring the folder-open action header, and listing completed exports. `git diff --check` found no whitespace errors. The first new migration test failed only because Windows rendered the same temporary path in long and short forms; the test now compares resolved paths, and the focused suite passed all seven tests. An initial PowerShell one-liner to query active jobs failed because its nested quotes were parsed as commands; a here-string run through `.venv` succeeded and found no active jobs. No Linux run or owner visual check of the new links was performed.
