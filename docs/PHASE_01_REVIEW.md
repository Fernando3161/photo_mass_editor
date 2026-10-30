# Phase 01 owner photo review

This is the manual acceptance check for the Phase 01 catalog. Run it from the repository root on `dev/v1-phase-01-catalog`. The procedure performs local import and thumbnail generation only; it makes no AI calls or uploads. Keep the sample and all generated evidence private under the Git-ignored `data/` directory. Do not add any of these files to Git.

## 1. Prepare a small private sample

The private review folders do not exist in a fresh clone because `data/` is ignored by Git. Create them with the commands below, then **copy** 10–15 representative photos into `input/`; do not move or edit the originals in your photo archive. A slightly larger set, such as 20 already selected photos, is fine if you review every imported thumbnail. Include, where available, architecture, people, landscapes, sculpture, day and night scenes, portrait and landscape orientations, and photos with and without capture/GPS metadata. JPEG, PNG, TIFF and WebP are supported. RAW/HEIC files and `.xmp`/`.aae` sidecars may be included to check that they are reported, but they will not be imported.

The catalog for this check will live separately at `data/phase01-review/catalog/`. Use a new review folder name if you have already run a previous review; do not delete an existing catalog to reset results. Keep the selected catalog directory stable for the entire review. The import uses the default `reference` mode, so no managed copy is created; the files in `input/` are read only. You may instead set the input path below to a folder outside the repository if you prefer to reference selected originals directly.

### Windows PowerShell

```powershell
$reviewRoot = 'data/phase01-review'
$reviewInput = Join-Path $reviewRoot 'input'
$reviewCatalog = Join-Path $reviewRoot 'catalog'
New-Item -ItemType Directory -Force -Path $reviewRoot, $reviewInput, $reviewCatalog | Out-Null
```

Copy the selected photos into `input/` using File Explorer. The following PowerShell blocks define their own paths, so they also work in a new session. Avoid the variable name `$input`: PowerShell reserves it for pipeline input.

### Linux shell

```bash
review=data/phase01-review
input="$review/input"
catalog="$review/catalog"
mkdir -p "$review" "$input" "$catalog"
```

Copy the selected photos into `input/` using your file manager. Then continue in the **same shell session**.

## 2. Record hashes before import

The hash list stays outside `input/` so it cannot be mistaken for a sidecar.

### Windows PowerShell

```powershell
$reviewRoot = 'data/phase01-review'
$reviewInput = Join-Path $reviewRoot 'input'
$reviewCatalog = Join-Path $reviewRoot 'catalog'
New-Item -ItemType Directory -Force -Path $reviewRoot, $reviewInput, $reviewCatalog | Out-Null
$manifest = Join-Path $reviewRoot 'before.sha256.txt'
if (Test-Path -LiteralPath $manifest) {
    throw 'The before-hash manifest already exists. Keep it and continue with Step 3.'
}
$files = @(Get-ChildItem -LiteralPath $reviewInput -File -Recurse -ErrorAction Stop)
if ($files.Count -eq 0) { throw 'No photos found in the review input folder.' }
$before = @($files | Sort-Object FullName | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256 -ErrorAction Stop
    "$($hash.Hash)  $($_.FullName)"
})
if ($before.Count -ne $files.Count) { throw 'A file could not be hashed.' }
$before | Set-Content -LiteralPath $manifest
"Recorded $($before.Count) input file hashes."
```

### Linux shell

```bash
review=data/phase01-review
input="$review/input"
catalog="$review/catalog"
mkdir -p "$review" "$input" "$catalog"
test -n "$(find "$input" -type f -print -quit)" || { echo 'No photos found in review input' >&2; exit 1; }
find "$input" -type f -exec sha256sum {} + | LC_ALL=C sort > "$review/before.sha256.txt"
```

Check that the manifest lists every file you selected. If the input folder is empty, stop and add photos before continuing.

## 3. Run setup, automated tests, and import

`--data-dir` must appear **before** the subcommand. Run the following from the repository root in PowerShell or a Linux shell. The commands create the review folders even if you open a new shell. `import-folder` initializes a new catalog automatically, so a separate `init` command is optional. First import should report each supported valid file under `imported`, with no `errors`. Known unsupported files appear under `unsupported`; sidecars appear under `sidecars`. If the catalog already contains these photos, import reports them as `existing`; use a new review root for a fresh first-import check.

### Windows PowerShell

