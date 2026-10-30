# Phase 02 owner review — desktop catalog workstation

Run this procedure from the repository root. It creates every ignored review directory it needs. Keep the sample photographs and catalog under `data/`; do not add them to Git.

The Phase 02 workstation is local only. It makes no AI calls, uploads, or image edits. The right comparison pane is intentionally empty and labeled **Not edited yet** because editing begins in Phase 04.

## Windows PowerShell

### 1. Prepare the private review area

```powershell
$reviewRoot = 'data/phase02-review'
$reviewInput = Join-Path $reviewRoot 'input'
$reviewCatalog = Join-Path $reviewRoot 'catalog'

New-Item -ItemType Directory -Force -Path $reviewRoot, $reviewInput, $reviewCatalog | Out-Null
```

Copy 10–20 representative owner photographs into `data/phase02-review/input/`. Include portrait and landscape orientation, people, buildings, landscapes, day/night, GPS and non-GPS files when available. Then verify the input:

```powershell
$reviewFiles = Get-ChildItem -LiteralPath $reviewInput -File -Recurse
if ($reviewFiles.Count -eq 0) { throw "No review photographs found in $reviewInput" }
$reviewFiles | Select-Object FullName, Length
```

Capture source hashes before any catalog operation:

```powershell
$reviewFiles |
    Sort-Object FullName |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "$($hash.Hash)  $($_.FullName)"
    } | Set-Content (Join-Path $reviewRoot 'before.sha256.txt')
```

Use `$reviewInput`, not PowerShell's automatic `$input` variable.

### 2. Set up and run automated checks

```powershell
python scripts/setup_env.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
```

`setup_env.py` verifies that Python runs from `.venv`, installs the exact Python lock, requires Node.js 22 or newer, and installs the exact frontend lock with `npm ci`.

### 3. Build a separate Phase 02 catalog

Use a new catalog or reuse its existing source folder. Do not import the same photographs from a second folder into an existing catalog: ingestion intentionally keeps identical bytes from distinct source paths as separate duplicate-candidate records, so both records will appear in the workstation. Repeating the command with the same `$reviewInput` paths is idempotent.

Before importing, check whether this review catalog already contains records:

```powershell
if (Test-Path (Join-Path $reviewCatalog 'catalog.sqlite')) {
    .\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog list
    Write-Host 'Existing catalog found. Confirm it already references this review input before importing.'
}
```

```powershell
.\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog import-folder $reviewInput
.\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog list
.\.venv\Scripts\python.exe -m backend.catalog --data-dir $reviewCatalog preflight
```

Expected: the catalog row count equals the number of intended input photographs, catalog listing succeeds, and every source and thumbnail is `OK`. If the row count is twice the input count, stop before reviewing and inspect duplicate hashes/source paths. The import references source files by default and does not alter them.

### 4. Start the workstation

```powershell
.\.venv\Scripts\python.exe -m backend.review --data-dir $reviewCatalog --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> in a desktop browser. Keep the terminal open while reviewing. Stop the server with `Ctrl+C` when finished.

### 5. Verify source integrity

After stopping the workstation, recalculate and compare hashes:

```powershell
$reviewFiles = Get-ChildItem -LiteralPath $reviewInput -File -Recurse
$reviewFiles |
    Sort-Object FullName |
    ForEach-Object {
        $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        "$($hash.Hash)  $($_.FullName)"
    } | Set-Content (Join-Path $reviewRoot 'after.sha256.txt')

$before = Get-Content (Join-Path $reviewRoot 'before.sha256.txt')
$after = Get-Content (Join-Path $reviewRoot 'after.sha256.txt')
if (Compare-Object $before $after) { throw 'Source photo hashes changed' }
'Source hashes match.'
```

## Linux shell

```bash
review_root='data/phase02-review'
review_input="$review_root/input"
review_catalog="$review_root/catalog"
mkdir -p "$review_root" "$review_input" "$review_catalog"
find "$review_input" -type f -print -quit | grep -q . || { echo "No review photographs found in $review_input" >&2; exit 1; }
find "$review_input" -type f -print0 | sort -z | xargs -0 sha256sum > "$review_root/before.sha256.txt"

python scripts/setup_env.py
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build

if [ -f "$review_catalog/catalog.sqlite" ]; then
  .venv/bin/python -m backend.catalog --data-dir "$review_catalog" list
  echo 'Existing catalog found. Confirm it already references this review input before importing.'
fi
.venv/bin/python -m backend.catalog --data-dir "$review_catalog" import-folder "$review_input"
.venv/bin/python -m backend.catalog --data-dir "$review_catalog" list
.venv/bin/python -m backend.catalog --data-dir "$review_catalog" preflight
.venv/bin/python -m backend.review --data-dir "$review_catalog" --host 127.0.0.1 --port 8000
```

After stopping the server:

```bash
find "$review_input" -type f -print0 | sort -z | xargs -0 sha256sum > "$review_root/after.sha256.txt"
diff -- "$review_root/before.sha256.txt" "$review_root/after.sha256.txt"
```

## Manual acceptance checklist

Record PASS, FAIL, or NOT_RUN for each item in the Phase 02 report.

- The filmstrip stays at the top, scrolls horizontally, marks the current photo, and remains responsive with the complete catalog.
- **Grid** opens a contact sheet and selecting any thumbnail jumps directly to that photo.
- Left and right arrow keys move between photos; `G` opens the grid when focus is outside a form field.
- The left comparison pane displays the selected original. The right pane clearly says **Not edited yet** and does not imply an edit exists.
- Search and status, subject, tag, city, and month filters narrow the collection as expected.
- Description, city/country, optional primary subject, multiple content tags, and multiple condition tags can be entered.
- The visible status progresses through **Unsaved changes**, **Saving**, and **All changes saved**. Reloading the page preserves saved data.
- **Save & next**, **Mark reviewed & next**, and **Next unreviewed** move to the correct item. Edited unreviewed records become **In progress** until explicitly marked reviewed.
- The three draft presets can be selected. Editing a preset visibly changes its version. The allowance and suggestion fields do not run AI or generate an image.
- Precise latitude/longitude and original filesystem paths never appear in the page or photo-detail response. The UI may show only that GPS is present.
- Statuses have text labels and controls have readable keyboard focus and accessible names; meaning does not depend on color alone.
- Source hashes match before and after the review.

## Failed-save recovery check

This check is safe and uses only local state:

1. With the page already loaded, stop the local server.
2. Change a description and wait for **Save failed**. Do not clear browser storage.
3. Restart the same server command and reload the page.
4. Confirm **Unsaved draft recovered** appears and the changed text is present.
5. Wait for **All changes saved**, reload once more, and confirm the value persists.

## Evidence and approval

Keep screenshots and hash manifests under `data/phase02-review/`. Update `reports/PHASE_02_TECHNICAL_REPORT.md` with the manual results. Automated tests do not establish visual correctness or review efficiency. Phase 02 remains pending until the owner completes this checklist and manually reviews the unstaged changes.
