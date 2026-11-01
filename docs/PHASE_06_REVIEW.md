# Phase 06 owner review — approved website export

The first Phase 06 command should be a SQLite backup **while the review server is stopped**. The backup command reads the existing catalog without migrating it. A complete recovery also needs the referenced source photographs and the catalog's generated media; the SQLite file alone is insufficient. Keep backups and exports private until you have inspected the people, captions, locations, ownership rights, and every image selected for publication.

## Windows PowerShell, from a fresh repository shell

```powershell
if (-not (Test-Path -LiteralPath 'data/phase04-review/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Catalog is missing. Complete Phase 04/05 review first.' }
New-Item -ItemType Directory -Force -Path 'data/phase06-review/backups' | Out-Null
python scripts/setup_env.py
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Repository virtual environment is missing.' }
.\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/phase04-review/catalog backup --output data/phase06-review/backups/catalog-before-phase06.sqlite
.\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/phase04-review/catalog audit
.\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/phase04-review/catalog preview
```

The backup command refuses to overwrite an existing file. For a repeat review, choose a new backup filename. The following `audit` or `preview` command applies migration 008. Check that `missing`, `changed`, `source_issues`, `invalid_manifests`, and `invalid_cost_reports` are empty before exporting. `orphaned` files need investigation; the audit never deletes them.

## Linux, from a fresh repository shell

```bash
test -f data/phase04-review/catalog/catalog.sqlite || { echo 'Catalog is missing. Complete Phase 04/05 review first.' >&2; exit 1; }
mkdir -p data/phase06-review/backups
python scripts/setup_env.py
test -f .venv/bin/python || { echo 'Repository virtual environment is missing.' >&2; exit 1; }
.venv/bin/python -m backend.review.export_cli --data-dir data/phase04-review/catalog backup --output data/phase06-review/backups/catalog-before-phase06.sqlite
.venv/bin/python -m backend.review.export_cli --data-dir data/phase04-review/catalog audit
.venv/bin/python -m backend.review.export_cli --data-dir data/phase04-review/catalog preview
```

## Start the web interface

Run these commands from the repository root **after the backup above**. Keep the server terminal open while using the browser. The production frontend must be built because the Python server serves `frontend/dist/`.

Windows PowerShell:

```powershell
if (-not (Test-Path -LiteralPath 'data/phase04-review/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Catalog is missing.' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Repository virtual environment is missing. Run python scripts/setup_env.py first.' }
if (-not (Test-Path -LiteralPath 'frontend/package.json' -PathType Leaf)) { throw 'Frontend package is missing.' }
New-Item -ItemType Directory -Force -Path 'frontend/dist' | Out-Null
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath 'frontend/dist/index.html' -PathType Leaf)) { throw 'Frontend build failed.' }
.\.venv\Scripts\python.exe -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

Linux:

```bash
test -f data/phase04-review/catalog/catalog.sqlite || { echo 'Catalog is missing.' >&2; exit 1; }
test -f .venv/bin/python || { echo 'Repository virtual environment is missing. Run python scripts/setup_env.py first.' >&2; exit 1; }
test -f frontend/package.json || { echo 'Frontend package is missing.' >&2; exit 1; }
mkdir -p frontend/dist
npm --prefix frontend run build || exit 1
test -f frontend/dist/index.html || { echo 'Frontend build failed.' >&2; exit 1; }
.venv/bin/python -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. If port 8000 is occupied, rerun the final server command with `--port 8001` and open **http://127.0.0.1:8001** instead. Stop the server with Ctrl+C when finished.

## Real sample acceptance

1. Inspect a varied owner-selected set of about 10–15 photos in the workstation. Ensure the desired version is explicitly **APPROVED**; rejected and pending versions stay unpublished. Check people, scene fidelity, captions, tags, city/country, and publication rights. No paid edit is required for this export review.
2. With the web interface open, select **Export** and click **Preview approved collection**. This previews **all** approved website versions in the catalog. Confirm the count and selected version IDs before authorizing the export. The preview reads and validates files; it does not make an API call to an editing provider.
3. Tick **I authorize this approved collection export**, then click **Export approved collection**. Alternatively, from the shell after inspecting the preview, run:

   ```powershell
   .\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/phase04-review/catalog export --authorized
   ```

   On Linux use `.venv/bin/python` in the same command. Each run makes a new UUID folder under `data/phase04-review/catalog/exports/`; it never overwrites an approved version or an earlier export.
4. Open the new `manifest.json`, `cost_report.json`, `images/`, and `thumbnails/`. Compare every sample website JPEG with its approved workstation version. The website JPEG must have the same SHA-256 and dimensions as the approved version and must have no EXIF/GPS. The thumbnail may be smaller and has a separate hash. The manifest must contain only the owner-confirmed editorial city/country and no precise coordinates, original path, or raw EXIF. A blank location is expected when one or both editorial fields are missing.
5. Run the `audit` command again and investigate every finding. Back up the complete catalog directory, including SQLite, publication inputs, edited versions and exports, plus any externally referenced source originals. To rehearse recovery, copy the catalog/media to a **separate private directory**, restore the SQLite backup there, and run `audit` and `preview` against that copy. Do not replace the live catalog during a rehearsal.

Record the actual sample IDs, version IDs, hashes, counts, privacy findings and visual decisions in private evidence. The agent's synthetic tests do not constitute owner visual acceptance. Do not publish the collection until you have reviewed it.