```powershell
$reviewRoot = 'data/phase01-review'
$reviewInput = Join-Path $reviewRoot 'input'
$reviewCatalog = Join-Path $reviewRoot 'catalog'
New-Item -ItemType Directory -Force -Path $reviewRoot, $reviewInput, $reviewCatalog | Out-Null
if (-not (Get-ChildItem -LiteralPath $reviewInput -File -Recurse | Select-Object -First 1)) { throw 'Copy photos into the review input folder first.' }
python scripts/setup_env.py
if ($LASTEXITCODE -ne 0) { throw 'Environment setup failed.' }
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed.' }
.\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog import-folder $reviewInput | Tee-Object -FilePath (Join-Path $reviewRoot 'import-first.json')
if ($LASTEXITCODE -ne 0) { throw 'First import failed.' }
.\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog list | Tee-Object -FilePath (Join-Path $reviewRoot 'catalog-list.json')
if ($LASTEXITCODE -ne 0) { throw 'Catalog listing failed.' }
.\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog preflight | Tee-Object -FilePath (Join-Path $reviewRoot 'preflight.json')
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed.' }
```

### Linux shell

```bash
review=data/phase01-review
input="$review/input"
catalog="$review/catalog"
mkdir -p "$review" "$input" "$catalog"
test -n "$(find "$input" -type f -print -quit)" || { echo 'Copy photos into the review input folder first' >&2; exit 1; }
python scripts/setup_env.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m backend.catalog --data-dir "$catalog" import-folder "$input" | tee "$review/import-first.json"
.venv/bin/python -m backend.catalog --data-dir "$catalog" list | tee "$review/catalog-list.json"
.venv/bin/python -m backend.catalog --data-dir "$catalog" preflight | tee "$review/preflight.json"
```

`catalog-list.json` maps each original filename to its UUID, SHA-256, metadata, and thumbnail path. It reports `gps_status` as `VALID`, `ABSENT`, `INCOMPLETE`, `INVALID_REFERENCE`, `INVALID_COORDINATES`, or `UNREADABLE`, without printing coordinates. `INVALID_REFERENCE` means latitude/longitude fields exist but their N/S or E/W direction is missing or invalid; the catalog deliberately leaves both coordinates empty. `city` and `country` are editorial fields and remain empty in Phase 01 even if GPS is valid; no reverse geocoding runs. Keep this JSON private because filenames and source paths may be sensitive. For every imported row, `preflight.json` should show `source: "OK"`, `thumbnail: "OK"`, and `managed: null` in reference mode.

If your phone displays a location for a photo marked `INVALID_REFERENCE`, create the ignored `data/phase01-review/phone-original/` folder (`New-Item -ItemType Directory -Force -Path 'data/phase01-review/phone-original'` in PowerShell or `mkdir -p data/phase01-review/phone-original` on Linux). Copy one unchanged original directly from the phone into that folder. Compare its SHA-256 with the matching file in `input/`, then inspect the phone copy's GPS direction fields. Different hashes show that the reviewed file is not byte-for-byte the phone original; they do not establish which transfer changed it. Matching hashes with empty direction fields mean the phone is displaying a location from another source or interpretation. Do not alter either copy or guess the missing N/S and E/W directions. Ask for a metadata inspection of the phone copy before changing the catalog or importer.

On Windows, after copying the file, compare it without printing the private hashes:

```powershell
$fileName = 'REPLACE_WITH_EXACT_FILENAME.jpg'
$reviewed = Join-Path 'data/phase01-review/input' $fileName
$phoneCopy = Join-Path 'data/phase01-review/phone-original' $fileName
if (-not (Test-Path -LiteralPath $reviewed -PathType Leaf) -or -not (Test-Path -LiteralPath $phoneCopy -PathType Leaf)) { throw 'Both photo copies must exist.' }
"Same bytes: $((Get-FileHash -LiteralPath $reviewed -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $phoneCopy -Algorithm SHA256).Hash)"
```

## 4. Review thumbnails and metadata

Open the PNGs in `data/phase01-review/catalog/thumbnails/` using your normal image viewer. Use `catalog-list.json` to match each UUID thumbnail to its original filename. Compare each thumbnail side by side with the corresponding input photo. Check orientation, framing, aspect ratio, visible image content, and whether any thumbnail is blank, corrupted, or unexpectedly rotated. Check a few captured dates, camera/lens fields, and the GPS-present flag against what you know about the originals. Missing metadata should remain missing rather than being invented. Software tests alone do not establish visual correctness.

Each thumbnail's hexadecimal-looking filename is the catalog photo UUID plus `.png`, not the photo's SHA-256 or original filename. In `catalog-list.json`, find `original_filename`, then open its `thumbnail_path`. Compare at least one landscape and one portrait image, and inspect several different capture dates. For those same records, compare `capture_datetime_raw`, `camera`, `orientation`, `gps_present`, and `gps_status` with the phone's Details view. `lens` may be null when the source EXIF has no lens model. Do not expect `city` or `country` to be filled in Phase 01. Record the owner's visual and metadata result in the phase report without copying private filenames or coordinates into Git.

