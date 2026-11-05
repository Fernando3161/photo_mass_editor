# V2 Priority 4 technical report — provenance, cost accounting and launch

- Date: 2026-11-04
- Branch: `dev/v2-04-provenance-launch`; baseline: owner-committed V2 Priority 3 `e621a5e`
- Status: working tree unstaged and uncommitted for owner review. No `git add`, commit, merge or release was made.
- Owner request: proceed with V2 Phase 04. No paid request, cloud image upload, real export, or private photo processing was authorized for this run.

## Acceptance evidence

| Check | Status | Evidence and limit |
| --- | --- | --- |
| Usage-based cost calculation and unknown handling | PASS in synthetic tests | Standard OpenAI image and GPT-6 Luna text rate snapshot `openai-standard-2026-11-04-v1`; incomplete usage and unsupported models remain unknown. Planning, calculated, provider-returned and billed fields stay separate. |
| Provider request identity and itemized billing | PASS in synthetic tests | Image/text adapters retain `x-request-id` (text also accepts response ID); failed responses with identity/usage retain them when available. Billing import requires a matching private request ID, is transactional and rejects duplicates. No real provider invoice was available. |
| Signed publication copy | PASS in synthetic signing test; owner validation NOT_RUN | A generated local CA/leaf test credential signed a synthetic JPEG; the test verified its ingredient, approved-version binding, unchanged approved pixels/bytes and tamper failure. Optional export writes a separate `signed/` hash and receipt. A production trusted certificate and real-photo export were not supplied or run. |
| Windows launcher | PARTIAL | PowerShell syntax parsed; canonical setup and offline `PIP_NO_INDEX=1` restart passed locally; fingerprint helper rebuilt once and then reused the bundle. A full launcher/browser/LAN smoke on the owner machine was not run to avoid changing the private working catalog. |
| Linux launcher | NOT_RUN locally | `scripts/start.sh` and Ubuntu CI checks are added; this Windows session could not execute the Linux launcher. CI results are pending owner push/PR. |
| Canonical environment and frontend | PASS locally | `.venv` interpreter verified; locked package setup, backend suite, Vitest and TypeScript/Vite production build passed. Windows and Linux fresh-clone CI jobs are configured but not yet observed. |
| Original preservation and publication approval | PASS in synthetic tests; owner visual review NOT_RUN | Export test confirms approved JPEG bytes stay unchanged and signed copy has a distinct hash. No owner photograph was edited or exported. |

## Implementation and design

