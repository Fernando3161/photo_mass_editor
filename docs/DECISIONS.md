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

## Governance
These Phase 00 recommendations require owner approval; record any changed decision, consequences, date and linked phase/PR here.
