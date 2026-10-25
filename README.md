# Photo Mass Editor

Local-first, human-reviewed photography catalog and AI-assisted image editing project.

**Current status (2026-10-25): Phase 00 specifications committed for owner review. No application has been implemented or tested yet.** The active development branch is `dev/v1-phase-00-foundation`; `main` remains unchanged pending approval.

## Project scope
Import selected original photographs without modifying them; record metadata and user-editable classifications; provide a desktop browser workstation with filmstrip/contact sheet, side-by-side original/edited comparison, distinct AI suggestions and user prompts, versioned edit attempts, explicit approval/rejection, batch retries excluding approved photos, and approved-only website export.

## Start here
1. Read [AGENTS.md](AGENTS.md) for agent constraints.
2. Read [project objectives](docs/PROJECT_OBJECTIVES.md), [phase plan](docs/PROJECT_PLAN.md), and [development workflow](docs/DEVELOPMENT_WORKFLOW.md).
3. Read [image editing/authenticity rules](docs/IMAGE_EDITING_POLICY.md), [data contract](docs/DATA_AND_ARTIFACTS.md), [logical schema](docs/DATABASE_SCHEMA.md), and [UI specification](docs/UI_WORKFLOW.md).
4. Review [decision log](docs/DECISIONS.md), [acceptance protocol](docs/TESTING_AND_ACCEPTANCE.md), and [Phase 00 report](reports/PHASE_00_TECHNICAL_REPORT.md).
5. Approve or amend Phase 00; do **not** launch Phase 01 before approval/merge.

## Codex handoff
```bash
git clone https://github.com/Fernando3161/photo_mass_editor.git
cd photo_mass_editor
git fetch origin
git switch dev/v1-phase-00-foundation
```
Ask Codex to read `AGENTS.md` and review Phase 00 against `docs/PROJECT_PLAN.md` and the report. Do not request an implementation until the owner accepts the specifications.

## Data policy
Never commit original photographs, generated versions, GPS-bearing operational databases, or API keys. All future local operational media belong outside tracked source control (typically `data/`).
