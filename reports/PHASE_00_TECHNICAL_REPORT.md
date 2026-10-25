# Phase 00 — Foundation and specifications report

Date: 2026-10-25
Branch: `dev/v1-phase-00-foundation`
Status: IMPLEMENTED FOR OWNER REVIEW — NOT YET APPROVED

## Objective
Establish documented mission, phase-gated development, architecture, data and editing policies, UI workflow, database logical schema and testing/acceptance before implementation.

## Deliverables
Root agent instructions; project objectives; phase plan and workflow; architecture; data/artifacts; logical schema; editing authenticity policy; UI workstation specification; verification protocol; report template; decision log; this report.

## Scope control
No frontend/backend runtime, migrations, image data import, AI calls, external uploads, or costly processing are part of Phase 00.

## Acceptance
- Required specification inventory: written; verify contents on branch.
- Phase branches and owner review gate: documented.
- Source-photo immutability, prompt provenance, editing attempt versioning: documented.
- UI random-access navigation, categories/tags, separate editable prompt fields: documented.
- Executable unit/integration/UI tests: NOT RUN — no implementation exists.
- Live API/image-quality benchmarks: NOT RUN — unauthorized and out of scope.
- Owner acceptance of governing specifications: PENDING.

## Risks and deferred decisions
Model availability/cost must be verified at implementation, not hardcoded. RAW/HEIC support, precise preset language, import vs external reference behavior, licensing/commercialization, filmstrip placement, masking UI, geographic public privacy and export target need later owner decisions. Schema is conceptual and requires migrations/fixture verification in Phase 01.

## Next step
Owner reviews Phase 00 docs and proposed decision log. Following approval, merge Phase 00, then start Phase 01 from reviewed baseline. Do not mark Phase 00 complete before owner acceptance.
