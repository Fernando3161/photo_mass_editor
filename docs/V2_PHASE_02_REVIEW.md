# V2 Priority 2 owner review — selection and batch workflow

Use about 20 varied owner-selected photos, including daylight, night, architecture, people, artwork, landscape and panorama images. Keep photographs, catalogs, backups and measurements under ignored `data/`. Stop the app before backing up the catalog. No paid provider run is part of this review. Preserve the original SHA-256 list for comparison afterward.

## Windows PowerShell, fresh shell at the repository root

```powershell
python scripts/setup_env.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Canonical environment setup failed.' }
& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python interpreter.' }
New-Item -ItemType Directory -Force -Path 'data/input', 'data/catalog', 'data/backups', 'data/evidence', 'frontend/dist' | Out-Null
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Catalog missing. Import owner-selected photos using the README, then rerun.' }
if (-not (Test-Path -LiteralPath 'frontend/package.json' -PathType Leaf)) { throw 'Frontend specification missing.' }
$backup = 'data/backups/catalog-before-v2-batch-' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.sqlite'
& .\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/catalog backup --output $backup
if ($LASTEXITCODE -ne 0) { throw 'Catalog backup failed.' }
& .\.venv\Scripts\python.exe -m backend.catalog preflight
if ($LASTEXITCODE -ne 0) { throw 'Source preflight failed.' }
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
test -f data/catalog/catalog.sqlite || { echo 'Import owner-selected photos using the README' >&2; exit 1; }
test -f frontend/package.json || { echo 'Frontend specification missing' >&2; exit 1; }
.venv/bin/python -m backend.review.export_cli --data-dir data/catalog backup --output "data/backups/catalog-before-v2-batch-$(date -u +%Y%m%dT%H%M%SZ).sqlite" || exit 1
.venv/bin/python -m backend.catalog preflight || exit 1
npm --prefix frontend ci || exit 1
npm --prefix frontend run build || exit 1
test -f frontend/dist/index.html || { echo 'Frontend build missing' >&2; exit 1; }
.venv/bin/python -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` while the server runs. The commands create required ignored directories and check the catalog, interpreter and frontend inputs. They make no image edit or paid call. If the catalog is absent, follow the README import procedure with an owner-selected folder, then rerun this guide.

## Pilot and evidence

1. Record the 20 photo IDs, original hashes, start time and total actions outside visual comparison privately under `data/evidence/`. Use the catalog preflight or a trusted local SHA-256 tool. Inspect the contact sheet; select a subset, use **Select visible**, clear it, and open the batch screen. Confirm the selected count and thumbnails match the intended photos.
2. Preview the local batch using per-photo recommendations. Check each preset, operations, PNG/JPEG targets, skipped reason and current approval status. Save a named recipe from one representative photo, select it, and override at least one other photo's exposure or recommendation. The **Apply** button must require a fresh preview after a change. Compare planned operations to the actual scenes; leave doubtful photos out of the run.
3. Check current-run authorization, then run a small local batch first. Record time, peak memory, PNG/JPEG disk use, successful/failed/skipped counts and source hashes. Confirm each successful version is PENDING with its own receipt and source-resolution master. Start a second safe batch and cancel queued items while a render is active; inspect the independent receipts. If practical, restart the app with queued items and confirm they resume while interrupted running items retain failed receipts. Do not infer 200-photo throughput from this small pilot.
4. Compare every resulting version with the original at full size for clipped highlights, color cast, halos, noise loss, face detail, artwork fidelity, crop and panorama edges. Use **A** to approve-and-next or **R** to reject-and-next only after inspecting the selected pending version. Confirm the shortcuts do not act while another tab or an editable control has focus. Confirm rejected attempts remain available and identical rejected settings are skipped without explicit retry override. For an already approved photo, check explicit replacement preview and final promotion; the old approval stays export eligible until the new candidate is separately approved.
5. For prompt preparation, use a different safe selection. Preview each previous/proposed prompt and its profile, allowance and consent. Verify the compile button needs acknowledgment of every eligible photo. Compile and inspect versions; approving them must not call an image provider or create a pending image. Change a draft or remove a required constraint in one prompt and confirm approval fails. The separate generative run screen must still require per-photo eligibility, paid-run estimate/budget and current-run authorization. Do not start a paid call for this pilot.
6. Record elapsed time and clicks from selection to pending local versions and from opening a version to decision, correction acceptance/rejection, skipped reasons, failures and any UI confusion. Recheck original SHA-256 values, use read-only export preview to confirm only approved versions are eligible, and record remaining quality or performance concerns. Keep the owner acceptance decision in the Phase 2 report before merge or Priority 3.

The automated tests and synthetic images do not establish visual correctness, real-machine memory or the target of under two hours for 200 photographs.
