# V2.0.0 release notes

V2 is the owner-authorized release of Photo Mass Editor's local-first, single-user photo catalog and review workstation. It keeps original files immutable, stores edits as separate versions, and exports only versions explicitly approved by the owner. The release builds on [V1.0.0](V1_RELEASE_NOTES.md).

## What changed since V1

- **Stronger local corrections.** Per-photo recommendations and presets cover levels, exposure, white balance, shadows and highlights, sharpening, denoise, straighten, perspective, lens adjustment, and crop. A local render writes a full-resolution PNG master and a separate website JPEG without requiring a compiled prompt or paid authorization. Its first review state is PENDING.
- **Batch workflow.** Named local recipes, per-photo overrides, eligibility previews, queued work, cancellation, and restart receipts support controlled processing of selections. Prompt batch preview and approval retain per-photo versions and staleness checks. Generative batches still require explicit current-run authorization and a planning budget.
- **Version replacement.** An approved image can be replaced through a new pending attempt and an explicit approval. The superseded version, bytes, and review history remain available; export selects the current approval.
- **Suggestions and prompts.** The expanded local ontology offers provisional subject, content, condition, and preset suggestions for owner review. Optional paid text refinement sends the prompt text, records a proposal, and requires separate adoption and approval before an image job. Provider credentials remain server-side.
- **Provenance and export.** Provider request IDs, usage-based cost calculations, and owner billing reconciliation remain distinct from estimates and unknown charges. Optional C2PA signing writes a separate signed copy while preserving the approved image bytes. Privacy-filtered export, file audit, and catalog/media backup guidance remain in place.
- **Startup and evaluation.** Windows and Linux launchers use the repository-local `.venv`. A Docker Desktop evaluation workflow creates an isolated, host-mounted Linux workspace and retains its reports and media privately. The README includes two downscaled, metadata-free, owner-approved before/after showcase pairs.

## Verification record

On 5 November 2026, release preparation on `dev/local-release-evaluation` ran the backend command from the repository root using the canonical `.venv`; the frontend commands ran from `frontend/` with its installed dependencies:

| Check | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m unittest discover -s tests -v` | **PASS**, 102 tests |
| `npm test` (from `frontend/`) | **PASS**, 23 tests in 4 files |
| `npm run build` (from `frontend/`) | **PASS**, TypeScript checks and Vite production build |

The earlier isolated Docker Linux run on `dev/v2-05-ontology-prefill` passed the locked build, 102 backend tests, 23 frontend tests, authenticated health, restart, 20-photo import and hash comparison, and SQLite integrity checks. The run ID, exact revision, and private evidence paths are in [Local Docker release evaluation](../README.md#local-docker-release-evaluation). The complete Docker happy path was not rerun after the final failure-report and input-link guards. GitHub Actions for the release commit had not run when these notes were prepared.

An initial inline PowerShell `python -c` environment check failed because its quotes were stripped. Repeating that check through standard input verified that `sys.prefix` resolves to the repository's `.venv`; no project test ran with the wrong interpreter. The earlier Docker wrapper failures and corrections are recorded in the README.

The owner authorized this V2 release with the following checks still **not recorded as passed**: photo-by-photo visual and workflow acceptance of ontology suggestions, representative local and batch edits, version approval and rejection, approved-only export and privacy review in the browser, and 200-photo performance. Paid provider calls and cloud uploads were not part of release verification. Software tests and the README examples do not establish photographic fidelity, model accuracy, or publication rights. Reproduction commands and acceptance steps remain in the README; keep private evidence under ignored `data/`.

## Known limits

- Local masters are full-resolution PNGs with 8-bit output. RAW and HEIC input and local inpainting are not supported.
- The AI reimagining allowance is application policy, not a provider guarantee of unchanged details. Masks do not guarantee unchanged pixels outside a selected area. Review every generated image before approval.
- Paid analysis, text refinement, and generative edits need a configured provider and explicit authorization for each current run. Planning budgets are application gates, not provider-enforced spending caps; usage calculations and owner billing can differ.
- C2PA signing requires owner-supplied credentials and trust decisions. A locally verifiable test certificate is not a publicly trusted identity.
- This is a local single-user workstation. LAN access uses Basic authentication over unencrypted HTTP on a trusted private network; do not expose it as a public service. Docker evaluation binds to loopback.
- Export remains a deliberate owner action. Back up the catalog and its media together; a SQLite snapshot alone is incomplete.

## Reproduce the automated checks

From a fresh PowerShell or Linux shell at the repository root, run the documented environment setup first (`python scripts/setup_env.py` on Windows or Linux). The script creates and verifies the repository-local `.venv` from pinned dependencies. Then run the commands above, using `.venv/bin/python` on Linux. Follow the [Docker evaluation procedure](../README.md#local-docker-release-evaluation) for an isolated Linux run and record manual visual findings in private evidence. No automated check should use a paid provider.
