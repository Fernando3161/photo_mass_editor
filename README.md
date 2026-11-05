# Photo Mass Editor

A local photography catalog, review workstation, and controlled editing pipeline. Originals stay unchanged. Every edit is a separate version; only an image you explicitly approve can enter a website collection.

Current release: **V1.0.0**. See [release notes and known limits](docs/V1_RELEASE_NOTES.md).

| Original photo | Owner-approved generative edit |
| :---: | :---: |
| ![Original Budapest Opera House photograph](docs/assets/opera-house-before.jpg) | ![Edited Budapest Opera House photograph](docs/assets/opera-house-after.jpg) |

These small, metadata-free previews come from the owner's photo 15 trial. The edit adjusts perspective and removes people; it is a generated interpretation, not documentary evidence of an empty scene. Full-size photographs are not in this repository.

### Japan garden — AI reimagining 1/10

**Before — original photograph**

![Original Japan garden photograph](docs/assets/japan_garden_before.jpg)

**After — owner-approved generative edit**

![Approved AI edit of the Japan garden photograph](docs/assets/japan_garden_after.jpg)

These downscaled, metadata-free previews show an approved generative edit made with the application's AI reimagining allowance set to **1/10**. The allowance is an internal application setting, not a guarantee that every detail remains unchanged. Full-size photographs are not in this repository.

## Quick start on Windows

