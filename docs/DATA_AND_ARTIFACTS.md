# Data and artifact contract

## Authority
Original bytes are immutable authoritative image evidence; EXIF-derived metadata is the captured-source record; editorial metadata is user-correctable; AI classification/suggestions are derived uncertain observations; generated edits are separate versions, never source replacements.

## Zones (all local and git-ignored)
`data/originals/`: managed copies if chosen; otherwise immutable referenced external paths. `data/thumbnails/`: regenerable previews. `data/masks/`: optional per-attempt masks. `data/edited/`: immutable output versions. `data/exports/`: generated public-facing derivatives. `data/catalog.sqlite`: authoritative operational SQLite state; back up explicitly.
Do not commit source photos, previews, user GPS locations, raw job responses, or .env secrets. Tiny synthetic, licensed test fixtures may be tracked in tests/.
These private `data/` directories are intentionally absent from a fresh clone. Each documented review or development procedure must create the directories it needs before reading or writing artifacts. The Phase 01 catalog creates its own catalog directory on first use, while the owner-review procedure explicitly creates the input and evidence directories.

## Ingestion invariants
Read-only inspect; compute SHA-256, width/height, file format, camera, lens, EXIF date/time/timezone if present, orientation and GPS as present. Preserve raw metadata snapshot without inventing missing coordinates/timezone. Sidecar files handled explicitly. Stable UUID IDs and content hash; identical bytes may be linked to duplicate candidates instead of silently deleted.
Original and managed paths are distinct. Missing/moved original -> flagged unresolved, never silently replaced or deleted. Fix EXIF orientation for preview only, not original pixels. Use atomic output writes and collision-resistant names.

## Derivation provenance
For each AI analysis: photo/version hash, model, instruction template/version, suggested tags/confidence if returned, UTC timestamp, input preview transform and response metadata. For each edit: approved source hash, preset/version, suggestion text, user text, compiled prompt/version, allowance and semantic operation policy, mask hash, engine/model, cost estimate and actual usage when available, status, error and output SHA-256. Never claim exact repeatability for stochastic model results; log settings for traceability.

## Publication and privacy
Website derivative strips precise GPS by default; maintain private GPS separately. Editorial city/country may be exported if confirmed. Do not automatically publish identifiable people or sensitive location metadata. Export manifests identify approved version ID, derivative paths/hashes, title/caption/alt text, crop, format and image size. Preserve appropriate copyright/ownership terms; review for commercialization before public release.

## Phase 01 implemented behavior

The CLI defaults to read-only source references. Managed copies require `--mode copy`. Catalog records contain absolute source paths, repository-data-relative managed and thumbnail paths, source and thumbnail SHA-256, a stable UUID, and a duplicate candidate link when bytes match another source. `preflight` detects missing/changed media; `relink` accepts a moved original only when its checksum matches. Sidecars and known unsupported RAW/HEIC files are reported without interpretation. Backup/restore automation and an orphan scanner remain future work.

## Phase 02 implemented behavior

The review UI reads media through catalog IDs. Internal source paths, hashes, raw EXIF, and precise GPS are not returned in photo-detail JSON. The frontend receives only `gps_present`; editorial city/country remain separate user fields. Review metadata, tag links, subject selection, review state, draft preset selection, allowance, suggestion text, and user instructions persist in SQLite. A failed browser save is also retained under a per-photo local-storage key until the server accepts it; accepted saves remove that recovery copy.

`frontend/node_modules/`, `frontend/dist/`, local browser state, review screenshots, and `data/phase02-review/` are generated/private artifacts and are not committed. The Phase 02 review procedure creates its input and catalog folders explicitly and verifies source hashes before and after review.

## Recovery
Database backup and media-manifest checks should validate physical paths and hashes. Failed writes never assume successful version creation. An orphan scanner should identify missing/unreferenced media without deleting it automatically.
