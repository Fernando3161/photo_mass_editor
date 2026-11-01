# First two-image trial: two OpenAI API edits

This is a small owner-run Phase 04 trial. It makes **two output images from two chosen photos, both through the OpenAI image-edit API**. Photo A requests photographic retouching with **0/10 AI reimagining**. Photo B is **photo 15, Budapest Opera**, requesting a modest frontal perspective correction and removal of visible people with **2/10 AI reimagining**. Each is a separate paid, owner-authorized run. Asking for a completely new viewpoint may invent unseen details.

**What this test can prove:** the paid edit path can process a prompt-directed, tightly constrained retouch and a separately instructed perspective edit; the source photos stay unchanged; and both output versions wait for your review. It cannot prove that an AI image is authentic or that prompt-directed edits stay within specific regions. Do not publish either image merely because its job succeeds. Approved-only export is Phase 05.

## What 0/10 means here

| Trial | Current Phase 04 behavior |
| --- | --- |
| Photo A, 0/10 | Choose **Generative image edit**. Send the publication-sized derivative and a prompt allowing only tonal/color/contrast retouching of existing content. No PNG mask is needed. No scene invention is requested. This is a paid OpenAI call. |
| Photo B, 2/10 | Choose **Generative image edit** again for photo 15, Budapest Opera, with a separately approved prompt requesting a modest frontal perspective correction and removal of visible people. This is a second paid OpenAI call. |

The 0–10 value describes **allowed reimagining in your app**, not whether the API is used and not an OpenAI fidelity setting. The OpenAI endpoint is generative for **both** edits. With no uploaded mask, the model interprets the prompt and decides which regions to change; the API does not return or automatically create a separate editable mask in this workflow. A 0/10 request cannot guarantee no invented detail or unchanged pixels. You decide whether its output satisfies the 0/10 intent after comparing it with the original. A very dark sky on an already dark photo is easier to judge as tonal retouching than turning a daytime scene into night.

If you have already compiled and approved the prompt for **photo 14 (Budapest Parliament)**, keep that prompt and continue at **step 3: Fund and configure**. Do not recompile or approve it just to follow this guide. Before sending the request, inspect its approved text and confirm that it says 0 of 10 and asks for the intended photographic changes without scene invention. If it asks for a literal uploaded mask, revise and reapprove the prompt before the paid run.

## 1. Prepare the two photos and the local environment (no API credit needed)

Run commands from the repository root. Keep all private images, catalog files, and evidence under the ignored `data/` directory. Do not put your API key in a source file, browser form, screenshot, or report.

**Windows PowerShell** (a fresh terminal):

```powershell
New-Item -ItemType Directory -Force -Path 'data/phase04-review/input', 'data/phase04-review/catalog', 'data/phase04-review/backups', 'data/phase04-review/evidence' | Out-Null
if (-not (Test-Path -LiteralPath 'requirements.lock' -PathType Leaf)) { throw 'Run this from the repository root.' }
python scripts/setup_env.py
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe' -PathType Leaf)) { throw 'Repository .venv is missing.' }
```

**Linux shell** (a fresh terminal):

```bash
mkdir -p data/phase04-review/input data/phase04-review/catalog data/phase04-review/backups data/phase04-review/evidence
test -f requirements.lock || { echo 'Run this from the repository root.' >&2; exit 1; }
python3 scripts/setup_env.py
test -f .venv/bin/python || { echo 'Repository .venv is missing.' >&2; exit 1; }
```

The setup script creates or updates the repository's only Python environment, installs locked dependencies, and verifies the interpreter. It also requires Node.js 22+ and npm. If it fails, resolve that failure before continuing; do not run project commands with system Python.

Place the two chosen photos under `data/phase04-review/input/` with your file manager, unless those exact files are already there from the Phase 04 local review. They may already be visible in the catalog; the import command below can be rerun. Use photos you own and are comfortable sending **both** to OpenAI. Avoid sensitive people, locations, or text. The app's default import **references** those copies and never changes them. This guide's hash check covers the files in that input folder.

Before importing or starting the server, back up an existing catalog. The following blocks also verify the inputs and record the current source hashes. If you already have more photos in this input folder, they are included in the hash record; you will still select only two in the UI.