Install [Python 3.11+](https://www.python.org/downloads/) and [Node.js 22+](https://nodejs.org/) so that Python and npm are on PATH. Open PowerShell in the cloned repository and run:

    powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1

Before the first run, copy your selected original photos into `data/input/` (create that folder if needed). This one script creates the ignored data folders and repository-local Python environment, installs pinned Python and Node dependencies, imports supported photos in `data/input/`, builds the website when its source changed, opens the browser, and starts the server. Leave the terminal open; press Ctrl+C to stop. Rerun it after adding photos or updating the repository. It also starts with an empty catalog if no supported photos are present yet.

The launcher checks the existing catalog's source hashes and private media before importing. If you replaced the input with an unrelated batch, it stops instead of combining that batch with stale records. See [Restart the catalog](#restart-the-catalog) for a reversible reset. A SQLite snapshot alone does not include thumbnails or edits.

On a fresh clone on another Windows laptop, `data/` is absent because it is private and ignored by Git. Copy that laptop's photos into `data/input/` and run the launcher once; it creates `data/catalog/catalog.sqlite`, thumbnails, and the other generated folders automatically. Direct service startup through the repository's `.venv` Python now performs the same catalog preparation when the environment and frontend are already set up. Startup stops if any supported photo fails to import. If you also copied an old `data/catalog/`, it is an existing catalog, not a fresh install: restore/relink its original files or archive it before starting a different batch. The catalog stores source paths for the laptop where each photo was imported.

The terminal prints a one-run username and password and a local URL. Enter those credentials in the browser prompt. LAN access is explicit: add `-Lan` to the Windows command. Other devices on the same trusted private network can then use the printed LAN URL. If Windows Firewall asks, allow Python only on **private** networks. The launcher uses plain HTTP; see [Security and privacy](#security-and-privacy).

The default binds to `127.0.0.1`. A first installation still needs access to the pinned Python and Node packages; an existing verified installation can restart offline. `-Check -NoBrowser` verifies setup, catalog and bundle without starting the server.

To change the port or keep the browser closed:

    powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Port 8001 -NoBrowser

No provider key is required for cataloging, local recognition, deterministic corrections, or export.

### Where to copy original photos

Copy selected originals directly into data/input/ before starting, or add more later and rerun the launcher. It creates data/input/ if absent. JPEG, PNG, TIFF, and WebP are supported. RAW and HEIC are reported as unsupported. Keep an independent private backup of the originals.

Import defaults to **reference** mode: the app records each original's path and SHA-256 and reads it without changing its bytes. Leave the files in data/input/ after import. The catalog, thumbnails, attempts, exports, model, and backups live in ignored data/ folders. Do not put data/ on public hosting.

To import originals from another location after setup, run from the repository root:

    & .\.venv\Scripts\python.exe -m backend.catalog import-folder "<YOUR_PHOTO_FOLDER>"

Those originals remain in that external folder. The launcher automatically imports only data/input/. Repeat imports are safe; existing photos are reported.

### Linux quick start

With Python 3.11+ and Node.js 22+ on PATH, run from the repository root:

    bash scripts/start.sh

Copy selected photos into `data/input/` first, creating the folder if needed. The Linux launcher creates required folders, verifies `.venv` and the catalog, imports supported photos, reuses a current production bundle, and starts on loopback with a new password. Open the printed local URL in your browser and use the printed username and password; press Ctrl+C to stop. Use `bash scripts/start.sh --check` for a setup check without serving, or `bash scripts/start.sh --lan-host 192.168.1.20` for explicit protected LAN binding (replace the address with this computer's LAN IPv4). The password protects requests, but LAN HTTP is unencrypted.

## Everyday workflow

### 1. Find and inspect a photo

The top filmstrip jumps to a photo; the contact sheet gives a wider overview. Press G to open it when you are not typing. Left and right arrows navigate outside editable fields. The left column shows the original above the selected edit; it says “Not edited yet” before a version exists. Filters and search find work by status, subject, tags, or location.

### 2. Fill out Catalog and draft

**Primary subject** is one main visible subject, or empty when none is clear. For the example, enter “Budapest Opera House” only after checking the building yourself. A local suggestion like “opera house” identifies a category, not an exact landmark.

**Content tags** describe several visible things, separated by commas, such as “architecture, facade, street”. **Condition tags** describe photographic conditions, such as “daylight, hard shadows” or “night, haze”. Tab or Enter accepts an autocomplete suggestion. You can also type a new value. These multi-value fields are independent of the one primary subject.

Write a short **Description** of what can be seen. Enter **City** and **Country** only when known; for this example use “Budapest” and “Hungary” after verification. Precise GPS stays private. The export includes editorial city/country only when both were entered or accepted. Set **Review status** as you work. **Save & next** persists the form and moves on. **Mark reviewed & next** also marks the catalog record reviewed. Watch the save indicator for errors.

Choose a **Publication profile** and **Draft preset**. The default website profile makes a JPEG in sRGB with a maximum 1600-pixel long edge, quality 85, preserved aspect ratio, no upscaling, and stripped metadata. Inspect any preset's instructions before using it.

The **AI reimagining allowance** is an app policy scale, not a provider fidelity guarantee. Start with a local deterministic correction for ordinary travel photos. **AI suggested corrections** contains editable machine suggestions; **My additional instructions** is your own request; **Approved constraints** states what to preserve. For example: “Keep architectural ornament and signage faithful.” Removing people or reconstructing architecture changes scene meaning, so check semantic-change consent only when you deliberately authorize it.

### 3. Optional local catalog suggestions

Expand **Catalog suggestions**. Authorize the current local recognition run and choose the current photo or up to 20 visible photos. First use may download a pinned model into ignored data/models/; it verifies and caches the files. Offline mode requires the verified cache. Recognition uses local thumbnails and does not upload photos. Review the proposed subject, tags, description, preset, and location match. Accept correct fields, dismiss the rest, or undo an acceptance. Existing owner-entered fields are preserved.

Under **Private visited cities**, enter a city, country, center coordinates, and matching radius. The app matches private photo GPS to this list. Ambiguous or unmatched locations remain unconfirmed. For photos without GPS, preview a bounded bulk assignment, apply it only to empty locations, and undo if needed. Confirm every editorial location before export.

### 4. Optional prompt for generative editing

For a generative edit, open **Analysis and final prompt**. Paid analysis is optional and the default analysis provider is unavailable. You can write your own instructions without it. Click **Compile prompt preview**, read the full text and any conflict warning, edit if needed, then **Save as new version**. Click **Approve current prompt** on the version you want. Saving photo metadata or draft changes makes approval stale; compile and approve again. Local correction does not use this prompt.

### 5. Create and review an edit

Open **Editing and versions**. Local correction is preselected and loads a recommendation for this photo. Review the preset and levels, exposure, color balance, shadows, and highlights. Optionally adjust denoise, sharpen, straighten, lens/perspective, or crop; use **Reset** to restore the recommendation. **Live preview while adjusting** is enabled by default: moving a slider automatically refreshes the reduced-resolution preview, while **Refresh preview** remains available as a fallback. **Create local version** performs the separate full-resolution render. This path requires no compiled prompt, budget, or paid-run checkbox. It creates a full-resolution PNG master and a separate website JPEG; both start private, and the JPEG begins **PENDING**. Choose **Generative image edit** only for a deliberate provider operation. Its input is a validated publication-sized derivative, never the original. An optional transparent PNG mask must match it; a mask cannot guarantee protected pixels stay unchanged.

For generative editing, click **Preview selected run** and inspect eligibility, prompt version, settings, and estimate. Enter a planning budget at least as large as the estimate. This is an app gate, not a provider spending cap. Check **I authorize this current paid run**, then **Start authorized run**. The first-20-visible batch remains available for this path. Every attempt has a receipt and immutable version. Success creates a **PENDING** version, never automatic approval.

Select the version and compare it with the original, including edges, faces, text, geometry, and reconstructed areas. Click **Approve selected** only after visual review, or **Reject selected** and revise the instructions. Rejected versions remain in history. Default batches skip approved photos and avoid identical rejected attempts without the explicit retry override.

To improve a photo that already has an approved version, check **Create a replacement for the approved version** in local correction, or enable replacement mode for a generative selection. The new version starts PENDING while the existing approval remains active. After comparing it, use **Approve and replace current**. The prior version stays downloadable and is labeled SUPERSEDED; only the new approval is eligible for export. Rejecting the candidate leaves the prior approval unchanged.

### 6. Export approved photos

Open **Website collection**. Click **Preview approved collection**; check the count and location status. Check export authorization, then **Export approved collection**. A new folder appears under data/exports/. Its images/ JPEGs are byte-for-byte copies of approved website versions. thumbnails/ has separate small images; manifest.json contains privacy-filtered editorial metadata; cost_report.json separates planning estimates, usage calculations, reconciled billing and unknown charges. The displayed path opens the collection folder. **Audit files** reports missing, changed, or orphaned artifacts without deleting them.

Optional C2PA signing creates separate `signed/` copies; the ordinary `images/` files remain exact approved bytes. Use an owner-supplied certificate chain and matching private key in ignored private storage. Decide the issuer, trust policy, and key custody before public use; a test certificate may verify locally but is not a publicly trusted identity. After starting the app once and approving the images, run from a fresh PowerShell shell at the repository root:

```powershell
New-Item -ItemType Directory -Force -Path 'data/catalog','data/exports','data/evidence/signing' | Out-Null
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf) -or -not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Run the launcher and prepare the catalog first.' }
if (-not (Test-Path -LiteralPath 'data/evidence/signing/cert.pem' -PathType Leaf) -or -not (Test-Path -LiteralPath 'data/evidence/signing/key.pem' -PathType Leaf)) { throw 'Owner signing credentials are missing.' }
& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python interpreter.' }
& .\.venv\Scripts\python.exe -m backend.review.export_cli preview
if ($LASTEXITCODE -ne 0) { throw 'Export preview failed.' }
```

Inspect the preview and the approved versions. Only when you authorize that collection, run:

```powershell
& .\.venv\Scripts\python.exe -m backend.review.export_cli export --authorized --c2pa-cert data/evidence/signing/cert.pem --c2pa-key data/evidence/signing/key.pem
if ($LASTEXITCODE -ne 0) { throw 'Signed export failed.' }
& .\.venv\Scripts\python.exe -m backend.review.export_cli audit
```

On Linux, create those directories with `mkdir -p`, check that the catalog and both credential files exist, verify `.venv/bin/python` belongs to `.venv`, then run the same three `-m backend.review.export_cli` commands with `.venv/bin/python`. Inspect the signed files, manifest, signer and privacy before publication. The CLI never creates or commits credentials.

Inspect every public image and the manifest before copying a collection to a website. Approval is a human decision. Disclose generative scene changes, including removed people, where documentary accuracy matters.

## Backups, checks, and troubleshooting

### Restart the catalog

To rebuild the database, thumbnails, edits, approvals, tags, and prompt history from the same `data/input/` originals, stop the server first. Archive the entire old catalog, including its SQLite WAL files and media, rather than deleting individual database files. Old exports also belong to the old catalog. From a fresh PowerShell shell at the repository root:

```powershell
if (-not (Test-Path -LiteralPath 'scripts/start.ps1' -PathType Leaf) -or -not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Run from the repository root with an existing catalog.' }
if (-not (Test-Path -LiteralPath 'data/input' -PathType Container)) { throw 'Input originals are missing.' }
$photos = @(Get-ChildItem -LiteralPath 'data/input' -File -Recurse | Where-Object { $_.Extension -match '^\.(jpe?g|png|tiff?|webp)$' })
if ($photos.Count -eq 0) { throw 'No supported input photos; keep the old catalog until originals are restored.' }
New-Item -ItemType Directory -Force -Path 'data/backups' | Out-Null
$stamp = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
Move-Item -LiteralPath 'data/catalog' -Destination (Join-Path 'data/backups' "catalog-$stamp")
if (Test-Path -LiteralPath 'data/exports' -PathType Container) { Move-Item -LiteralPath 'data/exports' -Destination (Join-Path 'data/backups' "exports-$stamp") }
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

On Linux, make the same input and catalog checks, create `data/backups/`, move `data/catalog/` and any `data/exports/` into uniquely named folders there, then run `bash scripts/start.sh`. Verify that the input contains all intended originals before moving the catalog, especially if you previously imported files from outside `data/input/` or used managed copies. A reset creates new photo IDs; old edits and review decisions remain only in the archived catalog.

The minimum recoverable set is data/input/, data/catalog/, and data/exports/, plus originals referenced elsewhere. Back up the ignored data/ tree to a separate private location. A SQLite snapshot does not include images:

    & .\.venv\Scripts\python.exe -m backend.review.export_cli backup --output data/backups/catalog-2026-11-01.sqlite

Use a new filename for every snapshot. Stop the server before manually copying the whole data/ tree. For read-only integrity checks:

    & .\.venv\Scripts\python.exe -m backend.catalog preflight --strict
    & .\.venv\Scripts\python.exe -m backend.review.export_cli audit
    & .\.venv\Scripts\python.exe -m backend.review.export_cli preview

If originals moved, use the catalog's hash-checked relink command; do not edit SQLite paths by hand. If the page is blank after an update, rerun the launcher to refresh frontend/dist/. If the port is occupied, stop the old server or use `-Port 8001` on Windows / `--port 8001` on Linux. If Python or npm is missing, install the required versions and rerun. A provider failure never approves or overwrites an existing version.

Developer checks from the repository root, after setup:

    & .\.venv\Scripts\python.exe scripts/setup_env.py
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    npm --prefix frontend test
    npm --prefix frontend run build

On a fresh checkout, use python scripts/setup_env.py once to create .venv/ before invoking its interpreter. To prepare the local model for offline use:

    & .\.venv\Scripts\python.exe scripts/setup_env.py --prefetch-model

Python dependencies are pinned in requirements.lock, frontend dependencies in frontend/package-lock.json. CI recreates .venv/ from these specifications on Windows and Linux.

## Local Docker release evaluation

Use three verification levels: development in the Windows repository `.venv`, isolated local release evaluation in Docker Desktop's Linux backend, and the existing Windows/Ubuntu GitHub CI. Docker runs the same FastAPI application, production React frontend, locked dependencies, and automated tests. The owner still decides photographic quality and publication approval.

The PowerShell launcher clones a selected branch or commit into a fresh `data/exports/docker/run-.../workspace/`, builds Python 3.13 and Node.js 24 dependencies in the repository-local Linux `.venv`, builds the frontend, runs tests, and starts the authenticated app. It copies `data/input/` into that workspace once, checks each original and copy with SHA-256, and rejects directory links that could cause copying loops. The entire workspace is bind-mounted to the host throughout the run. It includes source, `.venv`, frontend dependencies and build, input photos, catalog and WAL, thumbnails, masters, masks, derivatives, versions, model cache, backups, evidence, and exports. Dependency layers are cached; changes to either lockfile trigger installation again. The active development checkout is not used as the evaluation workspace.

### Start and test on Windows

Start Docker Desktop in Linux-container mode. From a fresh PowerShell shell at the repository root, with Git installed:

```powershell
if (-not (Test-Path -LiteralPath 'scripts/docker/evaluate.ps1' -PathType Leaf)) { throw 'Run from the repository root.' }
New-Item -ItemType Directory -Force -Path 'data/input' | Out-Null
if ((docker info --format '{{.OSType}}') -ne 'linux') { throw 'Start Docker Desktop with its Linux backend.' }
& .\scripts\docker\evaluate.ps1
```

Place owner-selected photos in `data/input/` before starting; an empty input is also supported. The default revision is `dev/v2-05-ontology-prefill`, the current successor to V2-04. Use `-Revision <branch-or-SHA>` to evaluate another revision, `-Repository <URL-or-local-Git-path>` for another source, and `-Port 8001` if port 8000 is occupied. The selected revision must be fetchable from that repository. First build needs access to the Docker base images and pinned package sources; later builds reuse Docker layers.

The launcher runs backend `unittest`, frontend `vitest`, and the production frontend build inside the isolated workspace. It stops on failure, keeps the partial run, and writes logs and a failure report. It makes no paid API calls. When the authenticated health check passes, it prints a run ID, URL, username, and password. Open that URL in the Windows browser. The host port binds to `127.0.0.1`; do not forward it to the network. The app retains its Basic authentication, Host checks, and origin checks.

The private `config/openAI.env` is never committed, so a fresh Docker checkout does not contain it. After configuring that local file from `config/openAI.example.env`, copy it to an ignored Docker config path outside the evaluation archive and start a **new** run with the copied file:

```powershell
if (-not (Test-Path -LiteralPath 'scripts/docker/evaluate.ps1' -PathType Leaf)) { throw 'Run from the repository root.' }
if (-not (Test-Path -LiteralPath 'config/openAI.env' -PathType Leaf)) { throw 'Configure config/openAI.env first.' }
New-Item -ItemType Directory -Force -Path 'config/docker' | Out-Null
$dockerConfig = Join-Path (Resolve-Path 'config/docker').Path 'openAI.env'
Copy-Item -LiteralPath 'config/openAI.env' -Destination $dockerConfig -Force
if ((Get-FileHash -LiteralPath 'config/openAI.env' -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $dockerConfig -Algorithm SHA256).Hash) { throw 'Docker config copy failed checksum verification.' }
& .\scripts\docker\evaluate.ps1 -ProviderConfigFile $dockerConfig
```

Add `-Port 8001` if 8000 is occupied. The launcher mounts `config/docker/openAI.env` read-only as `/workspace/config/openAI.env` **inside the running container**. The credential bytes are not copied into the preserved `run-.../workspace/` or the evaluation report; Docker may leave a zero-byte mount-point file there after stopping. Keep the copied file at the same host path for `Resume`. The app reads it on startup; copying it does not authorize a paid operation. Every paid operation still needs current-run in-app authorization. The launcher's separate login-password file lives in ignored `data/exports/docker/.credentials/`, outside individual runs. Never share or commit either credential.

### Stop, inspect, and resume

Replace `<run-id>` with the printed directory name. Verify the run exists before acting:

```powershell
if (-not (Test-Path -LiteralPath 'scripts/docker/evaluate.ps1' -PathType Leaf)) { throw 'Run from the repository root.' }
$runId = '<run-id>'
if (-not (Test-Path -LiteralPath (Join-Path (Join-Path 'data/exports/docker' $runId) 'metadata.json') -PathType Leaf)) { throw 'Run ID not found.' }
& .\scripts\docker\evaluate.ps1 -Action Status -RunId $runId
& .\scripts\docker\evaluate.ps1 -Action Snapshot -RunId $runId
& .\scripts\docker\evaluate.ps1 -Action Resume -RunId $runId
```

`Snapshot` and `Stop` gracefully stop the server, retain its logs, check SQLite integrity and foreign keys, verify workspace and host-input hashes, and create a separate consistent SQLite backup under `test-results/`. The whole host-mounted workspace is the recoverable record; a database backup alone lacks its media. `Resume` restarts the same container and waits for authenticated health. Stop and snapshot again before copying the entire run directory to private backup storage. Do not delete individual catalog files or overwrite an earlier export. Cleanup of a stopped container, image, run directory, or credential file is manual and should use its explicit run ID after a separate backup.

Completed collections appear on Windows under `data/exports/docker/<run-id>/workspace/data/exports/<export-id>/`. The in-app “Open export folder” button cannot open Windows Explorer from inside Docker; browse this host path directly. Check images, dimensions, manifest, cost report, and privacy before publication.

### Test record and owner acceptance

The local evaluation on 5 November 2026 used `dev/v2-05-ontology-prefill` commit `02246c13a931d193778daf51ef460499b6bf3122` in run `run-20261105-131013-9ec7ff83`, on host port 8001. The private evidence is under `data/exports/docker/<run-id>/`: `evaluation-report.md`, `logs/`, and `test-results/`. Do not commit or share it; it contains private photos and catalog data.

| Check | Measured result |
| --- | --- |
| Docker Linux image, locked installation, frontend production build | PASS |
| Backend `unittest discover -s tests -v` | 102 passed |
| Frontend `npm --prefix frontend test` | 23 passed |
| Frontend `npm --prefix frontend run build` | PASS |
| Authenticated health and production UI | PASS on port 8001; anonymous UI request returned 401 |
| Import and restart | 20 photos imported; 20 remained after stop and resume |
| Input integrity | 20/20 copied inputs and 20/20 host originals matched SHA-256 |
| SQLite and complete workspace | `integrity_check=ok`, zero foreign-key violations; backup and full workspace retained |

For owner-controlled manual acceptance, use the browser workflow above and record each result in the private run report:

1. Import representative JPEG, PNG, TIFF, and WebP files; repeat the import, then check duplicate detection and unchanged source hashes. Use synthetic files in a disposable run to check missing or changed-source handling without altering owner originals.
2. Check architecture, landscape, people, day/night, and condition suggestions. Review subject, tag, description, and preset proposals; correct a field, accept and undo a suggestion, and confirm owner-entered values remain intact. Keep paid analysis off unless separately authorized.
3. Create a deterministic local correction, inspect the full-resolution master and pending website version, then test batch processing, failure recovery, rejection, approval, and replacement without losing earlier versions.
4. Export an explicitly approved collection. Confirm only current approved versions appear, export IDs are unique, images and dimensions are correct, and the manifest excludes precise GPS and source paths. Inspect the cost report and host-side export folder.
5. Snapshot, resume, confirm catalog and export state, snapshot again, and compare the report's SQLite integrity and original checksums. Retain the entire run directory and its supporting media.

The successful Docker run preceded the final failure-report and input-link guards. Those guards passed PowerShell parsing; an invalid-revision exercise produced a private failure report with `NOT_RUN` checks. The complete happy path was not rerun after those guards. During development, normal Git stderr initially stopped the PowerShell wrapper, a backslash expression failed parsing, `docker cp` could not create a Linux symlink on NTFS, and port 8000 was occupied. The wrapper now checks native exit codes, uses string replacement, materializes the workspace through a Linux bind mount, and checks the requested port before cloning. A later non-ASCII character in failure-report text also broke Windows PowerShell parsing and was replaced. Failed run directories remain ignored for inspection.

Owner browser visual review, photographic quality, recognition accuracy, representative local and batch edits, version approval and rejection, approved-only export and privacy, and 200-photo performance are **NOT RUN**. Paid calls, cloud uploads, and GitHub Actions for this branch are **NOT RUN**. The owner should inspect these workflows in the browser, record PASS / FAIL / NOT_RUN with evidence in the private run report or a separate review note, and decide branch acceptance before staging, committing, merging, or release. The `docs/TESTING_AND_ACCEPTANCE.md` referenced by the earlier task is absent from this branch; this README and the run report are the available testing baseline. Software tests do not establish visual correctness.

## Provider configuration

Generative editing is disabled until you supply a server-side key. Copy config/openAI.example.env to ignored config/openAI.env, enter your own key, select a supported model, and set PHOTO_EDIT_PLANNING_COST_USD to your per-image estimate. Restart the server. Never place credentials in frontend code, screenshots, an issue, or a commit. There is no provider-enforced cost cap. Every paid run still needs an in-app preview, sufficient planning budget, and current-run authorization. Local recognition needs no paid key.

For an isolated Docker run, use the copy-and-mount command in [Local Docker release evaluation](#local-docker-release-evaluation); a fresh checkout does not inherit the local config file.

## Current branch review: ontology prefill

The `dev/v2-05-ontology-prefill` implementation is awaiting owner acceptance. Synthetic checks previously passed: 102 backend tests, 23 frontend tests, and the production build. A read-only pilot on 20 private photos proposed subjects for 12, content tags for 12, and conditions for 8; mean local inference time was about three seconds per photo. Those counts measure coverage, not label accuracy. Owner photo-by-photo accuracy, precision/recall, preset agreement, browser layout and workflow, correction clicks/time, Linux execution, and a 200-photo run remain **not run**. No paid API call, photo edit, or export was part of that pilot.

To reproduce the private pilot after running the launcher, use a fresh PowerShell shell at the repository root:

```powershell
New-Item -ItemType Directory -Force -Path 'data/evidence' | Out-Null
if (-not (Test-Path -LiteralPath 'data/catalog/catalog.sqlite' -PathType Leaf) -or -not (Test-Path -LiteralPath 'data/models/clip-vit-base-patch32-d15189d7/onnx/model_quantized.onnx' -PathType Leaf)) { throw 'Catalog or verified local model cache is missing.' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Run the launcher first.' }
& .\.venv\Scripts\python.exe -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python interpreter.' }
& .\.venv\Scripts\python.exe scripts/evaluate_ontology_pilot.py
if ($LASTEXITCODE -ne 0) { throw 'Pilot evaluation failed.' }
```

On Linux, create `data/evidence/`, check those catalog/model files and `.venv/bin/python`, verify its `sys.prefix`, then run `.venv/bin/python scripts/evaluate_ontology_pilot.py`. Inspect the private `data/evidence/ontology-pilot.png` and `.json` against each photograph. Record correct and incorrect subjects, content/condition tags, draft presets, missing labels, clicks, and correction time. In the browser, test a provisional suggestion and prompt preview before acceptance, edit a proposed field, accept and undo separate suggestions, verify owner-entered values remain intact, and review a bounded multi-photo selection. Confirm that preview creates no prompt version and acceptance does not approve a prompt, edit, or image. The owner decides whether to accept this branch before staging, merging, or starting another phase.

Possible later work includes local inpainting, RAW/HEIC support, and packaging without a Python/Node toolchain. Each needs a separate feasibility and owner decision; local inpainting remains a generative edit with derivative input, consent, an immutable pending attempt, and visual approval.

## Security and privacy

This is a single-user workstation, not a public web service. The Windows launcher uses a new password per run and restricts accepted Host headers and cross-origin writes. HTTP is unencrypted, so someone observing the network could see credentials or photographs. Use a trusted private LAN; never forward the port to the internet or expose it through a public tunnel. The authenticated original-image viewer serves the original file, including any embedded EXIF. Exported website images strip metadata.

The repository ignores the catalog, original photos, model cache, generated edits, exports, backups, and real provider configuration. Inspect every staged file before publishing. The two README showcase pairs are intentionally public and contain no EXIF/GPS; no other private photo belongs in Git. See [SECURITY.md](SECURITY.md) for network and privacy limits.

## License, author, and project records

Code and documentation are © 2026 Fernando Peñaherrera under the [PolyForm Noncommercial License 1.0.0](LICENSE). Its terms permit noncommercial use, changes, and redistribution; commercial permission requires a separate agreement. The four README preview images are © 2026 Fernando Peñaherrera under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). See [NOTICE.md](NOTICE.md). Third-party packages and the optional local model retain their own licenses.

Contact: [Fernando Peñaherrera](mailto:fernandopenaherrera@gmail.com) · [GitHub](https://github.com/Fernando3161). For bug reports, include OS, Python and Node versions, reproduction steps, and redacted logs. Never attach photos, SQLite files, GPS, or keys.

The application schema is defined by the ordered migrations in `backend/catalog/migrations/`; the retained [data contract](docs/DATA_AND_ARTIFACTS.md) and [schema reference](docs/DATABASE_SCHEMA.md) explain its storage rules. Prior plans, decisions, reviews, and technical reports remain available in Git history; they are not needed to run the application.
