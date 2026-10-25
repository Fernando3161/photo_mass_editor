# Data and artifact contract

## Authority
Original bytes are immutable authoritative image evidence; EXIF-derived metadata is the captured-source record; editorial metadata is user-correctable; AI classification/suggestions are derived uncertain observations; generated edits are separate versions, never source replacements.

## Zones (all local and git-ignored)
`data/originals/`: managed copies if chosen; otherwise immutable referenced external paths. `data/thumbnails/`: regenerable previews. `data/masks/`: optional per-attempt masks. `data/edited/`: immutable output versions. `data/exports/`: generated public-facing derivatives. `data/catalog.sqlite`: authoritative operational SQLite state; back up explicitly.
Do not commit source photos, previews, user GPS locations, raw job responses, or .env secrets. Tiny synthetic, licensed test fixtures may be tracked in tests/.

## Ingestion invariants
Read-only inspect; compute SHA-256, width/height, file format, camera, lens, EXIF date/time/timezone if present, orientation and GPS as present. Preserve raw metadata snapshot without inventing missing coordinates/timezone. Sidecar files handled explicitly. Stable UUID IDs and content hash; identical bytes may be linked to duplicate candidates instead of silently deleted.
Original and managed paths are distinct. Missing/moved original -> flagged unresolved, never silently replaced or deleted. Fix EXIF orientation for preview only, not original pixels. Use atomic output writes and collision-resistant names.

## Derivation provenance
For each AI analysis: photo/version hash, model, instruction template/version, suggested tags/confidence if returned, UTC timestamp, input preview transform and response metadata. For each edit: approved source hash, preset/version, suggestion text, user text, compiled prompt/version, allowance and semantic operation policy, mask hash, engine/model, cost estimate and actual usage when available, status, error and output SHA-256. Never claim exact repeatability for stochastic model results; log settings for traceability.

## Publication and privacy
Website derivative strips precise GPS by default; maintain private GPS separately. Editorial city/country may be exported if confirmed. Do not automatically publish identifiable people or sensitive location metadata. Export manifests identify approved version ID, derivative paths/hashes, title/caption/alt text, crop, format and image size. Preserve appropriate copyright/ownership terms; review for commercialization before public release.

## Recovery
Database backup and media-manifest checks should validate physical paths and hashes. Failed writes never assume successful version creation. An orphan scanner should identify missing/unreferenced media without deleting it automatically.
