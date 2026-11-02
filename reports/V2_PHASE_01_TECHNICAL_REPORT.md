# V2 Priority 1 technical report — local correction pipeline

Date: 2026-11-02. Branch: `dev/v2-01-local-pipeline`. Baseline: `90cd3a8` (V1 release preparation, still awaiting owner merge/tag and visual signoff). Working tree: all V2 changes unstaged and uncommitted for owner review. The owner requested Priority 1 implementation before the V1 release gate; no later V2 priority has started.

## Scope and result

V2 Priority 1 adds a prompt-independent local correction path. Each photo has a preloaded conservative recipe, optional manual settings and geometry, a preview, a source-resolution PNG master, and a separately encoded website JPEG. The job and recipe are immutable SQLite records; the JPEG starts PENDING and needs owner visual approval before export. Generative editing retains publication-sized derivative input, prompt approval, budget, and run authorization. No provider call, model download, bulk image run, or cloud upload was made during implementation.

| Acceptance check | Result | Evidence |
| --- | --- | --- |
| Original immutable, hash checked | PASS on synthetic fixture | Local correction tests verify source SHA-256 before and after preview/render/review. |
| Versioned recipe, per-photo recommendation and reset | PASS in code/DOM | Migration 009, local recommendation API, local editor and frontend test. |
| Levels, exposure, white balance, shadows/highlights | PASS in synthetic execution | Float32 tonal operations applied from stored recipe. Photographic quality is unverified. |
| Straighten, crop, lens and perspective controls | PASS on synthetic geometry | Geometry test validates reduced dimensions and safe bounds. Auto geometry remains identity due to missing reliable measurement. |
| Full-resolution master and separate website JPEG | PASS on synthetic fixture | 1800×1200 PNG master, 1600×1067 JPEG, no publication input or lossy intermediate; exact replay pixel comparison passes. |
| Local path avoids prompt, budget and paid-run authorization | PASS | API and frontend tests; compiled prompt and legacy edit job counts remain zero. |
| Receipt-linked pending review and approved-only export | PASS on synthetic fixture | Local job, pending version, owner event, master download and export preview tested. Queued job recovery fails safely on restart. |
| Explicit replacement of an approved version | PASS on synthetic fixtures and DOM | Local and generative jobs retain the target approval; implicit replacement is rejected; prior bytes/history remain SUPERSEDED and export selects the new approval. |
| Real 20-photo visual pilot and memory/time benchmark | NOT_RUN | Owner photographs and machine measurements require the owner review guide. |
| Linux runtime smoke test | NOT_RUN | Current execution host is Windows. Fresh-shell instructions are documented. |

## Implementation and data impact

Migration `009_local_recipes.sql` adds `local_recipes`, `local_jobs`, and `image_versions.local_job_id`. Migration `010_approval_replacements.sql` adds replacement targets to local/generative jobs and supersession provenance to versions. `backend/review/local_corrections.py` handles recommendation, validated settings, local preview, queued render, receipts, master media, and restart recovery. The API exposes local recommendation/preview/run/job and master endpoints. Review and export validate the master/source/profile/job chain. The audit includes masters. The frontend defaults to the local operation and offers recommendation, preset, reset, sliders, optional crop/geometry, preview, and direct version creation; the generative controls remain behind their selector. The one-time layout migration accepts schema 8, 9, and 10 catalogs. No dependency declarations or lockfile changed; NumPy, Pillow, FastAPI and test dependencies were already pinned in the canonical environment. Generated masters and database remain ignored private data.

The owner-requested quality-of-life pass replaces local numeric fields with sliders and compact readouts. The editing tab uses a wider three-column arrangement: original/edited comparison, independently scrolling controls, and independently scrolling preview/version review. The generative run preview uses the same right-hand preview area. Other work-area tabs retain their prior two-column shell.

The approved-version replacement pass keeps the default eligibility guard. An owner must enable replacement before a local or generative candidate can be queued; the job records the exact approved target. The candidate remains PENDING and does not disturb export eligibility. Final **Approve and replace current** validates that target and atomically approves the candidate while retaining the prior file and labeling it SUPERSEDED through explicit provenance. Rejection leaves the prior approval active. Synthetic tests cover local and generative replacement, missing confirmation, one-current-approval enforcement, retained history, and export selection.

Float32 processing is used for tonal calculations, with an 8-bit RGB PNG master. The render keeps the corrected image plus encoded master/JPEG in memory, so peak use on large originals remains unmeasured. Lens and perspective parameters are manual estimates, not calibrated camera profiles. A failed render can leave an immutable unreferenced artifact; the audit reports it without deletion. The local UI operates on one photo; selection-wide recipe application is Priority 2.

## Tests and command record

- `npm run build` in `frontend/`: PASS, TypeScript check and Vite production build.
- `npm test` in `frontend/`: first run FAIL (one new assertion parsed a GET request without a JSON body); assertion restricted to the POST request; second run PASS, 15 tests across 3 files.
- `.venv\Scripts\python.exe -m pytest -q`: FAIL because pytest is not in the locked environment. The repository uses `unittest`; no dependency was installed ad hoc.
- `.venv\Scripts\python.exe -m unittest discover -s tests -q`: PASS, 65 tests during initial integration; 67 after local pipeline coverage; replacement integration first rerun FAIL because two schema-migration count assertions still expected 9; corrected to 10; final rerun PASS, 69 tests.
- `.venv\Scripts\python.exe -m unittest tests.test_local_corrections -v`: PASS, 3 synthetic local tests at the intermediate checkpoint; final full suite includes 4 local tests.
- Final `npm test`: PASS, 16 tests across 3 files, including explicit replacement creation and approval labeling.
- Final `npm run build`: PASS, TypeScript and production bundle.
- Quality-of-life rerun: the first frontend test run failed because the new sliders lacked explicit accessible names. Added `aria-label` values to all correction and crop sliders; the rerun passed all 15 tests and the production build passed. The replacement pass then raised the final frontend count to 16 and backend count to 69.
- Visual browser smoke test: NOT_RUN because the browser-control host was unavailable. A synthetic ignored catalog was prepared under `data/evidence/qol-ui/`, but no private photo was opened and no external service was called. Automatic cleanup was rejected by the execution policy, so this disposable ignored folder remains for owner removal.

Every Python test command was preceded by verification that `sys.prefix` resolves to repository `.venv`. Tests use temporary synthetic images and mocked services. No tests called external paid APIs. No photographic quality conclusion follows from software tests.

## Risks, owner review and handoff

The real-photo pilot, peak memory, render time, disk use, clipping/color/geometry quality, and Linux smoke test are open. The photo recommendation uses image statistics and the selected draft preset; it does not identify a reliable horizon or calibrated lens. A locally edited image must be visually compared and explicitly approved. Follow [V2 Priority 1 review](../docs/V2_PHASE_01_REVIEW.md), record private evidence, and decide whether to accept/adjust this branch before any owner commit, merge, or Priority 2 implementation. The owner alone stages and commits reviewed changes.
