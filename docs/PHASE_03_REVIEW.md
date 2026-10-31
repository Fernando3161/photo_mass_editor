# Phase 03 owner review — analysis and prompt assembly

Phase 03 adds opt-in analysis orchestration and versioned prompt assembly. No production AI provider is selected or configured in this phase, and the review below makes no paid call. Provider behavior is verified with an injected fake in automated tests.

Run from the repository root. Keep catalogs and backups under ignored `data/`.

## Windows PowerShell

```powershell
$reviewRoot = 'data/phase03-review'
$backupRoot = Join-Path $reviewRoot 'backups'
$catalogRoot = 'data/phase02-review/catalog'
$catalogFile = Join-Path $catalogRoot 'catalog.sqlite'
New-Item -ItemType Directory -Force -Path $reviewRoot, $backupRoot | Out-Null
if (-not (Test-Path -LiteralPath $catalogFile -PathType Leaf)) { throw "Catalog missing: $catalogFile" }

python scripts/setup_env.py

@'
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
source = Path('data/phase02-review/catalog/catalog.sqlite')
target = Path('data/phase03-review/backups') / f"catalog-before-phase03-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite"
with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
with sqlite3.connect(target) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
print(target)
'@ | .\.venv\Scripts\python.exe -

.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m backend.review --data-dir $catalogRoot --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Starting the service applies pending migrations through 5 after the verified backup. If the service was already running, reload the page to refresh the preset list.

## Linux shell

```bash
review_root='data/phase03-review'
backup_root="$review_root/backups"
catalog_root='data/phase02-review/catalog'
mkdir -p "$review_root" "$backup_root"
test -f "$catalog_root/catalog.sqlite" || { echo 'Phase 02 catalog is missing' >&2; exit 1; }

python scripts/setup_env.py

.venv/bin/python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
source = Path('data/phase02-review/catalog/catalog.sqlite')
target = Path('data/phase03-review/backups') / f"catalog-before-phase03-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite"
with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
with sqlite3.connect(target) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
print(target)
PY

.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
.venv/bin/python -m backend.review --data-dir "$catalog_root" --host 127.0.0.1 --port 8000
```

## Manual checklist

- Existing Phase 2 metadata still loads after migration and schema version is 5.
- The draft-preset menu includes Natural balance, Architecture clarity, Portrait gentle, Museum artwork, Group photo, Night architecture, Food, and Panoramic scene. Selecting a new preset shows its instructions and includes them in the compiled prompt.
- The displayed 4000×3000 (or other source-size) image is for review. Phase 03 creates no publication derivative; Phase 04 must create the selected maximum-1600-pixel JPEG before generative editing.
- The editing draft shows **Website standard v1**: JPEG, maximum long edge 1600 px, quality 85, sRGB, preserved aspect ratio, no upscaling, and stripped metadata.
- **Preview analysis cost** reports that no production provider is configured. It must not make a network or paid call.
- Analysis controls require the explicit authorization checkbox and state that authorization applies to the current click only.
- Enter or edit the suggestion, owner instructions, and approved constraints independently; autosave persists each field.
- Set allowance above 3 without semantic-change consent. Prompt compilation is blocked with a clear consent conflict.
- Add `Keep the sky unchanged` as a constraint and `Replace the sky with sunset` as an owner instruction. Compilation is blocked with a sky conflict.
- Resolve the conflict and compile. The preview shows the selected subject/tags, preset version, publication profile, suggestion, owner instruction, constraint, allowance, and the rule that the future generative input is the publication derivative rather than the original.
- Edit the compiled prompt and choose **Save as new version**. Prompt history shows a new immutable owner-edited version.
- Approve the current version. Change any draft field and confirm the older prompt can no longer be approved until a new prompt is compiled.
- Reload and confirm prompt history and approval remain stored.
- Browser responses and built frontend contain no API key, precise GPS, raw provider response, source hash, or filesystem path.
- Source-photo hashes remain unchanged; Phase 3 creates no edited image.

## Database inspection

Open `data/phase02-review/catalog/catalog.sqlite` with a SQLite viewer. Analysis provenance is in `analysis_runs`; immutable prompt versions and their publication-profile snapshots are in `compiled_prompts`; editable fields and the selected profile are in `review_drafts`; `publication_profiles` contains the exact versioned settings. `publication_inputs` remains empty until Phase 04 creates validated derivatives.

```sql
SELECT photo_id, version_number, user_modified, approved_for_job,
       publication_profile_id, publication_profile_snapshot_json,
       generated_at, approved_at, compiled_text
FROM compiled_prompts
ORDER BY photo_id, version_number;

SELECT id, version, image_format, max_long_edge, quality, color_space,
       preserve_aspect_ratio, allow_upscale, strip_metadata
FROM publication_profiles;
```

The raw provider response is retained only in SQLite for provenance and is never returned by the review API. Keep this database and its backups private.
