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

## ADR-016 — Local corrections and guarded image-edit adapter (2026-10-31)

Default editing to local deterministic Pillow corrections on the validated publication input. An optional server-side OpenAI Images edit adapter is disabled until an API key and per-image planning amount are configured. Every paid run additionally requires a preview, owner authorization, and a run budget. The planning amount is an application gate, not a provider spending limit or exact invoice. The adapter sends only the JPEG derivative and an optional matching mask. Interruption never silently resumes a paid call, because the prior call may already have been billed. Alternative: automatically retry image edits after restart. That alternative risks duplicate charges and uncontrolled attempts.

## ADR-017 — Local catalog prefill before export (2026-11-01)

The owner approved Phase 04 and requested a local image-recognition and location-prefill phase before export. Phase 05 will produce reviewable suggestions from local image analysis and match private EXIF GPS to an owner-maintained visited-cities list; the former export phase becomes Phase 06. Alternative: add recognition during export or manually label every photo. A separate phase keeps suggestion quality, privacy, and owner corrections testable before building the export manifest. Suggestions never override confirmed fields or grant edit/publication approval. Phase 05 must choose and verify a Windows/Linux-compatible local inference stack, declare direct packages in `requirements.in`, pin the full `requirements.lock`, and extend `scripts/setup_env.py` for automatic installation in `.venv`. Pinned model files download and verify automatically into an ignored cache on first use; an automated prefetch option supports offline operation. No package or model choice is finalized by this planning decision.

## Phase 05 implementation choice — CPU CLIP and private city list

Phase 05 uses the pinned MIT-listed `Xenova/clip-vit-base-patch32` ONNX quantized model with CPU ONNX Runtime, NumPy, and tokenizers. It downloads checked files only when local recognition is explicitly run (or when the owner asks setup to prefetch); neither user photos nor GPS are sent to the model host. The model classifies a small controlled label set from a verified thumbnail. Similarity scores are relative and exact landmark names remain owner-entered. Private GPS is matched by a server-side Haversine distance against owner-entered city centers/radii; close competing matches are ambiguous. Acceptance is explicit and cannot change semantic consent or image approval. The implementation and owner pilot are recorded in the Phase 05 report.

## ADR-018 — Approved export identity and privacy (2026-11-01)

The website profile already yields a validated publication JPEG. Export copies its bytes without another resize or re-encode. A separate small JPEG thumbnail supports browsing. A new UUID directory and SQLite receipt preserve each export; a failed preparation remains for the read-only audit rather than deleting evidence. The manifest uses owner-entered or explicitly accepted editorial city/country when both fields are present, confirmed tags, and reviewed description/subject. It excludes original filenames, raw EXIF, precise GPS, local paths, and analysis suggestions that were not accepted. The cost report distinguishes known actual costs from missing receipts. A SQLite online backup can be taken before the Phase 06 migration; a complete recovery also needs the source and generated media files. Alternative considered: re-encoding the approved website image; rejected because it would change quality and break approved-version identity.

## ADR-019 — Phase-free operational data layout (2026-11-01)

The Phase 04 catalog path was a review convention, not a durable product layout. The canonical data root now uses `data/input` for selected originals, `data/catalog` for SQLite and internal artifacts, `data/exports` for approved collections, plus `data/backups`, `data/evidence`, and `data/models`. A one-time migration takes a SQLite backup, copies files with hash verification, updates only source paths in the copied database, validates the new catalog, and retains the old phase directories for recovery until the owner accepts the new layout. A fresh installation uses the phase-free paths from the beginning. Export files are routed to the sibling `data/exports` only for the canonical catalog; legacy catalogs remain readable. The UI opens recorded export directories through an explicit local action rather than exposing arbitrary filesystem paths to a browser-supplied request.

## ADR-020 — Protected private-LAN launch (2026-11-01)

The owner requested one-file Windows startup and access through the local IP. The supported launcher now generates a fresh password, constrains accepted Host headers, and runs the production frontend and API together. A non-loopback manual launch without an access password fails. HTTP Basic authentication is sufficient only on a trusted private LAN; traffic is unencrypted, so public internet or untrusted Wi-Fi use is unsupported. Alternative: leave the API unauthenticated on the LAN; rejected because it would expose originals, metadata, write actions, and configured paid editing to other devices. HTTPS and remote-user accounts are deferred beyond this single-user local scope.

## ADR-021 — Noncommercial public-release terms (2026-11-01)

The owner requested free redistribution for noncommercial purposes. The release tree adopts the standard PolyForm Noncommercial 1.0.0 software license in place of GPLv2; it permits noncommercial use, modification, and distribution. The two explicitly public README photo previews use separate CC BY-NC 4.0 terms. NOTICE.md records the author and makes clear that earlier GPLv2 grants in history are not revoked. Alternative: CC BY-NC for all files; not chosen because Creative Commons advises against applying CC licenses to software itself. Commercial permission and publication rights remain owner decisions.

## ADR-022 — Source-based local correction recipes (2026-11-02)

