# V2 Priority 5 technical report — ontology-driven catalog prefill

- Branch: `dev/v2-05-ontology-prefill`; base commit: `6878f4c` (`include ontolohy pre05`); date: 2026-11-05.
- Working tree: all feature changes unstaged and uncommitted for owner review. No merge, push, rebase or release was performed.
- Owner: repository owner; review status: **INCOMPLETE** pending photo-by-photo judgments and browser workflow acceptance.

## Scope and acceptance evidence

| Check | Status | Evidence |
|---|---|---|
| Owner ontology reused, aliases and duplicate validation | PASS | `config/ontology.yaml`, `ontology.py`, synthetic tests. Manual labels remain free text. |
| Separate subject, content and condition evaluation | PASS in synthetic tests | Relative within-kind scoring, ambiguity margins, day/night guard and content rules. Scores are not probabilities. |
| Provisional catalog, owner field protection and undo | PASS in API/component tests | Suggestion acceptance applies only empty scalar fields and new tags; edited provisional values can be accepted. Existing bounded bulk acceptance/undo remains. |
| Draft preset and local recipe separation | PASS in synthetic tests | Existing configured draft IDs map to local recipe IDs with explanation; explicit owner preset wins. |
| Deterministic prompt preview without automatic approval | PASS in API/component tests | Ephemeral form passes through `compile_text`; conflict results are visible; no prompt row is inserted until explicit save. Repeating unchanged compile reuses the same unapproved version. |
| No paid call, image approval or source mutation | PASS by code path and synthetic tests | Recognition uses cached local CLIP; pilot reads verified thumbnails and SQLite read-only. No generative request or approval endpoint is called. |
| Private 20-photo quality improvement | PARTIAL | Coverage and timing measured; owner accuracy, precision/recall, preset agreement and click counts NOT_RUN. |
| Windows/Linux browser and owner visual workflow | NOT_RUN | Vitest/TypeScript pass; actual browser inspection and Linux execution remain with owner. |

## Implementation

The committed owner file defined 37 primary subjects, 23 content tags and 14 conditions as three distinct fields. This branch adds optional aliases without removing canonical labels. `ontology.py` rejects missing/malformed sections, duplicate labels, duplicate recognition phrases and duplicate YAML keys. The pinned model and lock remain unchanged. PyYAML 6.0.3 was already pinned transitively; `requirements.in` now declares it directly and the lockfile header records this phase. Canonical setup verified the existing `.venv` and package tree.

`local_model.py` evaluates an aspect-ratio-preserving whole view and one center view for images wider than 1.65:1. Actual scene pixels, not neutral padding, supply luminance measurements. A concept's canonical phrase receives half its score weight; all its aliases share the other half by mean, so adding aliases does not multiply that concept's weight. `catalog_prefill.py` compares scores only within each field, selects conservative subject and content proposals, and permits broad subject fallbacks when close labels support one family. Subject-to-tag relationships add broad visible categories; independent content evidence needs stronger separation. Daytime can be positively suggested from relative CLIP evidence or supported outdoor content plus measured luminance. Nighttime needs stronger CLIP evidence and a dark scene; low indoor luminance alone is insufficient. Other conditions require a high margin. Rules return both an actual generative draft preset ID and a separate local recipe, with rationale. Preset choice never implies removing people or other scene content.

The suggestion fingerprint and evidence include the ontology SHA-256 and scoring version, so ontology/settings edits invalidate cached suggestions and acceptance checks. `prompts.preview_with_form` overlays unsaved catalog/draft values on the existing deterministic compiler. The browser shows those values in the catalog form and recomputes an unapproved preview as they change. Owner acceptance stores only chosen empty fields and tag additions; a separate click saves one versioned unapproved prompt. Existing staleness and conflict checks remain in force. Local corrections remain independent of prompt preparation.

Changed files: `backend/review/{ontology,local_model,catalog_prefill,prompts,app}.py`, `config/ontology.yaml`, `frontend/src/{App,api,types,styles}.{tsx,ts,css}` and `frontend/src/components/{CatalogPrefillPanel,MetadataPanel}.tsx`; tests `tests/{test_catalog_prefill,test_ontology_prefill}.py` and `frontend/src/test/{CatalogPrefillPanel,MetadataPanel}.test.tsx`; `scripts/evaluate_ontology_pilot.py`; `requirements.in`, `requirements.lock`; `docs/{V2_PROJECT_PLAN,REPOSITORY_ARCHITECTURE,UI_WORKFLOW,TESTING_AND_ACCEPTANCE,DEVELOPMENT_WORKFLOW,DECISIONS,V2_PHASE_05_REVIEW}.md`; this report. No schema migration or source photograph changed.

