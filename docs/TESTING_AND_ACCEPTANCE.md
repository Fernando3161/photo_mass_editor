# Verification protocol

## Principles
No test may alter source originals. Test fixtures must be tiny and synthetic/license-safe. CI never calls paid APIs. Record precise commands/results (PASS, FAIL, NOT_RUN with reasons), not vague assertions. Human visual approval is a separate gate from software correctness.
Every runnable test or owner-review procedure must create its required generated directories and check input existence before use. Do not assume ignored private `data/` folders are present in a fresh clone.

Agents leave tested changes unstaged and uncommitted for owner review. Automatic commits are forbidden; only the owner stages and commits changes after review. A passing test run does not authorize an agent to commit.

## Layers
1. Documentation contract: required paths, readable links, no contradictory branch names/policies, references to proposed vs implemented kept explicit.
2. Unit: EXIF parse including missing/invalid values, file hash, safe paths, DB invariants, tag relations, prompt resolver/conflict checks and state machine.
3. Integration: repeated imports/idempotency, missing file handling, persistence/transactions, version history, job retries, approval uniqueness and approved-only export.
4. Frontend: keyboard navigation, filmstrip random access, contact sheet, field autosave error visibility, side-by-side version selection and accessible status.
5. Mock AI: cache key, prompt input snapshot, refusal/error/timeout, cost gating, secret isolation, budget cap; never hit live endpoint during CI.
6. Visual/manual: representative 10–15-photo set (architecture, people, landscape, sculpture, day/night); compare geometry/content authenticity, inspect edits, masks and export.
7. Nonfunctional: memory with 200 thumbnails, API failure recoverability, data backup/restore, concurrent import/job contention.

## Hard gates
- Source SHA-256 preserved before/after every test operation.
- A generative adapter must receive a validated publication input path/hash and must never receive the original or managed-original path. Tests verify the exact format, maximum long edge, aspect ratio, no-upscale behavior, color space, metadata policy, and profile snapshot.
- No status promotion from SUCCEEDED to APPROVED without a user event.
- No approved version overwritten, no rejected attempt lost.
- Retry defaults exclude approved and concurrent in-flight photos; exact previously rejected config is not automatically retried.
- No private precise GPS in public exports by default.
- Failed save is visible to user; no silent data loss.
- Expensive jobs require explicit owner authorization.
- Completed milestone report contains actual test evidence and open blockers.

## Phase 01 gate

Follow [the Phase 01 owner photo review](PHASE_01_REVIEW.md) for a private 10–15-photo sample, source hash comparison, repeat import, preflight and thumbnail/metadata inspection. Record results in the Phase 01 report. Keep the sample and evidence out of Git.

## Phase 02 gate

Follow [the Phase 02 owner review](PHASE_02_REVIEW.md). Automated checks must cover API persistence/privacy/conflicts, keyboard navigation, visible autosave state, failed-save recovery, contact-sheet random access, and filmstrip windowing with 200 summaries. Build the production UI after the tests. The owner separately checks the representative private catalog for layout, keyboard flow, filters, readability, persistence, source hashes, and practical review speed. A passing DOM test is not visual approval.

## Phase 03 gate

Follow [the Phase 03 owner review](PHASE_03_REVIEW.md). Automated tests inject a fake provider and cover authorization denial, bounded requests, cost estimate, cache reuse/invalidation, raw-response isolation, conflict blocking, semantic consent, immutable prompt edits, publication-profile snapshot, approval, and stale invalidation. Live provider work is NOT_RUN until the owner selects a provider and explicitly authorizes that run. Manual review verifies the visible JPEG/1600px publication profile, inspectable prompt inputs/history, and that approval never executes an edit.

## Phase 04 gate

Follow [the Phase 04 owner review](PHASE_04_REVIEW.md). Automated tests must prove that the original hash remains stable, the publication input matches the exact selected profile, provider input is the derivative rather than the source, attempts and failed receipts are retained, repeated request keys do not make duplicate versions, rejected identical attempts require an override, and approval is an explicit event. Test concurrent claims and restart behavior without a network service. The owner inspects the original and every generated version visually. A limited paid trial is optional and requires separate current-run authorization and account configuration; automated tests never make paid calls. Phase 04 is not owner-approved merely because code tests pass.

## Phase 05 gate

Local recognition and location matching must run without an external image/AI service and without modifying source files. Tests cover model/cache provenance and checksum verification, offline cache-missing behavior, valid/invalid/missing GPS, nearest-city radius and ambiguous matches, owner override preservation, no-GPS bulk assignment with undo, accepted metadata invalidating stale prompts, and no automatic consent, edit run, version approval, or publication eligibility. `scripts/setup_env.py` must install all declared and locked Phase 05 dependencies into `.venv` on Windows and Linux; the application must automatically obtain pinned model files for first use and work offline from the verified cache thereafter. CI uses a fake recognizer and synthetic images; it must never download model weights or call a paid API. The owner reviews a varied private pilot of about 20 photos and checks suggested labels and locations before authorizing any larger batch.

## Phase 06 gate

Approved-only export tests cover precise-GPS removal, confirmed editorial city/country only, selected approved-version identity and dimensions, manifest validity, cost report, backup/restore, and cleanup audit. The owner inspects the real exported collection and confirms that no quality-changing resize or unapproved version entered it.

## Phase 07 gate

Run the canonical environment setup and full backend/frontend checks; verify the PowerShell launcher parses and starts from the repository root, refuses unauthenticated LAN requests, and serves authorized requests. Scan the tracked release and reachable Git blobs for credentials, private paths, and unexpected media. Verify public preview dimensions and absence of EXIF/GPS, review the exact license and contact details, and record unresolved risks in the release audit. The owner reviews the final staged file list, visual examples, licensing rights, and merge. A passing scan is not proof of zero vulnerabilities.

## Phase 00 gate
Audit document inventory, reference integrity, phase naming/branch, lifecycle consistency, risk/deferral register. No runnable application, image processing, UI or AI tests should be claimed for Phase 00.

## V2 Priority 1 gate

Run backend `unittest` inside the canonical `.venv`, frontend Vitest, and the production TypeScript/Vite build. Synthetic images must show source hash stability, independent prompt-free local queueing, full-resolution PNG master plus a separate validated website JPEG, no publication-input or lossy JPEG before local processing, deterministic recipe replay, safe crop/geometry bounds, receipt-linked pending version, and explicit approval before export. Test unchanged rejected recipe retry, API authorization split, and startup recovery. The owner separately compares a varied private sample at 100% zoom and records overcorrection, acceptance, click count, memory, render time, and disk use. Automated tests do not establish photographic quality or performance on 200 real photos. Follow the V2 Priority 1 review guide and report before owner acceptance.

## V2 Priority 2 gate

Run the same canonical-environment backend tests, frontend Vitest tests and production build. Synthetic tests cover mixed eligibility, named recipe and per-photo override snapshots, preview staleness, independent partial failures, cancellation, queued batch restart, rejected duplicate guard, per-photo prompt diff acknowledgment, stale and edited prompt approval checks, and explicit version review. Paid providers remain mocked or unavailable. The owner separately follows `V2_PHASE_02_REVIEW.md` on about 20 varied private photos, records click count/time and visual quality, and decides whether the batch workflow is usable before a 200-photo run or merge.