Migrations `013` and `014` add cost/request fields, additive billing reconciliation and separate signed-copy receipt fields. Existing SQLite/image rows are not rewritten. `costs.py` calculates only from complete usage for known model/rate combinations and stores the rate version at the call. [OpenAI standard pricing](https://developers.openai.com/api/docs/pricing) and the [image generation usage guide](https://developers.openai.com/api/docs/guides/image-generation) were checked on 2026-11-04. A calculated figure is not an invoice: model aliases, billing tiers, regions, cache behavior and later price changes can alter charges. The export cost report includes editing, analysis and text-refinement attempts. A private CSV reconciliation requires `operation,receipt_id,provider_request_id,billed_usd`; earlier export reports remain immutable, and a later export reflects imported billing.

`c2pa-python==0.38.0` plus its pinned transitive packages were added to `requirements.in`/`requirements.lock` and installed only in the canonical `.venv`. Signing is an explicit CLI option with owner-supplied PEM certificate chain and matching RSA PS256 private key, never a built-in production identity. The certificate subject and SHA-256 fingerprint are recorded; the private key stays in ignored owner storage. The signed copy carries an approved-JPEG ingredient and a limited operations assertion; source paths, GPS and hidden prompt text are excluded. Local verification tolerates an untrusted test issuer while rejecting manifest/binding failures. Public trust still depends on an owner-selected [C2PA compliant certificate and trust chain](https://opensource.contentauthenticity.org/docs/signing/get-cert/).

The Windows launcher now defaults to loopback and requires `-Lan` for protected LAN binding. `scripts/start.sh` uses the same canonical setup, loopback default and explicit `--lan-host`. Both have a check-only mode. `setup_env.py` reuses a verified `node_modules` tree when the lock fingerprint matches and repairs an inconsistent one. `frontend_bundle.py` hashes production inputs and reuses a current `dist` bundle. A fresh clone still downloads pinned dependencies; offline restart assumes previously installed packages, Node modules and model cache. CI now targets the Phase 04 branch on Windows and Ubuntu, with launcher syntax/setup and offline restart checks. No new model was downloaded.

Changed groups: migrations and `backend/review/{costs,billing,c2pa_signing,editing,openai_edit,prompt_refinement,analysis,analysis_service,export,export_cli}.py`; launch/setup/CI files; pinned dependency specs; synthetic tests and updated migration assertions; README, V2 plan, architecture/schema/data/workflow/testing/decision documents, and the owner review guide. Generated `.venv`, Node modules, frontend bundle, credentials, SQLite and private media remain ignored.

## Commands and results

All Python project execution used `C:\Repositories\Repos_other_projects\photo_mass_editor\.venv\Scripts\python.exe`; its `sys.prefix` was checked against `.venv` first.

- `& .\.venv\Scripts\python.exe scripts/setup_env.py`: PASS after pinning C2PA and its seven new transitive distributions; `pip check` passed and Node.js 24.14.0 dependency tree verified.
- `$env:PIP_NO_INDEX='1'; & .\.venv\Scripts\python.exe scripts/setup_env.py`: PASS on the existing environment; npm dependency verification reused the installed tree.
- `& .\.venv\Scripts\python.exe scripts/frontend_bundle.py`: PASS, production TypeScript/Vite bundle built; immediate second run reported current bundle and skipped build.
- `& .\.venv\Scripts\python.exe -m unittest discover -s tests -q`: PASS, 96 tests after final corrections.
- `npm --prefix frontend test`: PASS, 3 files / 22 tests.
- PowerShell parser on `scripts/start.ps1`: PASS; `git diff --check`: PASS.
- Linux shell syntax, Linux launcher, Windows full launcher/browser, CI jobs, real-photo export, production signing trust, live provider calls, billing-export reconciliation and 200-photo performance: NOT_RUN in this local session. Follow `docs/V2_PHASE_04_REVIEW.md`.

During implementation, failed commands were corrected as follows: a PowerShell `rg` search with a `*.sql` wildcard and `Select-Object -Index 250..300` failed on shell syntax; subsequent reads used valid paths and array slicing. The first full test run failed because SQLite cannot add a UNIQUE column; migration `014` now adds a normal column plus a unique index. The next run exposed schema-version expectations, a mocked response without headers and the old layout-migration guard; each was updated. Early synthetic C2PA tests failed on certificate EKU/action requirements; a generated CA/leaf certificate and `c2pa.created` assertion corrected them. A duplicate billing row initially surfaced a raw SQLite error; the importer now rejects it with a clear validation error. An export test initially placed an existing audit assertion under the new mocked signing case; it was moved back to the unsigned export test. A broad documentation patch missed an exact line and was applied in smaller patches. The lockfile header edit encountered a UTF-8 BOM and was completed through the canonical `.venv` interpreter. All final local tests pass.

## Risks and owner handoff

Actual provider costs remain unknown until matching usage or an owner billing export is available. The fixed price table must be reviewed before future paid runs. Billing exports are private and must stay under ignored `data/evidence/`. The C2PA test credential has no public trust; the owner must decide issuer, key custody, trust validation and whether to publish signed copies. Signed C2PA bytes differ from approved JPEGs by design and need their own website verification. Linux and full Windows/LAN owner smoke checks, real-photo privacy inspection and the pending Phase 03 visual/prompt review remain open. Automated tests do not establish photographic quality or public trust.

Reproduce using `docs/V2_PHASE_04_REVIEW.md` from a fresh shell. Back up the entire private catalog/media set before checking an existing catalog. Review the unstaged diff and test report, then the owner manually stages/commits any accepted changes and decides on merge/release. Engineering implementation is ready for owner review; Phase 04 acceptance remains **INCOMPLETE** until the owner and CI checks above are recorded.