## Private pilot comparison

The same existing 20 catalog thumbnails and stored old suggestions were compared offline. The full run used the verified cached model and left SQLite untouched. Private per-photo similarities, proposals, timings and a contact sheet are under ignored `data/evidence/ontology-pilot.*`.

| Measure | Earlier | New |
|---|---:|---:|
| Subject proposals | 3/20 | 12/20 |
| Content proposals | 3/20 | 12/20 |
| Condition proposals | 1/20 | 8/20 |
| Mean content tags/photo | 0.15 | 0.90 |
| Draft presets | Natural balance 20/20 | Natural balance 9; Panoramic scene 5; Museum artwork 3; Architecture clarity 3 |
| Mean inference time | Not recorded | 2.973 seconds/photo |

The first broad scoring pass generated 4.4 content tags/photo and 11 Museum artwork recommendations, including obvious false positives in the contact sheet. Rules were tightened and the ontology's generic shrine/museum/shop phrases were refined. A full inference run after the luminance fix captured the final model similarities and timing; the last description and daylight-rule changes were reapplied to those saved similarities with `--reuse-scores`. A contact-sheet inspection suggests fewer obvious false positives, but it is not owner field-by-field accuracy. Several temple/portrait photos remain blank. No exact landmark or location was inferred. Subject accuracy, content precision/recall, condition accuracy, preset agreement, manual corrections and click counts remain **NOT_RUN** until owner review.

## Exact commands and failures

All project Python commands used `.venv\Scripts\python.exe` after checking `sys.prefix` resolves to `.venv`.

- `.venv\Scripts\python.exe scripts/setup_env.py`: PASS; pinned packages, `pip check`, Node dependency tree and interpreter verified.
- `.venv\Scripts\python.exe -m unittest discover -s tests -q`: PASS, 102 tests.
- `.venv\Scripts\python.exe -m unittest tests.test_ontology_prefill tests.test_catalog_prefill -q`: PASS, 17 focused tests after the last scoring and preview edits.
- `npm --prefix frontend test`: PASS, 4 files / 23 tests.
- `npm --prefix frontend run build`: PASS, TypeScript and Vite production build.
- `.venv\Scripts\python.exe scripts/evaluate_ontology_pilot.py`: PASS against the existing private 20-photo catalog; no model download, paid call or database mutation. Full inference ran more than once to tune rules; final metrics are above.
- `.venv\Scripts\python.exe scripts/evaluate_ontology_pilot.py --reuse-scores`: PASS; reapplied the final rules to saved model similarities without another inference or database write.
- `git diff --check`: PASS; Git printed only working-copy LF/CRLF conversion warnings.
- Linux execution, CI, actual browser interactions, click timing, owner photo labels, paid APIs and 200-photo run: NOT_RUN.

Failed commands and corrections: the first `functions.exec` orchestration call had a JavaScript parenthesis error and was rerun correctly before any edit. An initial `apply_patch` targeting a nonmatching YAML line failed; the narrower patch succeeded without overwriting the owner ontology. A combined `apply_patch` against the same API file failed and was split. The initial focused tests failed because old fake recognizer labels used removed hardcoded phrases; fake rankings and expectations were updated to the canonical ontology. A first preview test failed because an unsaved photo had no draft; ephemeral preview now uses default draft values without inserting one. A test block was accidentally placed under the wrong method and moved back. The first read-only SQLite command used a relative path with `Path.as_uri()` and failed; resolving the path fixed it. Several documentation patches failed on line matching and were reapplied in smaller edits. Final commands above pass.

## Risks and handoff

CLIP similarities are relative and scene dependent. A threshold that improves this Japan-heavy pilot may behave differently on mountains, animals, night exteriors and museums elsewhere. The 20-photo set contains no verified owner labels, so classification accuracy and preset agreement cannot be claimed. The pilot is read-only but writes private evidence and contact-sheet files under ignored `data/evidence/`; keep them private. Whole-frame plus one crop costs about three seconds/photo on this local CPU pilot; a 200-photo runtime was not measured. A browser visual check is needed for layout, provisional state, field edits and multi-photo ergonomics. No owner photographs were edited or exported by this phase.

Follow `docs/V2_PHASE_05_REVIEW.md` from a fresh shell. Review the unstaged diff and private pilot evidence, record owner judgments/clicks, then manually stage and commit only accepted changes. Do not begin another phase or merge until owner review.
