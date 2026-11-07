# Owner review handoff: ontology-driven editing prompt autofill

Branch: `feature/ontology-driven-prompt-autofill`. Review status: **pending owner review**. All working-tree changes are unstaged and uncommitted. No source photograph, private catalog, approved image, paid provider, or cloud service was used.

## Scope and files

- `config/prompt_rules.yaml` and `backend/review/prompt_rules.py`: owner-editable rule catalog, ontology validation, deterministic matching, priority, incompatibility, consent and conflict handling.
- `backend/catalog/migrations/015_prompt_rules.sql`, `backend/review/service.py`, `backend/review/prompts.py`, `backend/review/editing.py`, `backend/review/app.py`: separate rule draft fields, immutable prompt snapshots, approval and job staleness checks. Migration 015 revokes readiness of prior prompts; it retains prompt and image rows.
- `backend/review/catalog_prefill.py`, `backend/review/prompt_batch.py`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`, and components and styles under `frontend/src/`: provisional and manual-tag previews, editable rule selection and wording, per-photo batch preview and selective prompt compilation.
- `tests/` and `frontend/src/test/`: focused rule, persistence, prompt, and UI checks; schema-version assertions updated. `scripts/migrate_data_layout.py` accepts schema 15. `README.md`, `docs/DATABASE_SCHEMA.md`, and `docs/DATA_AND_ARTIFACTS.md` describe the workflow and data contract.

No dependency declaration, lockfile, or environment setup change was needed. Python and frontend tests used the existing repository-local `.venv` and locked frontend dependencies.

## Acceptance checks

| Check | Result |
| --- | --- |
| Architecture plus nighttime; nature plus golden hour; animals versus transport; condition and conflict selection | PASS in synthetic backend tests |
| Manual tags and the catalog-acceptance path match the same rules | PASS in synthetic backend tests |
| Rule ID deduplication, edit preservation, disabled rules, optional semantic consent, repeated compilation | PASS in synthetic backend tests |
| Draft/tag changes stale prompt approval; rule configuration hash blocks stale approval; rule constraints survive prompt edits | PASS in synthetic backend tests |
| Batch preview is photo-specific; owner may compile a selected subset | PASS in backend and frontend tests |
| Provisional and draft UI rule controls | PASS in component tests; browser layout NOT RUN |
| Representative travel-photo prompts and photographic authenticity | NOT RUN; owner visual review required |
| Recognition accuracy, 20-photo workflow timing, 200-photo performance | NOT RUN |
| Real generative edits, provider charges, cloud uploads, and approved export | NOT RUN |

## Exact test record

Final verification from PowerShell at the repository root, with `.venv/Scripts/python.exe` verified as the repository interpreter:

- `& .\.venv\Scripts\python.exe -m unittest discover -s tests -q` — **109 passed**.
- `npm --prefix frontend test -- --run` — **24 passed**, four test files.
- `npm --prefix frontend run build` — **PASS**, TypeScript checks and Vite production build.
- `git -c core.safecrlf=false diff --check` — **PASS**, no whitespace errors in tracked changes.

Earlier failures and corrections: the first `tests.test_analysis_prompts` run found a schema-14 assertion; the first frontend build found missing new draft fields in test fixtures. The first full backend run found four schema-version assertions and two layout-migration schema-range errors. A later frontend test used a nonunique text query; a later full backend test still required acknowledgment of all batch items; and a later frontend batch mock returned two prompts after only one was selected. Those assertions, mocks, and the layout helper were corrected. The focused run, `& .\.venv\Scripts\python.exe -m unittest tests.test_prompt_rules tests.test_v2_batch -q`, passed 13 tests before final verification.

## Review and reproduction

Use the cross-platform setup and verification commands in [README.md](../README.md#ontology-driven-editing-prompt-autofill) from a fresh shell. Before opening a real existing catalog with migration 015, stop the app and back up the entire private catalog and media together. For a visual workflow check, use synthetic photos or owner-selected originals in an isolated catalog. Run local recognition on an architecture/night image and compare proposed tags and prompt before acceptance. Accept, deselect a rule, edit its text, change tags, refresh, and confirm owner instructions remain. Repeat manually without recognition, then preview a mixed photo batch and compile only selected prompts. Inspect layout, wording, photographic authenticity, and approval staleness in the browser. Do not authorize a paid run for this review.

Known limits: manually edited generated wording remains verbatim when a rule is deselected; the owner must remove its text or explicitly refresh. Rule matching recognizes canonical ontology labels, while manually entered noncanonical labels remain valid catalog data without an automatic rule match. Rule previews do not establish that a later generative result will preserve pixels or scene authenticity. Owner browser visual review, real-photo wording review, merge, and release remain outstanding.