**PowerShell:**

```powershell
$files = @(Get-ChildItem -LiteralPath 'data/phase04-review/input' -File -Recurse)
if ($files.Count -eq 0) { throw 'Put at least the two trial photos in data/phase04-review/input first.' }
$files | Sort-Object FullName | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash)  $($_.Path)" } | Set-Content 'data/phase04-review/evidence/first-trial-before.sha256.txt'
@'
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
source = Path('data/phase04-review/catalog/catalog.sqlite')
backup_dir = Path('data/phase04-review/backups')
backup_dir.mkdir(parents=True, exist_ok=True)
if source.is_file():
    target = backup_dir / f'catalog-before-first-trial-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite'
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    with sqlite3.connect(target) as check:
        assert check.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    print(f'Verified backup: {target}')
else:
    print('Fresh catalog: no prior database to back up')
'@ | .\.venv\Scripts\python.exe -
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog import-folder data/phase04-review/input
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog preflight
npm --prefix frontend run build
```

**Linux:**

```bash
find data/phase04-review/input -type f -print -quit | grep -q . || { echo 'Put at least the two trial photos in data/phase04-review/input first.' >&2; exit 1; }
find data/phase04-review/input -type f -print0 | sort -z | xargs -0 sha256sum > data/phase04-review/evidence/first-trial-before.sha256.txt
.venv/bin/python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
source = Path('data/phase04-review/catalog/catalog.sqlite')
backup_dir = Path('data/phase04-review/backups')
backup_dir.mkdir(parents=True, exist_ok=True)
if source.is_file():
    target = backup_dir / f'catalog-before-first-trial-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite'
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    with sqlite3.connect(target) as check:
        assert check.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    print(f'Verified backup: {target}')
else:
    print('Fresh catalog: no prior database to back up')
PY
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog import-folder data/phase04-review/input
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog preflight
npm --prefix frontend run build
```

Read the `preflight` output. Stop if either source is missing or changed. Import may report existing/duplicate photos when you rerun it; select the correct catalog entry by thumbnail in the UI.

## 2. Prepare photo A's prompt without sending a request

Stop any older server on port 8000. In a **new terminal**, from the repository root, start the workstation using the catalog above. A key is not needed to prepare a prompt:

