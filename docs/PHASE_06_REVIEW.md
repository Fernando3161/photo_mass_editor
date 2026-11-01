# Phase 06 owner review — approved website export

The operational layout is now `data/input/` for referenced originals, `data/catalog/` for SQLite and private working media, `data/exports/` for approved collections, `data/backups/` for SQLite snapshots, `data/evidence/` for private review records, and `data/models/` for the local model cache. New application runs use `--data-dir data/catalog`. The one-time copy migration preserves the old phase folders as recovery copies and verifies the new catalog. Stop any review server before migration or backup. A complete recovery needs source photographs and generated media as well as SQLite.

## Windows PowerShell, from a fresh repository shell

```powershell
python scripts/setup_env.py
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Repository virtual environment is missing.' }
New-Item -ItemType Directory -Force -Path 'data/backups', 'data/evidence' | Out-Null
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath 'data/phase04-review/catalog/catalog.sqlite' -PathType Leaf)) { throw 'No catalog exists to migrate.' }
    .\.venv\Scripts\python.exe -m scripts.migrate_data_layout
    .\.venv\Scripts\python.exe -m scripts.migrate_data_layout --apply
}
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Canonical catalog is missing.' }
$backup = 'data/backups/catalog-before-review-' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.sqlite'
.\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/catalog backup --output $backup
.\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/catalog audit
.\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/catalog preview
```

The migration itself makes a pre-layout SQLite backup in `data/backups/` and never deletes the source folders. The later backup command refuses to overwrite an existing file; choose a new filename if two runs start within the same second. Check that `missing`, `changed`, `source_issues`, `invalid_manifests`, and `invalid_cost_reports` are empty before exporting. `orphaned` files need investigation; the audit never deletes them.

## Linux, from a fresh repository shell

```bash
python scripts/setup_env.py
test -f .venv/bin/python || { echo 'Repository virtual environment is missing.' >&2; exit 1; }
mkdir -p data/backups data/evidence
if ! test -f data/catalog/catalog.sqlite; then
    test -f data/phase04-review/catalog/catalog.sqlite || { echo 'No catalog exists to migrate.' >&2; exit 1; }
    .venv/bin/python -m scripts.migrate_data_layout || exit 1
    .venv/bin/python -m scripts.migrate_data_layout --apply || exit 1
fi
test -f data/catalog/catalog.sqlite || { echo 'Canonical catalog is missing.' >&2; exit 1; }
.venv/bin/python -m backend.review.export_cli --data-dir data/catalog backup --output "data/backups/catalog-before-review-$(date -u +%Y%m%dT%H%M%SZ).sqlite"
.venv/bin/python -m backend.review.export_cli --data-dir data/catalog audit
.venv/bin/python -m backend.review.export_cli --data-dir data/catalog preview
```

## Start the web interface

Run these commands from the repository root **after the backup above**. Keep the server terminal open while using the browser. The production frontend must be built because the Python server serves `frontend/dist/`.

Windows PowerShell:

```powershell
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Catalog is missing.' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Repository virtual environment is missing. Run python scripts/setup_env.py first.' }
if (-not (Test-Path -LiteralPath 'frontend/package.json' -PathType Leaf)) { throw 'Frontend package is missing.' }
New-Item -ItemType Directory -Force -Path 'frontend/dist' | Out-Null
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath 'frontend/dist/index.html' -PathType Leaf)) { throw 'Frontend build failed.' }
.\.venv\Scripts\python.exe -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000
```

Linux:

```bash
test -f data/catalog/catalog.sqlite || { echo 'Catalog is missing.' >&2; exit 1; }
test -f .venv/bin/python || { echo 'Repository virtual environment is missing. Run python scripts/setup_env.py first.' >&2; exit 1; }
test -f frontend/package.json || { echo 'Frontend package is missing.' >&2; exit 1; }
mkdir -p frontend/dist
npm --prefix frontend run build || exit 1
test -f frontend/dist/index.html || { echo 'Frontend build failed.' >&2; exit 1; }
.venv/bin/python -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. If port 8000 is occupied, rerun the final server command with `--port 8001` and open **http://127.0.0.1:8001** instead. Stop the server with Ctrl+C when finished.

## Real sample acceptance

1. Inspect a varied owner-selected set of about 10–15 photos in the workstation. Ensure the desired version is explicitly **APPROVED**; rejected and pending versions stay unpublished. Check people, scene fidelity, captions, tags, city/country, and publication rights. No paid edit is required for this export review.
2. With the web interface open, select **Export** and click **Preview approved collection**. This previews **all** approved website versions in the catalog. Confirm the count and selected version IDs before authorizing the export. The preview reads and validates files; it does not make an API call to an editing provider.
3. Tick **I authorize this approved collection export**, then click **Export approved collection**. Alternatively, from the shell after inspecting the preview, run:

   ```powershell
   .\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/catalog export --authorized
   ```

   On Linux use `.venv/bin/python` in the same command. Each run makes a new UUID folder under `data/exports/`; it never overwrites an approved version or an earlier export.
4. Click the displayed collection path to open its `data/exports/<id>/` folder in File Explorer on Windows (or the system file manager on Linux). **Recent collections** keeps earlier exports available after a browser refresh, so you need not export again just to open the folder. Open `manifest.json`, `cost_report.json`, `images/`, and `thumbnails/`. Compare every sample website JPEG with its approved workstation version. The website JPEG must have the same SHA-256 and dimensions as the approved version and must have no EXIF/GPS. The thumbnail may be smaller and has a separate hash. The manifest must contain only the owner-confirmed editorial city/country and no precise coordinates, original path, or raw EXIF. A blank location is expected when one or both editorial fields are missing.
5. Run the `audit` command again and investigate every finding. Back up `data/catalog/`, `data/input/`, and `data/exports/` together, plus any externally referenced source originals. To rehearse recovery, copy these directories to a **separate private location**, restore a matching SQLite backup into its catalog, and run `audit` and `preview` against that copy. Do not replace the live catalog during a rehearsal.

Record the actual sample IDs, version IDs, hashes, counts, privacy findings and visual decisions in private evidence. The agent's synthetic tests do not constitute owner visual acceptance. Do not publish the collection until you have reviewed it.

## Retire legacy review folders

The application now reads only `data/catalog` and `data/input`, and writes approved collections to `data/exports`. Existing `data/phase*-review*` folders are historical recovery copies; they are excluded from the operational layout and remain ignored by Git. After you confirm the canonical catalog, existing export, source hashes, and any unique private evidence you wish to keep, archive or remove those legacy folders as a separate owner-approved cleanup. The migration deliberately does not delete them.
