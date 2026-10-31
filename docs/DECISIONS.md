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

## ADR-009 — Local FastAPI and React review workstation (2026-10-30)

Use a loopback FastAPI service for SQLite/media ownership and a React + TypeScript frontend for the Phase 02 workstation. The production build is served by the same local process. Alternative: a desktop-native GUI. The browser UI supports a rich large-screen workflow while retaining local storage and server-side filesystem boundaries. Node is a development/build dependency; the runtime remains local and makes no network provider call.

## ADR-010 — Optimistic autosave with local recovery (2026-10-30)

Save a photo's metadata and draft fields transactionally with an expected catalog revision. Return a conflict instead of overwriting a newer record. Retain each unsaved form in browser local storage until the server accepts it. Alternative: explicit save only. Autosave reduces repetitive work across roughly 200 photos, while visible states and local recovery prevent silent failure.

## ADR-011 — Top filmstrip and fixed split comparison (2026-10-30)

Place the horizontally virtualized filmstrip above a fixed side-by-side original/edited canvas. Provide a full contact sheet for random access. Alternative placements and overlay comparison remain available for later usability changes. The fixed split makes provenance explicit; Phase 02 labels the empty edited side rather than showing a duplicate or fabricated result.

## ADR-012 — Editable draft presets before prompt assembly (2026-10-30)

Seed three conservative preset records as explicitly draft wording and version each edit. Store preset selection and allowance as review metadata only. Alternative: freeze preset text during Phase 02. Editing the records now lets the owner refine wording, while prompt compilation and any cost-bearing action remain Phase 03 concerns.

## ADR-013 — Provider-neutral, fail-closed analysis boundary (2026-10-30)

Define an injected server-side analysis provider and ship Phase 03 with an unavailable default. Alternative: select and embed a specific paid provider now. Provider/model/pricing remain evidence-dependent decisions, so the default cannot make a live call. Every run requires current authorization, a prior cost estimate, and a maximum 25-photo request. Tests use a fake provider with no network.

## ADR-014 — Deterministic versioned prompt compiler (2026-10-30)

Compile approved metadata, preset version, editable suggestion, owner instructions, constraints, allowance, and policy locally. Every compile or owner edit creates an immutable numbered prompt; approval is explicit and becomes stale after draft/photo change. Alternative: ask another model to assemble the prompt. Deterministic compilation is inspectable, testable, and adds no hidden cost.

## ADR-015 — Publication-sized JPEG input before generative editing (2026-10-30)

Create a deterministic publication input before a generative edit and never send the original photograph as the editing image. The initial immutable profile is JPEG, sRGB, maximum 1600-pixel long edge, quality 85, preserved aspect ratio, no upscaling, and stripped metadata. The Turkey trip reference uses 1600-pixel WebP outputs, but JPEG was selected here because the owner's current workstation can inspect it directly. PNG remains available for cases that require lossless or alpha output. Profile changes create new derivatives and stale prior prompt readiness. Raw provider output and the validated publication version remain separate immutable artifacts.

## Governance
These Phase 00 recommendations require owner approval; record any changed decision, consequences, date and linked phase/PR here. Development agents leave decision changes unstaged and uncommitted; the owner manually stages and commits them after review. Automatic commits are forbidden.