```powershell
if (-not (Test-Path -LiteralPath 'data/phase04-review/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Trial catalog is missing.' }
.\.venv\Scripts\python.exe -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

On Linux, use `.venv/bin/python` in the last line and `test -f data/phase04-review/catalog/catalog.sqlite` for the check. Leave this terminal running. Open <http://127.0.0.1:8000> in your browser.

1. Select **photo A** in the filmstrip or contact sheet. In **Editing draft**, choose `website-standard-v1`, **No preset**, and **AI reimagining allowance: 0**. Leave **I explicitly allow semantic changes for this draft** unchecked. Do not click **Run analysis for current photo**; it is a separate paid action and is unnecessary here.
2. Leave **AI suggested corrections** empty. In **My additional instructions**, enter: `Use the existing photograph only. Darken the existing sky to near black through tonal and color adjustment; increase contrast and clarity on the existing architecture; adjust exposure and color as conventional photographic retouching. Keep all structures, windows, signs, people, and objects in their original positions. Do not invent, remove, reshape, or replace scene elements.` In **Approved constraints**, enter: `Preserve the building geometry, composition, and aspect ratio. Do not create new clouds, stars, lights, architecture, or background content. If a requested adjustment cannot be made without changing scene content, make a smaller adjustment.` This is an instruction to the API, not an enforced pixel-level guarantee.
3. Wait for the visible save status; click **Compile prompt preview**. Read the entire result. Confirm it says **0 of 10** and prohibits semantic changes. If you edit the compiled text, click **Save as new version**. Click **Approve current prompt**. Prompt approval does **not** start a request.
4. In **Editing and versions**, choose **Generative image edit** and **Current photo**. Open the **1600px publication input** link. Inspect that it is photo A, a separate JPEG with the intended aspect ratio and a longest edge of at most 1600 pixels. For this provider, the shorter edge must be at least 512 pixels and the aspect ratio between 1:3 and 3:1. The API will receive this derivative, never the original shown on the left. Leave **Optional transparent PNG mask** empty.

Stop this no-key server with `Ctrl+C` before the paid setup in step 3. The approved prompt remains in the local catalog.

## 3. Fund and configure the OpenAI API before either output

You can stop here and return when your API account is ready. ChatGPT billing and API billing are separate. In your [OpenAI Platform API billing overview](https://platform.openai.com/settings/organization/billing/overview), select the intended API organization, add a payment method, and purchase credits. OpenAI's [prepaid billing instructions](https://help.openai.com/en/articles/8264644-setting-up-and-managing-prepaid-api-billing) say the initial purchase minimum is $5 and auto-reload may be on during setup; inspect that option before confirming. Wait until the credit balance appears. A positive balance does not guarantee model access or a successful request. Check account usage and any project/organization spend controls as well. [API and ChatGPT billing are separate](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform). Plan for **two** separately billed edits.

Create an **API project key** in the Platform for the project you intend to bill. Keep it secret. The server automatically reads `config/openAI.env` when it starts; it never sends the key to the browser. The key tracking ID is not used by this app. Your old root-level `openAI.env` is not loaded: copy its secret value into the new `config/openAI.env` once. OpenAI may require organization verification or model access for image editing; see the [image generation guide](https://developers.openai.com/api/docs/guides/image-generation).

For this app, the server uses `gpt-image-2.5-sunburst` by default and requests **medium** quality PNG. The code supports `gpt-image-2.5-flare` if you deliberately set that model. Check current model availability, the [image edit API reference](https://developers.openai.com/api/reference/python/resources/images/methods/edit), and the [image generation cost calculator](https://developers.openai.com/api/docs/guides/image-generation) immediately before the live trial. Set a **conservative positive per-image planning amount in USD** in the private file; the amount is your estimate and the UI budget gate **for each single-photo run**, not a provider spending cap. Actual billed cost can differ, and the app's receipt does not show an invoice amount.

From the repository root, copy the commit-safe template **once** and fill in `OPENAI_API_KEY` and `PHOTO_EDIT_PLANNING_COST_USD` in the private copy. Keep the `NAME="value"` format; replace only the example values. `OPENAI_API_KEY` must contain the **secret key**, not its tracking ID. If `config/openAI.env` already exists, edit it instead of overwriting it. Both the root-level and config-level `openAI.env` files are ignored by Git, but only the config-level file is loaded at server startup.

**PowerShell:**

```powershell
if (-not (Test-Path -LiteralPath 'config/openAI.env' -PathType Leaf)) { Copy-Item -LiteralPath 'config/openAI.example.env' -Destination 'config/openAI.env' }
# Edit config/openAI.env in your IDE, then start the server:
if (-not (Test-Path -LiteralPath 'data/phase04-review/catalog/catalog.sqlite' -PathType Leaf)) { throw 'Trial catalog is missing.' }
.\.venv\Scripts\python.exe -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

**Linux:**

```bash
test -f config/openAI.env || cp config/openAI.example.env config/openAI.env
# Edit config/openAI.env in your editor, then start the server:
test -f data/phase04-review/catalog/catalog.sqlite || { echo 'Trial catalog is missing.' >&2; exit 1; }
.venv/bin/python -m backend.review --data-dir data/phase04-review/catalog --host 127.0.0.1 --port 8000
```

On startup the server prints `Loaded private server configuration from config/openAI.env` without printing the key. If the file still contains example values, startup stops with a field-specific error. Later restarts need only the final `backend.review` command. A process environment variable with the same name takes precedence over the private file.

Keep that terminal open and return to <http://127.0.0.1:8000>. Do not use **Run analysis for current photo** for this trial; it is a separate opt-in action and is unnecessary to compile your own prompt.

## 4. Make output 1: prompt-directed OpenAI retouch at 0/10

