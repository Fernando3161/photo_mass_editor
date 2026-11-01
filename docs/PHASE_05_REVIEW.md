# Phase 05 owner review — local catalog prefill

Use the existing Phase 04 catalog for a small pilot. The application migrates its SQLite schema to version 7 on first startup. Back up the catalog first. The local recognition model reads verified 512 px thumbnails; it does not call the OpenAI API, spend API credit, or upload a photograph. The first online recognition downloads about 157 MB of pinned model files automatically into ignored `data/models/`. The model card lists an MIT license. Model scores are relative similarities, so inspect each suggested label, tag, description, preset, and city before accepting.

## Windows PowerShell, from a fresh repository shell

```powershell
New-Item -ItemType Directory -Force -Path 'data/phase05-review/evidence' | Out-Null
if (-not (Test-Path -LiteralPath 'data/phase04-review/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Phase 04 catalog is missing. Import selected photos first.' }
python scripts/setup_env.py
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Repository virtual environment is missing.' }
.\.venv\Scripts\python.exe scripts/phase05_audit.py --data-dir data/phase04-review/catalog --evidence-dir data/phase05-review/evidence --stage before
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog preflight
.\.venv\Scripts\python.exe -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

## Linux, from a fresh repository shell

```bash
mkdir -p data/phase05-review/evidence
test -f data/phase04-review/catalog/catalog.sqlite || { echo 'Phase 04 catalog is missing. Import selected photos first.' >&2; exit 1; }
python scripts/setup_env.py
test -f .venv/bin/python || { echo 'Repository virtual environment is missing.' >&2; exit 1; }
.venv/bin/python scripts/phase05_audit.py --data-dir data/phase04-review/catalog --evidence-dir data/phase05-review/evidence --stage before
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog preflight
.venv/bin/python -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

If the Phase 04 catalog is missing or has too few photos, follow the [Phase 04 import instructions](PHASE_04_REVIEW.md) first. They create the private input/catalog directories and verify that photos exist before import. Import never mutates source files.

## Pilot in the browser

1. Open `http://127.0.0.1:8000`. Select about 20 varied photos. If the existing catalog has fewer, import more selected photos first. Do not start with all 200.
2. In **Private visited cities**, enter a city/country, representative latitude and longitude, and matching radius in kilometers. Add each city once. The browser never receives the stored precise coordinates after saving. To correct one, select it, reenter all its fields including coordinates, and click **Update selected city**; an unused entry can be removed. Start with a modest radius; overlapping nearby cities can produce an ambiguous result.
3. In **Catalog suggestions**, check **Authorize this local recognition run**. Click **Suggest current photo** or **Suggest first 20 visible**. The button stays disabled until checked. The first online run downloads and verifies the model automatically; the panel shows download progress or a failure. A repeated run with the same source, model settings, and city revisions reuses the saved suggestion. Check **Offline** to require the verified cache and block model-host access.
4. Inspect the proposed subject, content/condition tags, short description, preset, top model matches, and GPS match status. `MATCH` shows city/country and distance; `AMBIGUOUS`, `UNMATCHED`, and `NO_GPS` leave location blank. An opera-house suggestion is a category, not an exact building identity. Correct anything uncertain in the normal metadata fields.

   When entering content or condition tags manually, separate them with commas. Existing tags of the same kind appear as you type; press Tab or Enter to complete a suggestion. City and country likewise suggest existing catalog and visited-city names. You can enter a new value without selecting a suggestion. The edit panel opens on **Generative image edit** with a **0.10 USD** planning budget. An edit still requires a preview, a budget that covers its displayed estimate, and current-run authorization before **Start authorized run** becomes available.
5. For one photo, tick only the suggestion fields you want and click **Accept selected empty fields**, or **Dismiss**. Existing subject, description, preset, city, and country are preserved. New tags may be appended. Acceptance marks compiled prompts stale and revokes prior prompt approval; it does not authorize edits or approve versions. **Undo acceptance** works until someone changes the resulting metadata.
6. For a prepared batch, inspect the listed photo/label/location summaries and click **Accept selected fields in prepared batch** if they are appropriate. This is bounded to 20; partial failures are shown, and successfully accepted rows remain undoable. Use **Undo batch acceptances** immediately if needed. Open individual photos to correct uncertain or wrong suggestions before any prompt compilation.
7. For photos without GPS, choose a visited city under **Bulk location for empty fields**. Preview the first 20 visible photos, inspect eligible/skipped counts, then apply. Existing editorial locations are skipped. Use **Undo last bulk assignment** before further edits if needed. An outdated preview is rejected.
8. Check a representative mix of architecture, people, landscape, food, day/night, GPS, and no-GPS photos. Record incorrect and blank suggestions and whether manual work was reduced. Keep the 200-photo run for a separate owner decision after this pilot.

Stop the server with Ctrl+C. Verify original hashes again:

```powershell
.\.venv\Scripts\python.exe scripts/phase05_audit.py --data-dir data/phase04-review/catalog --evidence-dir data/phase05-review/evidence --stage after
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog preflight
```

```bash
.venv/bin/python scripts/phase05_audit.py --data-dir data/phase04-review/catalog --evidence-dir data/phase05-review/evidence --stage after
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog preflight
```

For offline preparation on another fresh machine, run `python scripts/setup_env.py --prefetch-model` while online. Later local runs can check **Offline**. The cache and SQLite backups remain private under `data/`; do not commit them. Owner visual and labeling review is the Phase 05 acceptance gate.
