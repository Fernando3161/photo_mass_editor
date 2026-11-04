# V2 Priority 3 owner review — suggestions and prompt refinement

Use the owner-selected photos in `data/input/` and the active catalog in `data/catalog/`. Keep originals, catalog, backups and observations under ignored `data/`. Stop the app before backing up or changing catalogs. These steps make no paid API request or image edit.

The Windows launcher and direct service startup now create the catalog and import supported `data/input/` photos automatically. The explicit commands below retain a backup, hash record and import receipt for the owner review.

The V1 `docs/PHASE_03_REVIEW.md` and `data/phase03-review/` are historical and do not hold the V2 working catalog. Do not reuse them for this review. An existing catalog belongs to its recorded source paths and hashes. If strict preflight fails after replacing the input batch, stop: restore the old sources, or archive the old catalog and associated media/exports before creating a fresh `data/catalog/`. A SQLite snapshot alone does not contain images.

## Windows PowerShell from a fresh shell at the repository root

```powershell
python scripts/setup_env.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Canonical environment setup failed.' }
& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python interpreter.' }
New-Item -ItemType Directory -Force -Path 'data/input', 'data/catalog', 'data/backups', 'data/evidence', 'data/exports', 'frontend/dist' | Out-Null
$photos = @(Get-ChildItem -LiteralPath 'data/input' -File -Recurse | Where-Object { $_.Extension -match '^\.(jpe?g|png|tiff?|webp)$' })
if ($photos.Count -eq 0) { throw 'Place owner-selected supported photos in data/input first.' }
if (-not (Test-Path -LiteralPath 'frontend/package.json' -PathType Leaf)) { throw 'Frontend specification missing.' }
if (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf) {
    & .\.venv\Scripts\python.exe -m backend.review.export_cli --data-dir data/catalog backup --output ('data/backups/catalog-before-v2-phase03-' + (Get-Date -Format 'yyyyMMddTHHmmss') + '.sqlite')
    if ($LASTEXITCODE -ne 0) { throw 'Catalog backup failed.' }
    & .\.venv\Scripts\python.exe -m backend.catalog preflight --strict
    if ($LASTEXITCODE -ne 0) { throw 'Existing catalog has missing or changed media. Resolve it before importing.' }
}
Get-ChildItem -LiteralPath 'data/input' -File -Recurse | Sort-Object FullName | ForEach-Object { '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash, $_.FullName } | Set-Content -LiteralPath 'data/evidence/v2-phase03-input-before.sha256.txt'
$importResult = & .\.venv\Scripts\python.exe -m backend.catalog import-folder data/input | Out-String | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Import command failed.' }
if ($importResult.errors.Count -gt 0) { $importResult.errors | Format-List; throw 'Resolve import errors before review.' }
$importResult | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath 'data/evidence/v2-phase03-import.json'
& .\.venv\Scripts\python.exe -m backend.catalog preflight --strict
if ($LASTEXITCODE -ne 0) { throw 'Imported catalog preflight failed.' }
npm --prefix frontend ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend install failed.' }
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath 'frontend/dist/index.html' -PathType Leaf)) { throw 'Frontend build failed.' }
& .\.venv\Scripts\python.exe -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000
```

Inspect the import JSON for `errors` and `unsupported`; resolve any errors before review. A repeat import reports existing photos. For a new batch, archive the previous `data/catalog/` and `data/exports/` with their media under `data/backups/` first, then create a fresh `data/catalog/`; never merge unrelated batches by changing source files in place.

## Linux from a fresh shell at the repository root

```bash
python3 scripts/setup_env.py || exit 1
test -f .venv/bin/python || { echo 'Canonical environment missing' >&2; exit 1; }
.venv/bin/python -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()" || exit 1
mkdir -p data/input data/catalog data/backups data/evidence data/exports frontend/dist
test -n "$(find data/input -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.tif' -o -iname '*.tiff' -o -iname '*.webp' \) -print -quit)" || { echo 'Place photos in data/input first' >&2; exit 1; }
test -f frontend/package.json || { echo 'Frontend specification missing' >&2; exit 1; }
if test -f data/catalog/catalog.sqlite; then
    .venv/bin/python -m backend.review.export_cli --data-dir data/catalog backup --output "data/backups/catalog-before-v2-phase03-$(date -u +%Y%m%dT%H%M%SZ).sqlite" || exit 1
    .venv/bin/python -m backend.catalog preflight --strict || exit 1
fi
find data/input -type f -print0 | sort -z | xargs -0 -r sha256sum > data/evidence/v2-phase03-input-before.sha256.txt
.venv/bin/python -m backend.catalog import-folder data/input > data/evidence/v2-phase03-import.json || exit 1
.venv/bin/python -c "import json; r=json.load(open('data/evidence/v2-phase03-import.json', encoding='utf-8')); assert not r['errors'], r['errors']" || exit 1
.venv/bin/python -m backend.catalog preflight --strict || exit 1
npm --prefix frontend ci || exit 1
npm --prefix frontend run build || exit 1
test -f frontend/dist/index.html || { echo 'Frontend build missing' >&2; exit 1; }
.venv/bin/python -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Run local suggestions on a small selection first. Compare proposed subjects and night, backlit, blurred and hazy conditions with the images; note false positives, missing terms and search usefulness. Confirm pending suggestion terms appear in search without becoming confirmed tags. Check that the exact landmark and editorial city remain unfilled until owner confirmation. Record source hashes again after review and compare them with the before manifest.

Compile a deterministic prompt for a representative photo. Inspect its profile, allowance, owner instruction and approved constraints. The optional **Preview text cost** and **Request proposal** controls must stay separate from **Adopt as new version**, **Approve current prompt**, and paid image editing. Compare each proposed prompt with the deterministic baseline for precision, scene invention, missing constraints and unnecessary length. A paid text call requires a separately authorized run and server-side `OPENAI_API_KEY`; the default review can stop at the cost preview. Do not authorize a paid image call or bulk operation as part of this check.

If the AI proposal omits a required preservation or profile rule, the saved proposal stays unchanged and the editable adoption draft restores the missing rule. Compare both texts before clicking **Adopt as new version**. A rejected adoption does not create a prompt-history entry. After restarting or reloading, open **Refinement history** and click **Review proposal** to reuse the saved result; no second paid text request is needed. Adoption creates a pending prompt version, which still needs separate prompt approval.

Record prompt usefulness, source hash stability, errors and actual request charges (if a paid trial was explicitly authorized) privately under `data/evidence/`. Evaluate a local prose model only after recording license, pinned files/hashes, verified Windows/Linux CPU package setup, download size, peak memory, latency and quality on the owner pilot. Automated tests do not establish visual correctness or the 200-photo time target.