1. Return to **photo A (photo 14, Budapest Parliament, if that is your selected first image)** and confirm its approved prompt still says **0 of 10**. Select **Generative image edit** and **Current photo**. Leave **Optional transparent PNG mask** empty. There should be no **Mask selected** ID. This sends the image and approved prompt to OpenAI without a mask file.
2. Click **Preview selected run (1)**. Expand **Per-photo eligibility and prompts**. Confirm exactly one eligible **photo A**, the approved 0/10 prompt with the intended sky/architecture retouching and no requested scene invention, `ready`, the intended model, and the estimated amount. Confirm **First 20 visible photos** is not selected and the identical-retry override is unchecked. The prompt guides regional editing; no exact region boundary is supplied.
3. Enter **Run budget in USD** at or above the displayed one-photo estimate. Check the Platform balance, photo content, publication input, prompt, selection count, model, and budget. The budget is an application estimate gate, not an account spending cap.
4. Check **I authorize this current paid run**, then click **Start authorized run** **once**. This queues the first billable API request. Wait for a terminal job receipt. A running provider call cannot be reliably cancelled. If it fails, inspect the receipt and Platform usage before retrying; a failed or interrupted call may still have been billed.
5. On success, select the new **PENDING** version. Compare it with the original and inspect a downloaded JPEG at full size. Check sky boundaries, façade edges, windows, signs, people, colors, and any altered objects. Decide **Approve selected** or **Reject selected** yourself. A 0/10 prompt without a mask does not guarantee the result is free of reimagining or confined to the requested regions. Record the actual API usage/cost shown in Platform before moving to photo B.

## 5. Make output 2: Budapest Opera perspective and people removal at 2/10

1. Select **photo 15, Budapest Opera**. Confirm the original image shows the intended opera building before editing. In **Editing draft**, choose `website-standard-v1`, **No preset**, and **AI reimagining allowance: 2**. Check **I explicitly allow semantic changes for this draft**, because both removing people and correcting perspective may reconstruct scene details. This checkbox does not itself start a paid request.
2. Clear **AI suggested corrections** if it contains text. In **My additional instructions**, enter: `Make the Budapest Opera building appear slightly more frontal by correcting the camera perspective. Keep the correction modest and photorealistic. Remove the visible people from the scene, including those in front of the building and at its entrance, and plausibly repair only the areas they obscured. Preserve the building's recognizable architecture, openings, materials, signs, ornament, surroundings, time of day, and general lighting. Do not add or remove any other scene elements.` In **Approved constraints**, enter: `Maintain the opera building's identity and architectural fidelity. Avoid fabricating unseen architectural features. If a more frontal view requires substantial reconstruction, make a smaller perspective correction. Keep the original aspect ratio and avoid cropping away important scene content. Remove people cleanly, without ghost figures, repeated textures, or visibly invented architectural details.` If the photo has no people in one of the named areas, the instruction simply applies to the people actually visible.
3. Wait for save status; click **Compile prompt preview**. Read every line. The final prompt should say **2 of 10** and explicitly include both the frontal perspective correction and people removal. Check that no older instruction says to retain people or forbids removing objects. Edit the compiled text if needed, click **Save as new version**, and then **Approve current prompt**. If a later draft change makes it stale, compile and approve a fresh version.
4. Select **Generative image edit** and **Current photo**. Open the **1600px publication input** link and inspect that separate JPEG before sending anything. It should be the intended photo, at most 1600 pixels on its longest edge, with the same aspect ratio. For this provider, its shorter edge must be at least 512 pixels and its aspect ratio must lie between 1:3 and 3:1. The API receives this derivative, not the original displayed in the comparison pane. Do not upload a mask for this first perspective test: the change affects building geometry beyond a small recolor area.
5. Click **Preview selected run (1)**. Expand **Per-photo eligibility and prompts**. Confirm exactly one eligible **photo 15, Budapest Opera**, the intended prompt version and full text, `ready`, `gpt-image-2.5-sunburst`, and the estimated amount. Confirm that **First 20 visible photos** is **not** selected and **Explicitly retry an identical rejected attempt** is unchecked.
6. Enter a **Run budget in USD** at or above the displayed estimate. This is only an application estimate gate, not the charge. Record your Platform API credit balance before the run. Before the final click, check the photo content, publication input, prompt, selection count, model, and budget once more.
7. Check **I authorize this current paid run** and click **Start authorized run** **once**. This click queues the **second** billable API edit. Do not refresh, restart, or retry while the job is `queued` or `running`. A running provider call cannot be reliably cancelled.

