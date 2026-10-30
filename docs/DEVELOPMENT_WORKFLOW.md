# Development workflow

## Lifecycle
1. Identify active phase and its acceptance criteria in PROJECT_PLAN; inspect outstanding report.
2. Create/check out phase branch from last owner-approved baseline; never work directly on main.
3. Read AGENTS.md and governing docs; record assumptions and decisions.
4. Implement only phase scope as reviewable working-tree changes; avoid unrelated refactors. Do not stage or commit changes automatically.
5. Run fast deterministic unit/integration checks, then phase-specific UI tests; mock paid AI.
6. Run user-authorized manual/paid/large operations only if needed; log input IDs, API version, counts, and actual cost.
7. Update report with exact executed commands, outputs and tests not run.
8. Review the unstaged diff: original/media files, secrets, local paths, schema migrations, cost/privacy changes and reproducibility. Leave all changes unstaged and uncommitted for the owner.
9. Owner reviews the changes, manually stages and commits them, reviews any merge, and authorizes the next phase.

## Branch naming
`dev/v1-phase-NN-short-slug` (e.g. `dev/v1-phase-02-review-ui`); optional task branches `feature/v1-phase-NN-short-topic`. No force push or history rewriting on reviewed branches without consent.

## Commit ownership

Automatic commits are forbidden. Only the owner stages and commits changes after review. Development agents must not run `git add`, `git commit`, `git commit --amend`, or otherwise create a commit. A task handoff must identify the branch and leave the working tree ready for the owner's review.

## Issue/PR discipline
Issue names: `PXX: objective`; define tests and acceptance before implementation. PR summary must include scope, screenshots for visible UI changes, database migration impact, tests, privacy/cost impact, limitations and rollback. Do not mark complete solely because tests pass.

## Decisions
Significant tradeoffs go into `docs/DECISIONS.md` with date, context, alternatives, chosen option, consequences. Update documentation in same PR as behavior. Avoid overlapping authoritative specifications.

## Reports
`reports/PHASE_XX_TECHNICAL_REPORT.md`; template in docs. Distinguish engineering phase reports from per-photo and per-batch processing logs. Never generate fictional performance numbers.

## CI and execution boundaries
Lightweight local/CI tests: parser/unit, database, API mocks, UI smoke, links. Full image batch, paid AI, cloud upload and destructive operations are explicit manual gates. No secrets or source photos in CI fixtures; synthetic/license-safe tiny images only.

## Release
Approved main only; git tags on intentional milestones; schema backup/migration test before upgrades. Preserve catalog export/backup paths outside Git.
