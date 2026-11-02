# Architecture (Phase 06 approved export implemented for owner review)

## Deployment
Single-user local application with a browser UI on a laptop/desktop. Phase 01 provides the catalog and image inspection. Phase 02 adds the local FastAPI/React review workstation. Phase 03 adds a server-side analysis-provider boundary, cached provenance, deterministic prompt compiler, immutable prompt approval, and versioned publication-profile contract. Phase 04 adds publication-input derivation, local corrections, an optional server-side image-edit adapter, bounded jobs, retained attempts, and explicit version review. Phase 05 adds local recognition and private visited-city matching. Phase 06 adds approved-only website export, privacy-filtered manifests, cost reporting, SQLite snapshot and read-only cleanup audit. Provider APIs and credentials stay server-side.

## Current and planned layout
```
backend/catalog/                         # implemented catalog and migrations
backend/review/                          # implemented local Phase 02 API
backend/review/{analysis,analysis_service,prompts}.py  # Phase 03 boundaries
backend/review/{image_pipeline,editing,openai_edit}.py # Phase 04 boundaries
backend/review/{local_model,catalog_prefill}.py         # Phase 05 boundaries
backend/review/{export,export_cli}.py                   # Phase 06 boundaries
backend/review/local_corrections.py                     # V2 Priority 1 recipes and full-resolution masters
frontend/src/
prompts/{presets,system}/
tests/
docs/
reports/
scripts/
data/input/                             # selected referenced originals
data/catalog/{catalog.sqlite,originals,thumbnails,publication-inputs,masks,edited}/
data/exports/                           # approved website collections
data/{backups,evidence,models}/         # private recovery, review, model cache
AGENTS.md
.env.example
```
The canonical application data directory is `data/catalog`; the backend resolves `data/exports` as its sibling. The one-time copy migration preserves old phase review folders until the owner verifies the new catalog. Fresh installations do not create phase-named data directories. Do not create empty scaffolding folders merely for cosmetic compliance.

FastAPI serves JSON/media endpoints and the production frontend build from one loopback-bound process. Vite is used only for frontend development. The UI requests summaries first and fetches a selected photo's full detail/original on demand. The horizontal filmstrip windows its DOM items; the contact sheet supplies full random access.

## Key boundaries
UI displays thumbnails, originals, and selected edited versions, never embeds API keys, and uses backend endpoints to persist review metadata. Backend owns database, private paths, derivative generation, a two-worker job queue, and optional model calls. Phase 05 local recognition runs from verified thumbnails through CPU ONNX Runtime; GPS-to-city matching and visited-city coordinates stay server-side. Phase 06 export copies validated approved website bytes into a new collection and exposes manifest/cost files through recorded export IDs. Media remain on local disk; relational DB stores IDs/paths/checksums/structured records, not full-size image blobs. Photo detail responses omit precise GPS, raw EXIF, hashes, and internal paths.
Image ingestion, AI observation, prompt compilation, publication-input derivation, editing execution, output normalization, and review are separate services with explicit persisted states. The editing adapter can read only the selected publication input; original and generated versions never share an output filename.

## Domain lifecycle
Original photo -> import/checksum/metadata -> optional local recognition and city suggestions -> human review of classification/location/preset/publication profile/instructions -> compile and inspect final prompt -> deterministic publication input -> authorized job/raw attempt -> validated publication version -> visual compare -> approve/reject -> approved-only export.
V2 local correction branches after catalog review: source hash and recipe recommendation -> owner-adjustable settings -> receipt and full-resolution PNG master -> separate website JPEG -> explicit visual approval -> approved-only export. The prompt and publication-input steps remain exclusive to generative editing.
A batch is a saved selection/filter and job group; it does not own source identity.

## Operational considerations
Use SQLite transactions/WAL, migrations and unique IDs. Stable IDs survive renames/moves; track original location and managed path separately. Jobs should be resumable and idempotent with unique output paths. UI virtualizes large image collections; never request all full-resolution assets simultaneously. Treat masks and generated images as potentially sensitive. Store actual provider model identifier and pricing/cost receipts per call rather than depending on hardcoded assumptions.

## Deferred alternatives
Desktop-native GUI, hosted database, distributed queue, cloud image storage, multi-agent orchestration and multi-tenant security deferred until demonstrated need.
