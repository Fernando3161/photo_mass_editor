# V2 Priority 2 technical report — selection and batch workflow

Date: 2026-11-02. Branch: `dev/v2-02-batch-workflow`. Baseline: `6754004` on the owner-completed Priority 1 branch. All Priority 2 changes are unstaged and uncommitted for owner review. The owner stated Priority 1 complete and requested Priority 2. No merge, release, paid provider run, cloud upload or private photo batch was performed.

## Scope and acceptance

| Check | Result | Evidence and limit |
| --- | --- | --- |
| Contact-sheet selection and recommendation grid | PASS in DOM/code | Selection controls, batch thumbnails, per-photo operations, targets and skipped reasons; frontend test verifies two-photo selection and preview-before-run. Real 200-photo usability is unmeasured. |
| Named recipes and per-photo overrides | PASS on synthetic fixtures | Migration 011 and local batch service store immutable named settings, per-photo recipe snapshots and exposure/recommendation overrides. A changed setting invalidates the preview signature. |
| Bounded local batch, authorization, cancellation, failure isolation, restart | PASS on synthetic fixtures | Existing two-worker executor, explicit current-run authorization, independent local job/version receipts, queued cancellation, queued batch resume, running-job fail-on-restart; tests cover a failed render beside a successful render. Real machine performance is unmeasured. |
| Pending versions and explicit review | PASS in existing/new automation | Local jobs still create PENDING versions. Approve-and-next / reject-and-next controls and keys are scoped to the visible editing tab. Existing review/replacement/export tests remain green. Visual quality is unverified. |
| Generative batch preparation | PASS on synthetic fixtures/DOM | Previous/proposed text and per-photo acknowledgment precede immutable prompt compilation and explicit approval. Approval rechecks revisions, constraints, allowance and semantic consent. No image job is created by prompt preparation. Paid execution retains the separate maximum-20-photo authorization path. |
| 20-photo owner pilot, click count and 200-photo benchmark | NOT_RUN | Private owner photos, visual judgment and actual-machine measurements are required. Follow `docs/V2_PHASE_02_REVIEW.md`. |
| Linux runtime/CI | NOT_RUN locally | The host is Windows. The CI branch trigger now includes Priority 2; remote CI result requires owner push/PR. |

## Design and data impact

`011_local_batches.sql` creates `named_local_recipes` and `local_batches` and links local jobs to batches. Existing source paths and approved image bytes are untouched. Each batch item uses the V2 Priority 1 source hash/profile/recipe/job/version chain. The batch preview signs source identity, profile, eligibility, settings and replacement intent; the client receives no source hash or private path. The API requires explicit current-run authorization before queueing and persists selection/skipped reasons. Queued jobs can resume after restart because local processing is deterministic and unpaid. Interrupted running jobs fail for inspection; single-photo queued jobs retain prior fail-on-restart semantics. Cancellation changes queued jobs only. Successful jobs still produce private PNG masters and website JPEGs requiring explicit owner image approval.

`prompt_batch.py` previews individual immutable prompt text against the prior version and requires acknowledgment of each eligible photo. A shared instruction is snapshotted per photo. Compiling/revising a new prompt revokes an older approval for that photo. Approval rechecks the current source/draft/profile revisions and required constraint, profile, allowance and consent lines; explicit scene removal/replacement/invention with zero allowance or absent semantic consent is blocked. The existing generative adapter still receives only the publication derivative, and image run authorization is unchanged. This is a bounded policy check, not proof that arbitrary natural language cannot express a conflict.

The frontend adds contact-sheet selection, a thumbnail recommendation grid, batch status/receipts, a recipe picker and per-photo override, separate prompt preparation, and single-photo approve/reject-and-next controls. The paid editor can use the first 20 selected photos. No new dependency was introduced; `requirements.in`, `requirements.lock`, `scripts/setup_env.py` and `frontend/package-lock.json` remain unchanged. CI uses the same canonical environment setup and now includes this branch in its push trigger. The layout migration accepts schema 11 catalogs.

## Exact command record

- `& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"`: PASS before project Python tests. The repository-local interpreter was used exclusively.
- `& .\.venv\Scripts\python.exe -m unittest discover -s tests -q`: first run FAIL, 70 tests: six schema-version expectations still read 10, two layout-migration tests rejected schema 11, and one restart test expected a queued single-photo job to fail. The first restart approach also left a worker holding a temporary catalog during cleanup. Corrected schema assertions and layout support, retained fail-on-restart for single-photo jobs, resumed only queued batch jobs, and closed every new SQLite connection. Final run PASS, 77 tests in 26.070 seconds.
- `& .\.venv\Scripts\python.exe -m unittest tests.test_v2_batch -q`: first run FAIL on Windows temporary-catalog cleanup because two new test connections were not closed. Closed them; rerun PASS, 3 tests. Later expanded to seven focused tests; included in the final 77-test suite.
- `npm test` in `frontend/`: PASS, 17 inherited tests before new UI cases; final PASS, 20 tests across three files, including active-tab scoping of approve-and-next.
- `npm run build` in `frontend/`: PASS, TypeScript checks and Vite production build before and after final UI changes.
- `Get-Content .github/workflows/test.yml`: FAIL because that path does not exist; corrected to `.github/workflows/catalog.yml` for CI review. No runtime impact.
- No `scripts/setup_env.py` installation was needed because dependencies did not change and the existing canonical `.venv` passed interpreter verification. No pytest, external paid service, model download or large batch was run.

## Owner review and limits

The synthetic tests verify state transitions and source hashes but cannot validate photographic quality, full-size memory use, real batch throughput, cancellation timing on large originals, accessibility in a real browser, or the under-two-hour 200-photo target. The UI was checked by DOM tests and production build, not a live visual browser session. The owner should back up the private catalog, follow `docs/V2_PHASE_02_REVIEW.md` on roughly 20 varied photographs, record actual clicks/time and image acceptance, verify original hashes, and decide whether this branch is acceptable before staging, committing, merging or starting Priority 3. Only the owner stages and commits changes.

Acceptance recommendation: **INCOMPLETE** until the owner pilot and visual/performance review are recorded. Engineering implementation is ready for owner review.
