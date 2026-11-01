# Phase 04 owner review — editing and immutable versions

For a smaller first trial with exactly two separately authorized OpenAI image edits, one at 0/10 reimagining and one at 2/10, follow [the first two-image trial](FIRST_TWO_IMAGE_TRIAL.md).

This procedure tests a **new** private batch of up to 20 owner photos from import through edited-image retrieval and explicit review. Export follows local catalog prefill in Phase 06. The default editing provider is unavailable; all local deterministic runs and automated tests cost $0. Real image editing requires a separate, authorized one-photo trial.

Run commands from the repository root. Stop any older review server before starting this phase's server. Keep source photos, catalogs, backups, masks, and edited outputs under ignored `data/`.

## Windows PowerShell: prepare and test locally

Create the private folders first:

```powershell
New-Item -ItemType Directory -Force -Path 'data/phase04-review/input', 'data/phase04-review/catalog', 'data/phase04-review/backups', 'data/phase04-review/evidence' | Out-Null
```

Copy the selected photos into `data/phase04-review/input/` using your file manager. Then verify that input exists and record hashes:

```powershell
$files = @(Get-ChildItem -LiteralPath 'data/phase04-review/input' -File -Recurse)
if ($files.Count -eq 0) { throw 'Copy selected photos into data/phase04-review/input before continuing.' }
$files | Sort-Object FullName | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash)  $($_.Path)" } | Set-Content 'data/phase04-review/evidence/source-before.sha256.txt'
```

Set up the canonical environment, then back up an existing catalog **before** a command applies migration 006. For a fresh catalog the backup block prints a message and leaves the new catalog directory empty.

```powershell
python scripts/setup_env.py
@'
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
source = Path('data/phase04-review/catalog/catalog.sqlite')
target_dir = Path('data/phase04-review/backups')
target_dir.mkdir(parents=True, exist_ok=True)
if source.is_file():
    target = target_dir / f"catalog-before-phase04-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    with sqlite3.connect(target) as check:
        assert check.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    print(f'Verified backup: {target}')
else:
    print('Fresh catalog: no prior database to back up')
'@ | .\.venv\Scripts\python.exe -
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend test -- --run
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog import-folder data/phase04-review/input
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog preflight
.\.venv\Scripts\python.exe -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The server remains running until `Ctrl+C`. Use a different terminal for the after-review hash command below.

## Linux shell: prepare and test locally

Create the private folders first:

```bash
mkdir -p data/phase04-review/input data/phase04-review/catalog data/phase04-review/backups data/phase04-review/evidence
```

Copy the selected photos into `data/phase04-review/input/` using your file manager, then run:

```bash
find data/phase04-review/input -type f -print -quit | grep -q . || { echo 'Copy selected photos into data/phase04-review/input before continuing.' >&2; exit 1; }
find data/phase04-review/input -type f -print0 | sort -z | xargs -0 sha256sum > data/phase04-review/evidence/source-before.sha256.txt
python scripts/setup_env.py
.venv/bin/python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
source = Path('data/phase04-review/catalog/catalog.sqlite')
target_dir = Path('data/phase04-review/backups')
target_dir.mkdir(parents=True, exist_ok=True)
if source.is_file():
    target = target_dir / f"catalog-before-phase04-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite"
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    with sqlite3.connect(target) as check:
        assert check.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    print(f'Verified backup: {target}')
else:
    print('Fresh catalog: no prior database to back up')
PY
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend test -- --run
npm --prefix frontend run build
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog import-folder data/phase04-review/input
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog preflight
.venv/bin/python -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

## Manual workstation checklist

1. For one representative photo, save the editing draft, compile a prompt, inspect it, and approve that exact version. The photo shown on the left may still be 4000×3000: that is the original review view.
2. Open the **1600px publication input** link. Inspect that separate image: JPEG, sRGB, long edge at most 1600 pixels, original aspect ratio, no enlargement, and no private EXIF/GPS. The catalog records its source and profile hashes. The original must remain unchanged.
3. Select **Local deterministic correction** and a visible setting such as exposure 1.10. Preview the selected run, inspect the per-photo prompt, check the current-run authorization box, then start. Watch the job receipt. A successful job creates a **PENDING** version; it is not approved automatically.
4. Select the new version in the timeline. Compare both sides, download the selected JPEG, and inspect it outside the browser. Reject it with a reason. Previewing an identical retry should require the explicit retry override; a changed setting or changed approved prompt is a separate attempt.
5. Run a second local correction and approve its pending version. Confirm that the rejected version remains available and that the default batch preview excludes the approved photo.
6. For a fuller local batch, save and approve a prompt for each of the remaining photos. Select **First 20 visible photos**, preview eligibility and each prompt, then authorize and run local deterministic corrections. Inspect all returned versions individually; batch success never grants approval.
7. Optional mask path: open the publication input and create a separate transparent PNG of identical dimensions in an image editor. Transparent pixels mark the requested edit area; opaque pixels mark the protected area. Upload it for a **single** generative photo. The mask guides the model but does not guarantee unchanged protected pixels.
8. Stop the server, run catalog `preflight` again, and compare source hashes. Check ignored `data/phase04-review/catalog/publication-inputs/` and `edited/{raw,versions}/` for distinct files. No original, API key, or edited image belongs in Git.

