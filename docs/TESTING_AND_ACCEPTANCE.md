# Verification protocol

## Principles
No test may alter source originals. Test fixtures must be tiny and synthetic/license-safe. CI never calls paid APIs. Record precise commands/results (PASS, FAIL, NOT_RUN with reasons), not vague assertions. Human visual approval is a separate gate from software correctness.

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
- No status promotion from SUCCEEDED to APPROVED without a user event.
- No approved version overwritten, no rejected attempt lost.
- Retry defaults exclude approved and concurrent in-flight photos; exact previously rejected config is not automatically retried.
- No private precise GPS in public exports by default.
- Failed save is visible to user; no silent data loss.
- Expensive jobs require explicit owner authorization.
- Completed milestone report contains actual test evidence and open blockers.

## Phase 00 gate
Audit document inventory, reference integrity, phase naming/branch, lifecycle consistency, risk/deferral register. No runnable application, image processing, UI or AI tests should be claimed for Phase 00.
