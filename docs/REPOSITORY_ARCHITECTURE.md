# Architecture (proposed, not implemented)

## Deployment
Single-user local application with browser UI on a laptop/desktop. Python FastAPI backend, React + TypeScript frontend, SQLite with migrations, filesystem-backed originals/thumbnails/versions. Consider Pillow/OpenCV for deterministic operations, ExifTool for metadata, OpenAI API accessed *only* server-side. Exact stack is subject to Phase 00 approval and Phase 01 feasibility check.

## Proposed layout
```
backend/{api,database,ingestion,processing,ai,export}/
frontend/src/
prompts/{presets,system}/
tests/
docs/
reports/
scripts/
data/{originals,thumbnails,masks,edited,exports,catalog.sqlite}  # ignored
AGENTS.md
.env.example
```
Do not create empty scaffolding folders merely for cosmetic compliance.

## Key boundaries
UI displays thumbnails/previews, never embeds API keys, and uses backend endpoints to persist settings and approval. Backend owns database, filesystem paths, model calls, queue, concurrency, logs and export rules. Media remain on local disk; relational DB stores IDs/paths/checksums/structured records, not default full-size image blobs.
Image ingestion, AI observation, prompt compilation, editing execution and review are separate services with explicit persisted states. Original and generated versions never share an output filename.

## Domain lifecycle
Original photo -> import/checksum/metadata -> optional AI suggestions -> human review of classification/preset/instructions -> compile and inspect final prompt -> authorized job/attempt -> visual compare -> approve/reject -> approved-only export.
A batch is a saved selection/filter and job group; it does not own source identity.

## Operational considerations
Use SQLite transactions/WAL, migrations and unique IDs. Stable IDs survive renames/moves; track original location and managed path separately. Jobs should be resumable and idempotent with unique output paths. UI virtualizes large image collections; never request all full-resolution assets simultaneously. Treat masks and generated images as potentially sensitive. Store actual provider model identifier and pricing/cost receipts per call rather than depending on hardcoded assumptions.

## Deferred alternatives
Desktop-native GUI, hosted database, distributed queue, cloud image storage, multi-agent orchestration and multi-tenant security deferred until demonstrated need.
