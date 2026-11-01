# Architecture (Phase 04 implemented; Phase 05 catalog prefill planned)

## Deployment
Single-user local application with a browser UI on a laptop/desktop. Phase 01 provides the catalog and image inspection. Phase 02 adds the local FastAPI/React review workstation. Phase 03 adds a server-side analysis-provider boundary, cached provenance, deterministic prompt compiler, immutable prompt approval, and versioned publication-profile contract. Phase 04 adds publication-input derivation, local corrections, an optional server-side image-edit adapter, bounded jobs, retained attempts, and explicit version review. Phase 05 will add local recognition and private visited-city matching before Phase 06 export. Provider APIs and credentials stay server-side.

## Current and planned layout
```
backend/catalog/                         # implemented catalog and migrations
backend/review/                          # implemented local Phase 02 API
backend/review/{analysis,analysis_service,prompts}.py  # Phase 03 boundaries
backend/review/{image_pipeline,editing,openai_edit}.py # Phase 04 boundaries
frontend/src/
prompts/{presets,system}/
tests/
docs/
reports/
scripts/
data/{originals,thumbnails,publication-inputs,masks,edited,models,exports,catalog.sqlite}  # ignored; models planned Phase 05
AGENTS.md
.env.example
```
Do not create empty scaffolding folders merely for cosmetic compliance.

FastAPI serves JSON/media endpoints and the production frontend build from one loopback-bound process. Vite is used only for frontend development. The UI requests summaries first and fetches a selected photo's full detail/original on demand. The horizontal filmstrip windows its DOM items; the contact sheet supplies full random access.

## Key boundaries
UI displays thumbnails, originals, and selected edited versions, never embeds API keys, and uses backend endpoints to persist review metadata. Backend owns database, private paths, derivative generation, a two-worker job queue, and optional model calls. Phase 05 local recognition and GPS-to-city matching will run server-side; export follows in Phase 06. Media remain on local disk; relational DB stores IDs/paths/checksums/structured records, not full-size image blobs. Photo detail responses omit precise GPS, raw EXIF, hashes, and internal paths.
Image ingestion, AI observation, prompt compilation, publication-input derivation, editing execution, output normalization, and review are separate services with explicit persisted states. The editing adapter can read only the selected publication input; original and generated versions never share an output filename.

## Domain lifecycle
Original photo -> import/checksum/metadata -> optional local recognition and city suggestions -> human review of classification/location/preset/publication profile/instructions -> compile and inspect final prompt -> deterministic publication input -> authorized job/raw attempt -> validated publication version -> visual compare -> approve/reject -> approved-only export.
A batch is a saved selection/filter and job group; it does not own source identity.

## Operational considerations
Use SQLite transactions/WAL, migrations and unique IDs. Stable IDs survive renames/moves; track original location and managed path separately. Jobs should be resumable and idempotent with unique output paths. UI virtualizes large image collections; never request all full-resolution assets simultaneously. Treat masks and generated images as potentially sensitive. Store actual provider model identifier and pricing/cost receipts per call rather than depending on hardcoded assumptions.

## Deferred alternatives
Desktop-native GUI, hosted database, distributed queue, cloud image storage, multi-agent orchestration and multi-tenant security deferred until demonstrated need.