PowerShell after-review source check, from a fresh terminal:

```powershell
if (-not (Test-Path -LiteralPath 'data/phase04-review/evidence/source-before.sha256.txt' -PathType Leaf)) { throw 'Missing before-hash evidence.' }
$files = @(Get-ChildItem -LiteralPath 'data/phase04-review/input' -File -Recurse)
if ($files.Count -eq 0) { throw 'Review input photos are missing.' }
$files | Sort-Object FullName | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash)  $($_.Path)" } | Set-Content 'data/phase04-review/evidence/source-after.sha256.txt'
if (Compare-Object (Get-Content 'data/phase04-review/evidence/source-before.sha256.txt') (Get-Content 'data/phase04-review/evidence/source-after.sha256.txt')) { throw 'Source hashes differ; stop review.' }
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog preflight
```

Linux after-review source check, from a fresh shell:

```bash
test -f data/phase04-review/evidence/source-before.sha256.txt || { echo 'Missing before-hash evidence' >&2; exit 1; }
find data/phase04-review/input -type f -print -quit | grep -q . || { echo 'Review input photos are missing' >&2; exit 1; }
find data/phase04-review/input -type f -print0 | sort -z | xargs -0 sha256sum > data/phase04-review/evidence/source-after.sha256.txt
cmp data/phase04-review/evidence/source-before.sha256.txt data/phase04-review/evidence/source-after.sha256.txt
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog preflight
```

## Optional one-photo OpenAI trial

Complete the local checks first. A key or prepaid credit is **not** required for them. For a live trial, create a project API key in your OpenAI Platform account and put its secret value in the private `config/openAI.env` file as described below. The [official quickstart](https://developers.openai.com/api/docs/quickstart) describes key setup; the [Image API edit reference](https://developers.openai.com/api/reference/python/resources/images/methods/edit) documents the edit request. Model access and any organization verification depend on your account.

The server automatically loads `config/openAI.env` when started with `python -m backend.review`. It does not load the old root-level `openAI.env`. Copy `config/openAI.example.env` to `config/openAI.env` once, replace `YOUR_KEY_HERE` with the **secret key value** (not the key tracking ID), and replace `YOUR_ESTIMATE_HERE` with a positive per-image planning estimate. The private copy is ignored by Git; the example is safe to commit. Process environment variables take precedence over file values. Keep the real key out of reports and screenshots.

The example selects `gpt-image-2.5-sunburst`; change `PHOTO_EDIT_MODEL` to `gpt-image-2.5-flare` only if intended. Use the [official image generation cost calculator](https://developers.openai.com/api/docs/guides/image-generation) for a conservative per-image planning amount. It is an application **estimate and run gate**, not a provider-enforced spending limit; the provider response supplies usage but no invoice amount. Check actual account usage after the trial. A $5 credit balance does not guarantee a particular number of edits.

In a **new** PowerShell server terminal, from the repository root (edit the copied file in your IDE before starting):

```powershell
if (-not (Test-Path -LiteralPath 'data/phase04-review/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Phase 04 catalog is missing.' }
if (-not (Test-Path -LiteralPath 'config/openAI.env' -PathType Leaf)) { Copy-Item -LiteralPath 'config/openAI.example.env' -Destination 'config/openAI.env'; throw 'Fill in config/openAI.env in your IDE, then rerun the server command.' }
.\.venv\Scripts\python.exe -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

In a **new** Linux server shell (edit the copied file before starting):

```bash
test -f data/phase04-review/catalog/catalog.sqlite || { echo 'Phase 04 catalog is missing' >&2; exit 1; }
test -f config/openAI.env || { cp config/openAI.example.env config/openAI.env; echo 'Fill in config/openAI.env, then rerun the server command.' >&2; exit 1; }
.venv/bin/python -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

In the UI, choose one non-sensitive photo with an approved current prompt, select **Generative image edit**, preview cost and prompt, set the run budget at or above the estimate, and explicitly authorize that one run. Inspect the returned pending image and account usage before trying another. Do not run the 20-photo paid batch as the first live test. Never paste a key into the browser, commit it, or send it in a report.

If the service or computer stops during a provider call, the job is marked failed on restart because the call may already have been billed. A queued generative call is also not resumed without a new authorization. Inspect the receipt and account usage before any retry.
