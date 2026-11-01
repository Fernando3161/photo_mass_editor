# Phase 04 — editing engine and versioning technical report

- Date: 2026-10-31
- Branch: `dev/v1-phase-04-processing`
- Owner-approved Phase 03 baseline: `3ae1a8d` (`modified for further presets.`)
- Commit state: Phase 04 code and trial documentation are in owner commit `46ce4e1`; this later phase-plan revision remains unstaged and uncommitted for owner review
- Owner/reviewer: project owner; both limited live edits completed and approved
- Owner decision: **PHASE 04 APPROVED** on 2026-11-01; the broader 20-photo walkthrough remains deferred as recorded below

## Scope and acceptance

| Check | Status | Evidence |
| --- | --- | --- |
| Immutable publication input before any generative edit | PASS | Synthetic 2000×1500 original yields separate 1600×1200 RGB JPEG; source SHA-256 unchanged; recorded source/profile/input hashes |
| Provider never receives the original | PASS | Fake provider and mocked OpenAI HTTP adapter observe only the publication-input path/bytes |
| Metadata and color policy | PASS | Output is JPEG with no EXIF/ICC/comment, no upscale, preserved aspect; embedded ICC is converted to sRGB and absent ICC is assumed sRGB |
| Local deterministic corrections | PASS | Brightness, contrast, color, sharpness, and median denoise operate on the derivative; outputs are distinct raw and normalized artifacts |
| Optional mask | PASS | Uploaded PNG requires matching derivative dimensions, alpha channel, and both transparent/opaque pixels; saved privately with hash |
| Jobs, bounded batch, and restart | PASS | At most 20 selected photos and two local workers; request keys are idempotent; concurrent claims produce one version; interrupted or queued paid calls require reauthorization |
| Failure and raw-attempt retention | PASS | Failed provider call retains job error, no approved version; successful raw bytes and normalized JPEG have separate immutable paths |
| Explicit review and retry guard | PASS | Versions start PENDING; approval/rejection writes review event; rejected output remains; identical rejected attempt is blocked without changed inputs or override; approved photos are skipped |
| Cost and API authorization | PASS | Default provider unavailable; per-run authorization and configured planning estimate/budget required before a paid job is queued; no live call in tests |
| Owner visual quality and new 20-photo walkthrough | NOT_RUN | The owner approved both limited live edited versions; the broader 20-photo walkthrough remains pending. Software tests cannot judge photographic fidelity. |
| First live OpenAI edit: 0/10 prompt-directed retouch | PASS | Owner-authorized job `c675c29b-22c7-41ca-abaa-4f59c7f2d6cd` succeeded; source, derivative, raw, and version hashes matched; the owner explicitly approved the new version after review. |
| Second live OpenAI edit: 2/10 Budapest Opera perspective and people removal | PASS | Owner-authorized job `a2cd22d3-0d65-4a65-9047-ed808d1b6711` succeeded; source and artifact hashes matched; the owner explicitly approved the version after visual review. |
| Remote Windows/Linux CI | NOT_RUN | Requires owner commit and push on this branch |
| Website export | NOT_RUN | Renumbered Phase 06 scope after the owner's local-prefill decision |

## Design and implementation

Migration `006_editing_jobs.sql` adds `masks`, `edit_batches`, and `edit_jobs` and connects generated `image_versions` to jobs and publication inputs. Existing photos, prompts, profile rows, and preset rows are preserved. Job receipts retain model, settings, hashes, status, errors, timestamps, planning estimate, usage, and actual cost if a provider returns one. The provider adapter currently returns usage but not an invoice amount, so actual OpenAI cost remains unknown in the application until reconciled against the account.

The image pipeline verifies the original hash before derivation, applies EXIF orientation, converts embedded ICC profiles to sRGB or records the sRGB assumption, resizes without upscaling to the selected profile, strips metadata, and writes a new file without replacing an existing artifact. Reuse requires the stored derivative hash to match. The worker checks the derivative, current prompt, source hash, and optional mask again before execution. Provider output is saved as an immutable raw attempt and normalized to a separate JPEG. An inconsistent output aspect ratio fails rather than cropping the scene silently.

