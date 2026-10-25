# Agent operating contract — Photo Mass Editor

## Mission
Build a local-first, non-destructive photographic catalog, review workstation, and controlled image-editing pipeline. The initial scope is roughly 200 manually selected travel photos. User approval—not successful API execution—determines publication eligibility.

## Read before changing code
1. docs/PROJECT_OBJECTIVES.md
2. docs/PROJECT_PLAN.md
3. docs/DEVELOPMENT_WORKFLOW.md
4. docs/IMAGE_EDITING_POLICY.md
5. docs/DATA_AND_ARTIFACTS.md
6. docs/DATABASE_SCHEMA.md
7. docs/TESTING_AND_ACCEPTANCE.md
8. The active phase report and relevant architecture documentation.

## Non-negotiable invariants
- Never overwrite, recompress, rename in place, or otherwise mutate source photographs. Preserve SHA-256, EXIF extraction, and original path; copy only when explicitly importing into managed storage.
- Store paths/metadata in SQLite and images on disk; never commit private photographs, SQLite operational files, API keys, or generated full-resolution outputs.
- Photo categories/tags are many-to-many. Primary subject is optional; tags are multi-valued. AI predictions are suggestions, not authoritative labels.
- Preserve distinct AI-suggested instructions, user instructions, approved constraints, compiled prompt, model/settings, and each editing attempt. A compiled prompt is editable and versioned.
- Every generated image is a separate immutable attempt/version. Review is explicit: APPROVED, REJECTED, PENDING. Retain rejected versions. Do not export unapproved images by default.
- Default batch eligibility: photos without an approved version. Avoid repeating identical rejected attempts without a changed instruction or explicit retry override.
- A numeric AI allowance is internal application policy, not a provider-guaranteed generative fidelity control. Higher allowance requires explicit consent for semantic changes. Masks are not a guarantee of unchanged unmasked pixels.
- AI API calls, bulk generation, uploads, or paid processing require owner authorization for the current run; prepopulation/analysis also costs money and must be opt-in. Never place provider credentials in browser client code.
- Distinguish local deterministic image corrections from generative changes. For authentic travel photography default to deterministic processing.
- User remains responsible for owner approval of phase branch, merge, and release unless expressly delegated.

## Development discipline
Use the active dedicated phase branch; do not modify main. Read its documented scope, implement only that scope, write small tests and phase report, list exactly which tests ran and which did not. Never claim visual correctness from software tests alone. Do not begin a new phase or merge without owner review. Use repository-relative paths and no machine-specific configuration.
Do not introduce .codex subagents by default; introduce only with a measured, documented benefit.

## Heavy/costly operations
May code and mock API clients, but no real AI calls, large-batch execution, cloud uploads, or destructive file operations without explicit current authorization. Tests must not call external paid services. Never silently alter the original or overwrite an approved edit.

## Completion
A phase is complete only if documented acceptance checks, tests, report, unresolved risks, and reproduction handoff are present. Record failures and unrun tests honestly. Phase 00 consists solely of governance/specifications, not implementation.
