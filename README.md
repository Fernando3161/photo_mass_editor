# Photo Mass Editor

A local photography catalog, review workstation, and controlled editing pipeline. Originals stay unchanged. Every edit is a separate version; only an image you explicitly approve can enter a website collection.

Current release: **V1.0.0**. See [release notes and known limits](docs/V1_RELEASE_NOTES.md).

| Original photo | Owner-approved generative edit |
| :---: | :---: |
| ![Original Budapest Opera House photograph](docs/assets/opera-house-before.jpg) | ![Edited Budapest Opera House photograph](docs/assets/opera-house-after.jpg) |

These small, metadata-free previews come from the owner's photo 15 trial. The edit adjusts perspective and removes people; it is a generated interpretation, not documentary evidence of an empty scene. Full-size photographs are not in this repository.

## Quick start on Windows

Install [Python 3.11+](https://www.python.org/downloads/) and [Node.js 22+](https://nodejs.org/) so that Python and npm are on PATH. Open PowerShell in the cloned repository and run:

    powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1

This one script creates the ignored data folders and repository-local Python environment, installs pinned Python and Node dependencies, imports supported photos in data/input, builds the website, opens the browser, and starts the server. Leave the terminal open; press Ctrl+C to stop. Rerun it after adding photos or updating the repository.

The terminal prints a one-run username and password, a local URL, and LAN URLs. Enter those credentials in the browser prompt. Other devices on the same trusted private network can use a LAN URL. If Windows Firewall asks, allow Python only on **private** networks when LAN access is needed. The launcher uses plain HTTP; see [Security and privacy](#security-and-privacy).

To change the port or keep the browser closed:

    powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1 -Port 8001 -NoBrowser

No provider key is required for cataloging, local recognition, deterministic corrections, or export.

### Where to copy original photos

Copy selected originals directly into data/input/ before starting, or add more later and rerun the launcher. It creates data/input/ if absent. JPEG, PNG, TIFF, and WebP are supported. RAW and HEIC are reported as unsupported. Keep an independent private backup of the originals.

Import defaults to **reference** mode: the app records each original's path and SHA-256 and reads it without changing its bytes. Leave the files in data/input/ after import. The catalog, thumbnails, attempts, exports, model, and backups live in ignored data/ folders. Do not put data/ on public hosting.

To import originals from another location after setup, run from the repository root:

    & .\.venv\Scripts\python.exe -m backend.catalog import-folder "<YOUR_PHOTO_FOLDER>"

Those originals remain in that external folder. The launcher automatically imports only data/input/. Repeat imports are safe; existing photos are reported.

### Linux setup

The one-file launcher is for Windows PowerShell. Linux uses the same locked specifications from the repository root:

    mkdir -p data/input data/catalog data/exports data/backups data/evidence data/models
    python3 scripts/setup_env.py
    .venv/bin/python -m backend.catalog init
    test -f data/catalog/catalog.sqlite
    npm --prefix frontend run build
    .venv/bin/python -m backend.review --data-dir data/catalog --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000/. Before starting the server, import Linux photos placed in data/input with:

    .venv/bin/python -m backend.catalog import-folder data/input

The Linux command binds to the current computer. Network binding requires an access password and explicit host configuration; the supported LAN flow is scripts/start.ps1 on Windows.

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

### 4. Compile and approve an editing prompt

Open **Analysis and final prompt**. Paid analysis is optional and the default analysis provider is unavailable. You can write your own instructions without it. Click **Compile prompt preview**, read the full text and any conflict warning, edit if needed, then **Save as new version**. Click **Approve current prompt** on the version you want. Saving photo metadata or draft changes makes approval stale; compile and approve again.

### 5. Create and review an edit

Open **Editing and versions**. Choose **Local deterministic correction** for exposure, contrast, color, sharpness, or denoise. Choose **Generative image edit** only for a deliberate provider operation. Start with **Current photo**; a bounded first-20-visible batch is available after a small trial. The generative input is a validated publication-sized derivative, never the original. An optional transparent PNG mask must match it; a mask cannot guarantee protected pixels stay unchanged.

Click **Preview selected run** and inspect eligibility, prompt version, settings, and estimate. For a generative run, enter a planning budget at least as large as the estimate. This is an app gate, not a provider spending cap. Check **I authorize this current ... run**, then **Start authorized run**. Every attempt has a receipt and immutable version. Success creates a **PENDING** version, never automatic approval.

Select the version and compare it with the original, including edges, faces, text, geometry, and reconstructed areas. Click **Approve selected** only after visual review, or **Reject selected** and revise the instructions. Rejected versions remain in history. Default batches skip approved photos and avoid identical rejected attempts without the explicit retry override.

### 6. Export approved photos

Open **Website collection**. Click **Preview approved collection**; check the count and location status. Check export authorization, then **Export approved collection**. A new folder appears under data/exports/. Its images/ JPEGs are byte-for-byte copies of approved website versions. thumbnails/ has separate small images; manifest.json contains privacy-filtered editorial metadata; cost_report.json separates estimates from known and unknown actual costs. The displayed path opens the collection folder. **Audit files** reports missing, changed, or orphaned artifacts without deleting them.

Inspect every public image and the manifest before copying a collection to a website. Approval is a human decision. Disclose generative scene changes, including removed people, where documentary accuracy matters.

## Backups, checks, and troubleshooting

The minimum recoverable set is data/input/, data/catalog/, and data/exports/, plus originals referenced elsewhere. Back up the ignored data/ tree to a separate private location. A SQLite snapshot does not include images:

    & .\.venv\Scripts\python.exe -m backend.review.export_cli backup --output data/backups/catalog-2026-11-01.sqlite

Use a new filename for every snapshot. Stop the server before manually copying the whole data/ tree. For read-only integrity checks:

    & .\.venv\Scripts\python.exe -m backend.catalog preflight
    & .\.venv\Scripts\python.exe -m backend.review.export_cli audit
    & .\.venv\Scripts\python.exe -m backend.review.export_cli preview

If originals moved, use the catalog's hash-checked relink command; do not edit SQLite paths by hand. If the page is blank after an update, rerun scripts/start.ps1 to rebuild frontend/dist/. If the port is occupied, stop the old server or use -Port 8001. If Python or npm is missing, install the required versions and rerun. A provider failure never approves or overwrites an existing version.

Developer checks from the repository root, after setup:

    & .\.venv\Scripts\python.exe scripts/setup_env.py
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    npm --prefix frontend test
    npm --prefix frontend run build

On a fresh checkout, use python scripts/setup_env.py once to create .venv/ before invoking its interpreter. To prepare the local model for offline use:

    & .\.venv\Scripts\python.exe scripts/setup_env.py --prefetch-model

Python dependencies are pinned in requirements.lock, frontend dependencies in frontend/package-lock.json. CI recreates .venv/ from these specifications on Windows and Linux.

## Provider configuration

Generative editing is disabled until you supply a server-side key. Copy config/openAI.example.env to ignored config/openAI.env, enter your own key, select a supported model, and set PHOTO_EDIT_PLANNING_COST_USD to your per-image estimate. Restart the server. Never place credentials in frontend code, screenshots, an issue, or a commit. There is no provider-enforced cost cap. Every paid run still needs an in-app preview, sufficient planning budget, and current-run authorization. Local recognition needs no paid key.

## Security and privacy

This is a single-user workstation, not a public web service. The Windows launcher uses a new password per run and restricts accepted Host headers and cross-origin writes. HTTP is unencrypted, so someone observing the network could see credentials or photographs. Use a trusted private LAN; never forward the port to the internet or expose it through a public tunnel. The authenticated original-image viewer serves the original file, including any embedded EXIF. Exported website images strip metadata.

The repository ignores the catalog, original photos, model cache, generated edits, exports, backups, and real provider configuration. Inspect every staged file before publishing. See the [release audit](reports/RELEASE_AUDIT.md) for findings and limits. The two README examples are intentionally public and contain no EXIF/GPS; no other private photo belongs in Git.

## License, author, and project records

Code and documentation are © 2026 Fernando Peñaherrera under the [PolyForm Noncommercial License 1.0.0](LICENSE). Its terms permit noncommercial use, changes, and redistribution; commercial permission requires a separate agreement. The two README photos are © 2026 Fernando Peñaherrera under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). See [NOTICE.md](NOTICE.md). Third-party packages and the optional local model retain their own licenses.

Contact: [Fernando Peñaherrera](mailto:fernandopenaherrera@gmail.com) · [GitHub](https://github.com/Fernando3161). For bug reports, include OS, Python and Node versions, reproduction steps, and redacted logs. Never attach photos, SQLite files, GPS, or keys.

The [objectives](docs/PROJECT_OBJECTIVES.md), [architecture](docs/REPOSITORY_ARCHITECTURE.md), [data policy](docs/DATA_AND_ARTIFACTS.md), [editing policy](docs/IMAGE_EDITING_POLICY.md), and [testing protocol](docs/TESTING_AND_ACCEPTANCE.md) document the design. Historical phase reports remain in reports/ for provenance.