The default engine uses local Pillow corrections. The optional OpenAI Images edit adapter uses `gpt-image-2.5-sunburst` by default and `gpt-image-2.5-flare` when selected by server environment. The model and endpoint shape follow [official OpenAI image-edit documentation](https://developers.openai.com/api/reference/python/resources/images/methods/edit). The adapter is disabled without both a server-side API key and a positive per-image planning amount. The browser has no credential field. The run budget is an estimate gate, not an account spending cap. Every live run still needs a separate owner click. A cancelled queued job never calls a provider; a running provider call cannot be reliably cancelled. Startup resumes queued local corrections but fails queued or interrupted paid jobs to prevent automatic repeat billing.

The UI previews eligibility and each prompt, offers a current photo or first-20-visible selection, shows job receipts, compares original with a chosen version, downloads a selected version, and records approval/rejection. Masks can be prepared from the publication input in an external editor and uploaded as PNG. An in-app brush editor is not claimed. Approved-only export and approved-version promotion are deferred.

A private root-level `openAI.env` file and its `.gitignore` entry appeared during initial Phase 04 work. It was not read, modified, or loaded then. In the later owner-requested configuration update, the server loads only `config/openAI.env` (when present), with process environment values taking precedence. The old root-level private file remains untouched and is not loaded. The commit-safe `config/openAI.example.env` documents the required fields without secrets.

No dependency versions changed. The existing locked Pillow, FastAPI, and frontend dependencies support this implementation. Setup, local tests, and CI continue to use the canonical `.venv` procedure; no alternative environment was created.

## Files changed

- Backend/schema: migration `006_editing_jobs.sql`; `backend/review/image_pipeline.py`, `editing.py`, `openai_edit.py`; review API, photo detail, and server entrypoint updates.
- Frontend: edit panel, version comparison, API/types, styles, and focused UI test.
- Tests: `tests/test_editing.py` and schema-version assertions updated to version 6.
- Documentation/CI: Phase 04 review guide, architecture, schema/data/editing/testing contracts, README, decision log, Phase 03 approval closure, workflow branch, and this report.

## Tests and failures

| Command | Final result |
| --- | --- |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | PASS; 38 tests, 8.248 s |
| `npm --prefix frontend test -- --run` | PASS; 2 files, 9 tests, 6.52 s |
| `npm --prefix frontend run build` | PASS; TypeScript and Vite build, 255.33 kB JS and 11.40 kB CSS before gzip |
| Migration smoke on ignored SQLite backup | PASS; schema 5→6 with 20 photos, 8 presets, 7 prompt versions unchanged; integrity and foreign-key checks pass |

The first full Python run after migration 006 failed four assertions expecting schema version 5; those expectations were updated to 6. An initial frontend test run failed five assertions because the mock did not answer the new `/edits` request and a prior text query became ambiguous; the mock and assertion were corrected. A documentation patch initially targeted nonexistent `.github/workflows/phase-tests.yml`; the actual workflow is `.github/workflows/catalog.yml`, and the patch was applied there. A read of nonexistent `.env.example` failed; no secret file was introduced. All final listed tests passed. No external paid service was called.

## Private catalog migration smoke

The ignored owner catalog was backed up with SQLite's backup API to `data/phase04-review/backups/catalog-before-phase04-20261031T165021Z.sqlite` and verified with `PRAGMA integrity_check`. Migration 006 was applied to a separate ignored copy under `data/phase04-review/migration-smoke/`, leaving the owner catalog at schema 5. The copy advanced to schema 6 while retaining 20 photo rows, 8 preset rows, and 7 compiled prompt rows. Integrity and foreign-key checks passed. No source photograph or private image was processed during this smoke check.

## Risks and deferred work

- The owner must visually inspect real edited images and source hashes using the Phase 04 guide. Automated tests prove contracts on synthetic fixtures, not visual quality.
- Both owner-authorized live runs confirm access to `gpt-image-2.5-sunburst` for this account. Larger batch behavior and exact per-request billing reconciliation remain untested. The owner should inspect every result before approval.
- The configured per-image estimate and run budget are application gates. They cannot stop a provider from charging a different amount for a call already submitted. The owner should check actual Platform usage after the trial.
- Some provider outputs may change aspect ratio or add semantic content despite prompt or mask instructions; the pipeline rejects an aspect mismatch, while semantic authenticity still needs human review.
- Replacing an already approved version requires a future explicit promotion design. Default jobs skip approved photos and never overwrite an approval.
- Crashes between immutable file creation and SQLite commit can leave unreferenced files. Recovery never deletes them automatically; an orphan audit remains to be added in Phase 06.
- The optional mask is uploaded from an external editor. A brush/mask editor inside the workstation remains deferred.

## Handoff

Follow [the Phase 04 owner review](../docs/PHASE_04_REVIEW.md) from a fresh PowerShell or Linux shell. It creates ignored directories, verifies inputs, backs up an existing catalog before migration, runs local checks, imports a new batch, compares source hashes before and after, retrieves edited JPEGs, and separates an optional one-photo paid trial. The owner has approved Phase 04; the next phase is local catalog prefill under the revised project plan. The owner still reviews, stages, and commits this documentation revision before Phase 05 starts.

## First two-image trial guide addendum (2026-11-01)

Added [the first two-image trial guide](../docs/FIRST_TWO_IMAGE_TRIAL.md) at the owner's request, then corrected it after the owner clarified that **both** images must use the OpenAI image-edit API. The owner further clarified that no PNG mask will be made or uploaded: the first is a prompt-directed 0/10 retouch, and the second is a separately authorized 2/10 perspective request. Updated the allowance policy and UI wording to distinguish reimagining from API usage. The existing adapter already omits the optional mask field when none is uploaded, so no application code change was needed for the owner's no-PNG workflow. Updated the fake-provider test fixture to 0/10; its optional-mask test still verifies that path separately. No dependency specification or environment setup procedure changed. Owner visual review and both limited live OpenAI calls remain **NOT_RUN**; no paid service was called by the agent.

Correction verification on 2026-11-01: `.venv\Scripts\python.exe -m unittest discover -s tests -v` **PASS** (38 tests, including the final 0/10 masked-provider assertion); `npm --prefix frontend test -- --run` **PASS** (2 files, 9 tests); `npm --prefix frontend run build` **PASS**. `git diff --check` for the changed tracked policy, UI, and test files and a balanced Markdown-fence check for the new guide also passed. No live API or owner visual test ran.

## Private server configuration addendum (2026-11-01)

At the owner's request, added a commit-safe `config/openAI.example.env`, ignored `config/openAI.env`, and server-only startup loading in `backend/review/local_config.py` and `backend/review/__main__.py`. The private file supplies `OPENAI_API_KEY`, `PHOTO_EDIT_MODEL`, and `PHOTO_EDIT_PLANNING_COST_USD`; it is read only by the `backend.review` server entrypoint. The old root-level `openAI.env` was not read or moved. Environment variables override file values. Missing config leaves local-only startup available; a copied template with unreplaced placeholders stops startup with a field-specific error. No dependency changes were needed. Updated the README and both Phase 04 owner guides. No API call or image processing was authorized or run for this change.

An initial read-only PowerShell metadata command failed to parse because `"$n:"` was interpreted as an invalid variable reference; the command did not execute or print any secret. The owner then specified the exact template layout, so no inspection of the old secret file was needed.

Verification for this addendum: `.venv\Scripts\python.exe -m unittest discover -s tests -v` **PASS** (41 tests, including three new synthetic-only config tests). The interpreter was verified to belong to the repository `.venv`. `git check-ignore` confirmed `config/openAI.env` is ignored and `config/openAI.example.env` is not. Frontend tests/build were **NOT_RUN** for this addendum because no frontend files changed. A live startup with the owner's real key, image calls, and visual review remain **NOT_RUN** until the owner completes the private config and authorizes each run.

One verification command incorrectly used PowerShell's `-not` on the empty output of `git check-ignore -q`, causing a false failure even though the ignore rule was present. The corrected check used `$LASTEXITCODE`: `git check-ignore -v -- config/openAI.env` reported `.gitignore:237:/config/openAI.env`, and the example file was confirmed not ignored. Template placeholders were checked without reading any private config value.

## First owner-authorized live edit evidence (2026-11-01)

The owner ran one 0/10 prompt-directed OpenAI edit of the Budapest Parliament night photograph. Read-only inspection of the private catalog found batch `affce193-bc50-4c2b-8756-28b203697475` COMPLETED and job `c675c29b-22c7-41ca-abaa-4f59c7f2d6cd` SUCCEEDED with no error. The job used `gpt-image-2.5-sunburst`, an approved prompt version 2 saying `0 of 10`, and no uploaded mask. It ran from 15:00:40 to 15:01:02 UTC. The original remained a separate 4000×3000 JPEG with its recorded SHA-256 unchanged. The provider input was a 1600×1200 JPEG with no EXIF or ICC; the raw response was a distinct 1600×1200 PNG; the normalized publication version was a distinct 1600×1200 JPEG with no EXIF or ICC. All recorded source, input, raw, and version hashes matched the on-disk files, and the lineage IDs matched. Version `18f9197e-2917-42c9-9203-4bb3324e2bc2` began PENDING; the owner explicitly changed it to **APPROVED** at 15:05:09 UTC, with one PENDING→APPROVED review event.

The receipt recorded 1,452 image input tokens, 315 text input tokens, and 424 image output tokens. Applying [OpenAI's current standard GPT Image 2.5 token rates](https://developers.openai.com/api/docs/pricing) gives an approximate cost of $0.025911 for this request; the owner observed the API credit balance move from $5.00 to $4.97. The app's $1.00 planning estimate/budget was a run gate, not the charge, and `actual_cost_usd` remains null in the receipt. Account billing is the authority for final cost. At identical token usage, 200 successful one-pass edits would be about $5.18; 200 at a rounded $0.03 each would be $6.00. Prompt length, image content, output tokens, failures, and retries can change that total.

Visual comparison showed a darker sky and stronger architectural definition, along with changed texture and small details in the water, foreground boat, and building. This is a potential authenticity concern for the 0/10 goal, not a software failure; the owner's explicit approval remains the review decision. No additional paid call was made during this evidence review. Verification commands: read-only SQLite queries through `.venv\Scripts\python.exe`, local SHA-256/Pillow inspections, and image viewing. Automated tests were **NOT_RUN** for this evidence-only report update.

## Photo 15 trial instructions addendum (2026-11-01)

Updated step 5 of [the first two-image trial guide](../docs/FIRST_TWO_IMAGE_TRIAL.md) for the owner's Budapest Opera photo 15. Its 2/10 OpenAI prompt now asks for a modest frontal perspective correction and removal of visible people, with explicit semantic-change consent, no uploaded mask, and checks for plausible repairs and architectural fidelity. The guide asks the owner to record the credit balance before and after the run and review Platform usage for the actual charge. No application code, dependencies, or environment setup changed. This documentation change did not start or authorize the second paid call; the owner will make that run. Verification: the two proposed prompt fields passed the app's `detect_conflicts` check using the repository `.venv` interpreter; the requested edits were present and Markdown fences balanced. Automated suites, live API execution, and visual review were **NOT_RUN** for this documentation-only update.

## Run button readiness addendum (2026-11-01)

At the owner's request, the Phase 04 Start authorized run button now has a distinct muted disabled style and a nearby text reason when the preview, eligibility, paid-run budget, or current-run authorization is missing. Its submission handler locks before the asynchronous draft-save check, preventing repeated clicks from queueing duplicate runs while that check or the queue request is pending. A failed save or request clears preview and authorization so a retry requires a fresh review. The backend authorization, budget, and idempotency checks remain in place. Updated `docs/UI_WORKFLOW.md`; no dependency or environment change was needed.

Verification: repository `.venv` interpreter path checked; `npm --prefix frontend test -- --run` **PASS** (2 files, 10 tests, including a new paid-run readiness and double-click test); `npm --prefix frontend run build` **PASS** (TypeScript and Vite). Python tests, live API execution, and owner visual inspection were **NOT_RUN** for this frontend-only update. No paid request was made by the agent.

## Second owner-authorized live edit evidence (2026-11-01)

The owner reports that the Budapest Opera photo 15 result looks fine and is approved. Read-only inspection of the private catalog found batch `3aff9db6-2d43-4a0f-ad7b-101696857895` COMPLETED and job `a2cd22d3-0d65-4a65-9047-ed808d1b6711` SUCCEEDED without error. It used `gpt-image-2.5-sunburst`, prompt version 3 containing the frontal perspective and people-removal requests, and no uploaded mask. The separate version `b65bf39b-a0aa-4f47-b2b0-95adaaad9e85` is **APPROVED**, with one approval review event at 15:56:01 UTC. The source, publication input, raw provider result, and final version all exist with SHA-256 hashes matching the catalog; the job's input hash also matches its publication-input row. The final version is 1600×1200. This metadata check does not replace the owner's visual judgment.

The second receipt records 1,452 image input tokens, 240 text input tokens, and 424 image output tokens; its `actual_cost_usd` is null. The owner observed a **$0.02** credit-balance change for this run, after a **$0.03** change for the first run: **$0.05 displayed balance change across two edits**. These are owner-reported rounded balance movements, not exact per-request invoice amounts. No paid call or image edit was made by the agent for this report update. Verification: read-only SQLite and SHA-256 inspection using the repository `.venv` interpreter. Automated suites were **NOT_RUN** because only this evidence report changed; the broader 20-photo owner walkthrough remains pending.

## Owner approval and revised next phase (2026-11-01)

The owner explicitly closed and approved Phase 04 after reviewing both limited live outputs. The broader 20-photo walkthrough, remote CI, and exact provider billing reconciliation remain recorded as unrun or unresolved; approval does not turn them into passing checks. The owner chose local catalog prefill and private GPS-to-visited-city suggestions as the new Phase 05, moving approved-only export and orphan cleanup to Phase 06. This planning revision updates the project plan, supporting architecture/schema/data/UI/testing contracts, decision log, README, and historical review guides' forward-looking phase references. No Phase 05 implementation, dependency installation, model download, paid API call, or image processing was performed for this revision.

Documentation verification: `git diff --check` **PASS** (line-ending conversion notices only); a Python check through the repository `.venv` **PASS** for relative Markdown links, balanced fences, and Phase 05/06 heading order across 12 changed documents. The first checker version reported false stale-export matches because its pattern also matched correct sentences mentioning both phases. The second checker version failed to locate a heading because an em dash in a PowerShell pipeline was not preserved in the Python source. Replacing the broad phrase pattern and matching headings with ASCII-only regular expressions fixed both checker issues; no project document defect was involved. Python and frontend test suites were **NOT_RUN** because this revision changes only documentation and no dependency specification or setup procedure.