If the preview says the provider is unavailable, stop and check that the key and positive planning amount were set in the **same terminal that launched this server**. If the job fails, inspect the receipt and Platform usage **before** any retry; an interrupted request may already have been billed. A provider output with the wrong aspect ratio can fail normalization after a charged request.

## 6. Review the two results and close the trial

1. For photo B, wait for a `succeeded` or `failed` job receipt. A success creates a separate **PENDING** version. Select it, compare the original and edited image, download the JPEG, and inspect the opera façade, edges, windows, doors, signs, ornament, shadows, sky, and corrected perspective at full size. Check every area where a person was removed for ghosts, duplicated texture, or invented building detail. Reject it with a reason if details were invented or the result is misleading. Approve only if you personally accept it.
2. Check the Platform API usage/billing view for **both** charges. The app records provider usage when returned, but its `actual_cost_usd` can remain empty. Record both job outcomes and approximate billed amounts privately; do not include the key. For photo 15, note the balance before and after and the job's token usage; the balance difference is only an approximate per-job cost if no other API calls occurred meanwhile.
3. Stop the server with `Ctrl+C`. In a fresh terminal, compare source hashes and run catalog preflight again:

**PowerShell:**

```powershell
if (-not (Test-Path -LiteralPath 'data/phase04-review/evidence/first-trial-before.sha256.txt' -PathType Leaf)) { throw 'Missing before-hash evidence.' }
$files = @(Get-ChildItem -LiteralPath 'data/phase04-review/input' -File -Recurse)
if ($files.Count -eq 0) { throw 'Trial input photos are missing.' }
$files | Sort-Object FullName | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash)  $($_.Path)" } | Set-Content 'data/phase04-review/evidence/first-trial-after.sha256.txt'
if (Compare-Object (Get-Content 'data/phase04-review/evidence/first-trial-before.sha256.txt') (Get-Content 'data/phase04-review/evidence/first-trial-after.sha256.txt')) { throw 'Source hashes changed; stop and investigate.' }
.\.venv\Scripts\python.exe -m backend.catalog --data-dir data/phase04-review/catalog preflight
git status --short
```

**Linux:**

```bash
test -f data/phase04-review/evidence/first-trial-before.sha256.txt || { echo 'Missing before-hash evidence.' >&2; exit 1; }
find data/phase04-review/input -type f -print -quit | grep -q . || { echo 'Trial input photos are missing.' >&2; exit 1; }
find data/phase04-review/input -type f -print0 | sort -z | xargs -0 sha256sum > data/phase04-review/evidence/first-trial-after.sha256.txt
cmp data/phase04-review/evidence/first-trial-before.sha256.txt data/phase04-review/evidence/first-trial-after.sha256.txt
.venv/bin/python -m backend.catalog --data-dir data/phase04-review/catalog preflight
git status --short
```

The catalog should contain distinct files under `publication-inputs/`, `edited/raw/`, and `edited/versions/`. The original hash comparison must pass. The private `data/` tree and API key must not appear as staged or tracked files. Keep both version decisions and job receipts in the catalog for the Phase 04 owner review.

## Trial record (fill in privately)

| Item | Photo A: OpenAI 0/10 | Photo B: Budapest Opera 2/10 |
| --- | --- | --- |
| Photo/catalog ID | 20261021_211524.jpg |20261023_121858.jpg  |
| Approved prompt version | v2 | v3 |
| Input and output image dimensions |1600x1200  |1600x1200  |
| Job status and version ID | 4c836e54 · generative · succeeded | 9917d722 · generative · succeeded |
| Review decision and reason | approved |  approved |
| Platform credit balance before and after |5/4.97  |4.97/4.95  |
| Actual API cost seen in Platform | 0.03 | 0.,2 |
| Source hashes unchanged; preflight clean |yes  | yes |

Both attempts remain separate immutable versions. Approval is your decision after visual comparison, independent of API success.
