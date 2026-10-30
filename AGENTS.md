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
- Automatic commits are forbidden. The owner alone stages and commits changes after reviewing them. Development agents must leave all changes unstaged and uncommitted; do not run `git add`, `git commit`, `git commit --amend`, or create commits by another method.

## Development discipline
Use the active dedicated phase branch; do not modify main. Read its documented scope, implement only that scope, write small tests and phase report, list exactly which tests ran and which did not. Leave the resulting working tree for owner review and manual staging/commit. Never claim visual correctness from software tests alone. Do not begin a new phase or merge without owner review. Use repository-relative paths and no machine-specific configuration.
Do not introduce .codex subagents by default; introduce only with a measured, documented benefit.

## Heavy/costly operations
May code and mock API clients, but no real AI calls, large-batch execution, cloud uploads, or destructive file operations without explicit current authorization. Tests must not call external paid services. Never silently alter the original or overwrite an approved edit.

## Completion
A phase is complete only if documented acceptance checks, tests, report, unresolved risks, and reproduction handoff are present. Record failures and unrun tests honestly. Phase 00 consists solely of governance/specifications, not implementation.


## Local Development Environment

### Environment Management

- Python is installed and available through the system `PATH`.
- The project must use a **dedicated, repository-local Python virtual environment** located at `.venv/`, created using Python's standard `venv` module.
- The `.venv/` directory must be excluded from Git through `.gitignore`.
- **All development, execution, debugging, and testing must use this environment exclusively.**
- Codex and other development agents must not create temporary, alternative, or agent-specific Python environments.
- System Python may only be used to create or repair `.venv/`, not to execute project code or tests.

### Environment Setup and Reproducibility

- Provide a reproducible environment setup procedure compatible with **Windows PowerShell and Linux**.
- Prefer a single cross-platform Python setup script, with minimal platform-specific wrappers only when necessary.
- The setup procedure must:
  1. Create `.venv/` if it does not exist.
  2. Install dependencies from version-controlled dependency specifications.
  3. Update the existing environment when dependencies change.
  4. Verify the environment, installed dependencies, and Python interpreter.
- All direct and transitive dependencies must be reproducibly specified, preferably using a lockfile with pinned versions.
- Use the same environment specification and setup procedure for local development, automated testing, and CI/CD.
- CI/CD must recreate `.venv/` from the version-controlled specifications rather than copy or reuse a local environment.

### Dependency Management

- Dependencies must not be installed ad hoc without updating the project's dependency specifications.
- When a development phase introduces, removes, or updates dependencies, the agent must update the dependency declarations, lockfile (if applicable), and environment setup procedure as part of the same phase.
- All installations and dependency updates must target the repository's `.venv/`.
- If the environment fails or becomes inconsistent, the agent must diagnose the problem and repair the canonical environment or its setup procedure.
- **Creating an alternative environment to bypass errors is prohibited.**
- Dependency and environment changes must be documented in the corresponding phase technical report.

### Execution Rules

- Before running project code, tests, or scripts, verify that the selected Python interpreter belongs to the repository's `.venv/`.
- Prefer invoking the virtual environment's Python interpreter directly rather than relying on shell activation:
  - **Windows:** `.venv\\Scripts\\python.exe`
  - **Linux:** `.venv/bin/python`
- Run tools and tests through that interpreter whenever possible (for example, `python -m pytest` using the environment's Python).
- Do not use globally installed Python packages or development tools as substitutes for missing project dependencies.
- Do not modify the system Python installation or global package environment.

### Testing and CI/CD

- All automated tests, integration tests, and supported development commands must execute within `.venv/`.
- CI/CD pipelines must create their own repository-local `.venv/` using the documented setup procedure.
- The environment setup must be repeatable on a clean machine with a compatible Python installation.
- Any environment-related failures must be reported with their causes, attempted corrections, and remaining limitations.
- A development phase must not be declared complete until its required tests execute successfully using the canonical environment, unless an explicitly documented and owner-approved exception applies.
