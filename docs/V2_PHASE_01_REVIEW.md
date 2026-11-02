# V2 Priority 1 owner review — local correction

This review uses private owner-selected photographs. It does not call a paid provider. Keep all photos, catalog files, backups, and measurements under ignored `data/` or another private location. Stop the app before taking a catalog backup. Record the sample IDs and findings privately under `data/evidence/`.

## Windows PowerShell, fresh shell at the repository root

```powershell
python scripts/setup_env.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Canonical environment setup failed.' }
& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python interpreter.' }
New-Item -ItemType Directory -Force -Path 'data/input', 'data/catalog', 'data/backups', 'data/evidence' | Out-Null
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Catalog is missing. Import the selected photo folder before review.' }
if (-not (Test-Path -LiteralPath 'frontend/package.json' -PathType Leaf)) { throw 'Frontend package specification is missing.' }
$backup = 'data/backups/catalog-before-v2-local-' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.sqlite'
& .\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/catalog backup --output $backup
if ($LASTEXITCODE -ne 0) { throw 'Catalog backup failed.' }
& .\.venv\Scripts\python.exe -m backend.catalog preflight
if ($LASTEXITCODE -ne 0) { throw 'Source preflight failed.' }
New-Item -ItemType Directory -Force -Path 'frontend/dist' | Out-Null
npm --prefix frontend ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend install failed.' }
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath 'frontend/dist/index.html' -PathType Leaf)) { throw 'Frontend build failed.' }
& .\.venv\Scripts\python.exe -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000
```

## Linux, fresh shell at the repository root

```bash
python3 scripts/setup_env.py || exit 1
test -f .venv/bin/python || { echo 'Canonical environment missing' >&2; exit 1; }
.venv/bin/python -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()" || exit 1
mkdir -p data/input data/catalog data/backups data/evidence frontend/dist
test -f data/catalog/catalog.sqlite || { echo 'Import selected photos before review' >&2; exit 1; }
test -f frontend/package.json || { echo 'Frontend package specification missing' >&2; exit 1; }
.venv/bin/python -m backend.review.export_cli --data-dir data/catalog backup --output "data/backups/catalog-before-v2-local-$(date -u +%Y%m%dT%H%M%SZ).sqlite" || exit 1
.venv/bin/python -m backend.catalog preflight || exit 1
npm --prefix frontend ci || exit 1
npm --prefix frontend run build || exit 1
test -f frontend/dist/index.html || { echo 'Frontend build missing' >&2; exit 1; }
.venv/bin/python -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000
```

If there is no catalog, use the import procedure in the README with a verified owner-selected input folder, then rerun this guide. These commands do not import or edit arbitrary files. Open `http://127.0.0.1:8000` while the server remains running.

## Visual and practical pilot

1. Select about 20 varied photos: daylight, night, architecture, people, artwork, landscape, and panorama. Before processing, record original SHA-256 and pixel dimensions using the catalog preflight or a trusted local hash tool.
2. For each photo, open **Editing and versions**. Confirm local correction is selected, the recommended preset/settings are already filled, and **Live preview while adjusting** is checked. Move several tonal and geometry sliders continuously; confirm the preview updates without pressing a button, shows **Updating…**, settles on the last value, and does not flicker back to an older setting. Disable live preview and confirm slider movement stops automatic requests; **Refresh preview** must still work. Use Reset after a temporary change and confirm the recommended values and preview return. Geometry should be neutral unless you change it.
3. Create a local version. Confirm its receipt reaches SUCCEEDED, the version is PENDING, and the full-resolution PNG master download has the source’s oriented dimensions unless you chose crop/geometry. Confirm the JPEG fits the selected website profile. Compare both at 100% with the original for clipping, color cast, halos, noise loss, facial detail, architecture, artwork, and panorama edges. Reject poor results and adjust the recipe; never approve by job success alone.
4. Record time from opening a photo to pending local version, actions outside visual review, render time, peak process memory, PNG/JPEG disk size, recommendation acceptance/rejection, and manual overrides. Use a representative larger original for memory checks. Do not extrapolate to 200 photos without a measured batch run.
5. Explicitly approve only visually acceptable versions. Run the read-only export preview and audit. Confirm pending/rejected images are absent from export eligibility. Recheck original SHA-256. Do not publish a collection as part of this pilot unless separately reviewed and authorized.
6. On one already approved photo, confirm **Create replacement version** is disabled until the replacement checkbox is selected. Create a visibly different candidate and confirm the old version remains APPROVED while the candidate is PENDING. Reject one candidate and confirm the old approval remains. Create another, visually inspect it, choose **Approve and replace current**, and confirm the earlier version is labeled SUPERSEDED and still downloadable while export preview selects only the new approval.

The Windows and Linux commands are documented for fresh shells; this branch was tested on Windows only. Leave owner findings in private evidence and record acceptance in the phase report before merging or starting Priority 2.
