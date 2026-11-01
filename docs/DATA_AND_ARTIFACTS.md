# Data and artifact contract

## Authority
Original bytes are immutable authoritative image evidence; EXIF-derived metadata is the captured-source record; editorial metadata is user-correctable; AI classification/suggestions are derived uncertain observations; generated edits are separate versions, never source replacements.

## Zones (all local and git-ignored)
`data/input/`: owner-selected referenced originals. `data/catalog/catalog.sqlite`: authoritative operational SQLite state, including private visited-city entries. `data/catalog/{originals,thumbnails,publication-inputs,masks,edited}/`: managed originals (if chosen) and private generated media. `data/exports/`: approved collections, manifests, and separate small thumbnails. `data/backups/` and `data/evidence/`: private recovery and review records. `data/models/`: ignored verified local-recognition model cache. A fresh installation uses this phase-free layout; the one-time migration copies old phase review data, rebinds source paths in the copied catalog, and leaves the old folders intact for owner verification.
Do not commit source photos, previews, user GPS locations, raw job responses, or .env secrets. Tiny synthetic, licensed test fixtures may be tracked in tests/.
These private `data/` directories are intentionally absent from a fresh clone. Each documented review or development procedure must create the directories it needs before reading or writing artifacts. The Phase 01 catalog creates its own catalog directory on first use, while the owner-review procedure explicitly creates the input and evidence directories.

## Ingestion invariants
Read-only inspect; compute SHA-256, width/height, file format, camera, lens, EXIF date/time/timezone if present, orientation and GPS as present. Preserve raw metadata snapshot without inventing missing coordinates/timezone. Sidecar files handled explicitly. Stable UUID IDs and content hash; identical bytes may be linked to duplicate candidates instead of silently deleted.
Original and managed paths are distinct. Missing/moved original -> flagged unresolved, never silently replaced or deleted. Fix EXIF orientation for preview only, not original pixels. Use atomic output writes and collision-resistant names.

## Derivation provenance
For each AI analysis: photo/version hash, model, instruction template/version, suggested tags/confidence if returned, UTC timestamp, input preview transform and response metadata. For each publication input: original source hash, publication profile ID/version and complete settings, derivative path/hash/dimensions/format, encoder identity/settings, and creation time. For each edit: publication-input ID/hash, approved prompt/version, allowance and semantic operation policy, mask hash, engine/model, cost estimate and actual usage when available, status, error, raw output SHA-256, and normalized publication-version SHA-256. Never claim exact repeatability for stochastic model results; log settings for traceability.

## Publication and privacy
Website derivative strips precise GPS by default; maintain private GPS separately. Editorial city/country may be exported if confirmed. Do not automatically publish identifiable people or sensitive location metadata. Export manifests identify approved version ID, derivative paths/hashes, title/caption/alt text, crop, format and image size. Preserve appropriate copyright/ownership terms; review for commercialization before public release.

## Phase 01 implemented behavior

The CLI defaults to read-only source references. Managed copies require `--mode copy`. Catalog records contain absolute source paths, repository-data-relative managed and thumbnail paths, source and thumbnail SHA-256, a stable UUID, and a duplicate candidate link when bytes match another source. `preflight` detects missing/changed media; `relink` accepts a moved original only when its checksum matches. Sidecars and known unsupported RAW/HEIC files are reported without interpretation. Phase 06 adds a SQLite snapshot command and read-only media audit; media still need a separate backup.

## Phase 06 export behavior

`backend.review.export_cli preview` validates each approved website version, its owner approval event, source hash, job/profile provenance, image hash, dimensions, JPEG format, and absence of embedded EXIF. `export --authorized` creates a new, never overwritten collection under `data/exports/` when the canonical `data/catalog` is used. The website image is copied byte for byte; only the separate 320 px thumbnail is encoded. The manifest contains approved version identity, file hashes, dimensions, confirmed editorial city/country when both exist, reviewed description/subject and confirmed tags. It excludes original filenames/paths, raw EXIF and private GPS. The cost report lists editing and analysis estimates, known actual amounts and unknown counts; it does not imply a provider billing cap. The audit reports missing, changed and unreferenced files without deleting them. SQLite backup is a consistent snapshot but does not include media. The export folder action opens only a completed recorded export in the local file manager.

## Phase 02 implemented behavior

The review UI reads media through catalog IDs. Internal source paths, hashes, raw EXIF, and precise GPS are not returned in photo-detail JSON. The frontend receives only `gps_present`; editorial city/country remain separate user fields. Review metadata, tag links, subject selection, review state, draft preset selection, allowance, suggestion text, and user instructions persist in SQLite. A failed browser save is also retained under a per-photo local-storage key until the server accepts it; accepted saves remove that recovery copy.

`frontend/node_modules/`, `frontend/dist/`, local browser state, review screenshots, and `data/phase02-review/` are generated/private artifacts and are not committed. The Phase 02 review procedure creates its input and catalog folders explicitly and verifies source hashes before and after review.

## Phase 03 implemented behavior

Analysis runs retain provider/model/template/config identity, source hash, raw and sanitized output, suggestions, status, usage, and estimate/actual cost. Raw provider responses and source hashes stay server-side. The browser receives sanitized suggestions only. Prompt rows are immutable versions with input snapshots and explicit approval; draft changes make prior approval stale without deleting history. Phase 03 review backups live under ignored `data/phase03-review/backups/`.

Migration `004_publication_profiles.sql` adds the versioned website profile, associates it with drafts and prompt snapshots, revokes readiness of prompts compiled before the profile rule existed, and reserves immutable `publication_inputs` provenance for Phase 04. Phase 03 selects and records the profile but creates no publication image or edited image.

## Phase 04 implemented behavior

The editing service checks the original SHA-256, creates a separate orientation-corrected JPEG publication input under `publication-inputs/`, and records its source/profile hash, encoder settings, and dimensions. It reuses only a validated immutable input. Deterministic corrections operate on that input. Generative requests receive only the validated derivative and an optional dimension-matched private PNG mask. Every attempt has a job receipt; successful output is retained separately as raw provider/local bytes under `edited/raw/` and as a normalized JPEG under `edited/versions/`. Review begins PENDING, and explicit approval/rejection writes an event. Rejected versions stay available. A duplicate rejected configuration requires a changed prompt/settings or explicit retry override.

Server-side `OPENAI_API_KEY`, model, and planning amount are read from the process environment; no credential is sent to browser code. Restarted queued or interrupted paid jobs are not resumed automatically. Planning amounts gate runs but are not provider-enforced account limits or actual cost receipts. Phase 04 review data lives under ignored `data/phase04-review/`. Phase 05 keeps pinned local model files under ignored `data/models/`, visited-city data and suggestion provenance in private SQLite, and never uploads photos for recognition. It hashes the original or managed source before using the separately stored verified thumbnail as model input. Model downloads are checksum verified and contain no user photograph. Export moves to Phase 06.

## Recovery
Database backup and media-manifest checks should validate physical paths and hashes. Failed writes never assume successful version creation. An orphan scanner should identify missing/unreferenced media without deleting it automatically.