The owner requested V2 Priority 1 before V1 release signoff. Local deterministic edits now use an independent versioned recipe and source-based full-resolution render, while generative edits retain prompt approval and publication-sized input. This removes prompt and paid-run controls from the local workflow. The recipe records a source hash, profile snapshot, measured recommendation, manual settings, and a job receipt; the output is a private PNG master plus a website JPEG. Conservative auto exposure, levels, white balance, shadows, and highlights are preloaded. Geometry is manual and neutral by default because no trustworthy horizon/lens-profile measurement is available. Float32 tonal calculations yield an 8-bit RGB master; higher bit depth and the real-photo performance/quality pilot remain open. Owner image review still controls export.

## ADR-023 — Explicit approved-version replacement (2026-11-02)

An approved version remains the publication choice until the owner explicitly creates and approves a replacement. Local and generative jobs store the exact approved version they target and fail if it changes before completion. The candidate begins PENDING. Final **Approve and replace current** runs in one transaction: the new version becomes APPROVED, the previous approval receives supersession metadata and is exposed as SUPERSEDED, and both immutable files and review events remain. Rejection leaves the prior approval active. The stored status of a superseded row uses the existing non-current `REJECTED` value plus explicit supersession fields, avoiding a destructive SQLite table rebuild while keeping the partial unique APPROVED index and existing export queries correct.

## ADR-024 — Per-photo batch receipts and prompt acknowledgment (2026-11-02)

V2 Priority 2 retains the existing source-based single-photo local recipe/job as the unit of image provenance. A batch snapshots selection and settings and links independent jobs; it never owns or approves image bytes. The two-worker executor bounds concurrent renders. Queued batch jobs resume on startup because deterministic local rendering has no provider charge; interrupted running jobs fail for inspection, and paid generative calls retain their no-auto-resume rule. Cancellation marks only queued local jobs. Alternative: a single all-or-nothing render transaction; this would discard successful versions when one source fails and would obscure per-photo recovery.

Named recipes are immutable settings snapshots, and an owner can override a selected photo's recommendation before previewing. A preview signature covers per-photo source identity, profile, settings, eligibility and replacement intent. Batch prompt preparation similarly requires visible per-photo previous/proposed text and acknowledgment before creating immutable prompt versions. Prompt approval rechecks current photo/draft identity, required constraints and semantic-change policy; paid image editing still has a separate 20-photo preview, budget and current-run authorization. No batch action grants image approval.

## ADR-025 — Text-only optional refinement and local model gate (2026-11-04)

V2 Priority 3 keeps CLIP as a local suggestion and search aid with a larger, versioned candidate set. Similarity scores are relative, and owner-confirmed subject/location remain authoritative. Optional OpenAI text refinement receives only the deterministic prompt, after a planning-cost preview, budget entry and authorization for that run. It saves an immutable proposal receipt; adoption creates a separate pending prompt version that must pass policy validation and receive explicit approval. Image editing retains its own authorization. The standard API planning rate uses the documented GPT-6 Luna text prices observed on 2026-11-04; the model is an alias and pricing must be rechecked before a paid pilot. Alternative: send photo pixels to a cloud vision model for a richer prompt; rejected for this phase because it adds private-image transfer and cost without local evidence of usefulness.

An [Apache-2.0 SmolVLM-256M model](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct) and its [175 MB Q8 GGUF form](https://huggingface.co/ggml-org/SmolVLM-256M-Instruct-GGUF) are plausible local prose candidates. The model card gives a GPU memory claim, not measured Windows/Linux CPU memory or latency for this application. The separate llama.cpp runtime is also outside the current locked `.venv` setup. Selection, download and dependency changes are deferred until a reproducible CPU/package and owner-photo quality evaluation satisfies the Priority 3 gate. CLIP cannot generate prose, so the UI does not present its labels as a local scene description.

## ADR-026 — V2 cost receipts and optional signed publication copies (2026-11-04)

The OpenAI Images API provides usage and a request header, not an invoice amount. Store usage, request ID and a dated standard-tier rate snapshot on each new receipt; calculate USD only when the exact supported model and required token breakdown are known. Keep planning estimates, provider-returned amounts and owner-supplied itemized billing separate. Reconciliation requires a matching provider request ID and is additive. Rates reflect [OpenAI's standard pricing and image-generation guidance](https://developers.openai.com/api/docs/pricing) on 2026-11-04; aliases, tiers, regions and future rates can differ. Prior receipts with incomplete usage remain unknown rather than being backfilled from planning amounts.

Optional C2PA signing uses the pinned Python SDK and an owner-supplied certificate and private key stored outside version control. The browser export remains unsigned; an explicit CLI run signs separate JPEG copies, records signer subject/certificate fingerprint and approved-version ingredient, and verifies the signed asset before publication. A self-issued test certificate proves local binding but not public trust. The owner must choose production certificate custody and a trust policy before using signed files publicly. Signing and the approved export do not alter the approved JPEG. Alternatives considered: signing approved bytes in place and using built-in test credentials in production; both would break byte identity or falsely imply trust.

Windows and Linux launchers use the same locked `.venv` setup, default to loopback with a fresh access password, and require explicit LAN binding. Dependency and frontend bundle stamps avoid unnecessary npm reinstall/rebuild on an offline restart. Fresh installation still requires access to pinned packages. The owner must visually check the actual OS and network flows before release.

## Governance

These Phase 00 recommendations require owner approval; record any changed decision, consequences, date and linked phase/PR here. Development agents leave decision changes unstaged and uncommitted; the owner manually stages and commits them after review. Automatic commits are forbidden.
