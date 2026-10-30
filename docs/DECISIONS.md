# Architecture decision log

## ADR-001 — Local-first catalog (proposed, Phase 00)
Use local SQLite for structured records and disk storage for image bytes. Alternative: remote SQL/cloud storage. Rationale: one local operator, reduced cost and better source-photo control. Revisit if remote/multi-user service becomes a committed requirement.

## ADR-002 — Primary subject plus many tags (proposed)
Optional single primary subject and multiple content/condition tags. Not a rigid hierarchical taxonomy. AI predictions are editable observations.

## ADR-003 — Versioned approval (proposed)
Per-attempt immutable edited version with PENDING/APPROVED/REJECTED review and explicit approval events. Only one current approved version per photo. Default batch selection excludes approved.

## ADR-004 — Separate editable instructions (proposed)
AI suggestion field and independent user field, compiled into an inspectable editable prompt with provenance and conflict detection before execution.

## ADR-005 — No mandatory Codex subagents (proposed)
Keep AGENTS.md guidance and phase reports; no .codex multi-agent orchestration until measurable benefit.

## ADR-006 — UI navigation (proposed)
Desktop dual-view, horizontally virtualized filmstrip, full contact sheet and keyboard controls. Specific placement/compare gesture deferred to Phase 02 user testing.

## ADR-007 — Phase 01 reference-first ingestion (2026-10-30)

Default to referencing source files read-only; explicit `--mode copy` creates a managed original. Both modes retain the original path and checksum. Alternative: copy every source on import. Reference mode avoids duplicating a curated library and any inadvertent source relocation; it requires preflight checks when external files move or change. Hash-verified relink retains the UUID after a move. The owner can revisit the default after trying real photos.

## ADR-008 — Phase 01 format and dependency boundary (2026-10-30)

Use Pillow 13.0.0 for JPEG, PNG, TIFF and WebP inspection and orientation-corrected thumbnails. Defer RAW/HEIC and sidecar interpretation until a supported decoder and metadata policy are selected. Alternative: install broad native format tools now. The narrow dependency keeps local and CI setup reproducible; unsupported files are reported rather than silently imported.

## Governance
These Phase 00 recommendations require owner approval; record any changed decision, consequences, date and linked phase/PR here. Development agents leave decision changes unstaged and uncommitted; the owner manually stages and commits them after review. Automatic commits are forbidden.