## 5. Verify source integrity and stable IDs

Do not change files in `input/` between the first and repeat import. Repeat import should report the same photos under `existing`, with no new `imported` rows or `errors`. The IDs should match `import-first.json` and `catalog-list.json`.

### Windows PowerShell

```powershell
$reviewRoot = 'data/phase01-review'
$reviewInput = Join-Path $reviewRoot 'input'
$reviewCatalog = Join-Path $reviewRoot 'catalog'
New-Item -ItemType Directory -Force -Path $reviewRoot, $reviewInput, $reviewCatalog | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $reviewCatalog 'catalog.sqlite') -PathType Leaf)) { throw 'Run the first import before the repeat import.' }
.\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog import-folder $reviewInput | Tee-Object -FilePath (Join-Path $reviewRoot 'import-repeat.json')
if ($LASTEXITCODE -ne 0) { throw 'Repeat import failed.' }
$files = @(Get-ChildItem -LiteralPath $reviewInput -File -Recurse -ErrorAction Stop)
$after = @($files | Sort-Object FullName | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256 -ErrorAction Stop
    "$($hash.Hash)  $($_.FullName)"
})
if ($after.Count -ne $files.Count) { throw 'A file could not be hashed.' }
$after | Set-Content "$reviewRoot/after.sha256.txt"
$before = @(Get-Content "$reviewRoot/before.sha256.txt" -ErrorAction Stop)
if ($before.Count -eq 0 -or (Compare-Object $before $after)) {
    throw 'Input photo hashes or file list changed during review.'
}
'PASS: input file list and SHA-256 hashes are unchanged.'
```

### Linux shell

```bash
review=data/phase01-review
input="$review/input"
catalog="$review/catalog"
mkdir -p "$review" "$input" "$catalog"
test -f "$catalog/catalog.sqlite" || { echo 'Run the first import before the repeat import' >&2; exit 1; }
.venv/bin/python -m backend.catalog --data-dir "$catalog" import-folder "$input" | tee "$review/import-repeat.json"
find "$input" -type f -exec sha256sum {} + | LC_ALL=C sort > "$review/after.sha256.txt"
diff -u "$review/before.sha256.txt" "$review/after.sha256.txt"
```

On Linux, `diff` exits successfully and prints nothing when the file list and hashes match. On Windows, the final command prints `PASS` only when they match. Any mismatch is a Phase 01 failure to investigate before acceptance.

## 6. Close the phase gate

Update `reports/PHASE_01_TECHNICAL_REPORT.md` with the date, number of supported photos, formats observed, first and repeat import counts, preflight result, hash comparison, and visual/metadata observations. Record any failures as `FAIL`; keep unperformed checks as `NOT_RUN`. Keep filenames, precise locations, GPS coordinates, hashes, and generated JSON evidence in ignored `data/`, not in the report or Git. If the real-photo review passes, change its row from `NOT_RUN` to `PASS` with a short evidence summary. The owner then reviews the phase diff, manually stages and commits it, and decides whether to merge and authorize Phase 02.

The CI row can be closed after the owner manually commits and pushes this branch and the Windows and Linux jobs pass. If those jobs are not run, keep that row `NOT_RUN` and record the reason. Do not claim Phase 01 complete while an original-integrity or privacy failure remains unresolved.

## Troubleshooting and reruns

- A fresh clone has no `data/phase01-review/` because `data/` is Git-ignored. Run the Step 1 directory commands before copying photos. Step 3 also creates the required folders, then stops with a clear message if `input/` is empty. The catalog and thumbnail subdirectories are created on demand by the importer.
- In PowerShell, `$input` is an automatic variable. Using it for the photo path caused `Get-ChildItem -LiteralPath $input` to receive an empty string during the first owner review. Use `$reviewInput` as shown. The `>>` text shown by an interactive PowerShell prompt is a continuation prompt, not part of a command to paste.
- A first import into an existing catalog reports `existing`, not `imported`. For a clean review, choose a new ignored review root and change `$reviewRoot` (or `review`) in every block. You may point its input variable at the existing unchanged photo folder; do not move, delete, or overwrite source photos or an earlier catalog. Capture the new before-hash manifest before the new first import.
- If a photo shows a location on the phone but `gps_status` is `INVALID_REFERENCE` or `ABSENT`, inspect an unchanged direct phone copy. The first review copies had unusable GPS direction fields; the directly copied phone files had valid GPS. The specific transfer step that changed the first copies was not proven.
