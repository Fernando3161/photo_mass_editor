# Photo Mass Editor

Local-first, human-reviewed photography catalog and controlled image-editing project.

**Current status:** Phases 00–02 were reviewed by the owner. Phase 03 analysis and prompt assembly changes are on `dev/v1-phase-03-prompts`, unstaged and uncommitted for owner review. Editing and export have not begun.

**Commit policy:** Development agents leave all changes unstaged and uncommitted. Automatic commits are forbidden. The owner reviews, stages, and commits changes manually.

## Development setup

Python 3.11 or newer and Node.js 22 or newer are required. The setup script creates or updates the repository-local `.venv`, installs the exact Python lock, verifies the interpreter and dependencies, installs the exact frontend lock with `npm ci`, and validates the npm tree.

```powershell
python scripts/setup_env.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
```

```bash
python scripts/setup_env.py
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
```

CI runs this sequence on Windows and Linux from a clean checkout. Direct Python requirements are in `requirements.in`; the complete exact environment is in `requirements.lock`. Frontend direct and transitive versions are fixed by `frontend/package-lock.json`. All project Python commands below must use the `.venv` interpreter.

## Catalog commands

Run from the repository root, substituting `.venv/bin/python` on Linux. All operational data goes under the ignored `data/` directory by default; the CLI creates its catalog directory on first use. `--data-dir` can select another private location.

```powershell
.\.venv\Scripts\python.exe -m backend.catalog init
.\.venv\Scripts\python.exe -m backend.catalog import-photo "C:\path\to\photo.jpg"
.\.venv\Scripts\python.exe -m backend.catalog import-folder "C:\path\to\selected-photos"
.\.venv\Scripts\python.exe -m backend.catalog list
.\.venv\Scripts\python.exe -m backend.catalog preflight
.\.venv\Scripts\python.exe -m backend.catalog relink PHOTO_ID "C:\new\path\to\photo.jpg"
```

The default `reference` mode reads an original in place without copying it. Pass `--mode copy` to an import command to explicitly create a managed copy under `data/originals/`. Imports calculate SHA-256, save original path and EXIF/GPS metadata in SQLite, and create an orientation-corrected PNG thumbnail. The read-only `list` command reports `gps_status`; invalid GPS direction fields leave coordinates empty rather than guessing a location. `city` and `country` are editorial fields and are not filled by Phase 01 ingestion. Supported image formats are JPEG, PNG, TIFF, and WebP. Folder import reports sidecars and known unsupported RAW/HEIC formats without processing them. The preflight command reports missing or changed source, managed, and thumbnail files. A moved source may be relinked to its stable photo ID only when its hash matches.

No original file is modified by catalog commands. The database, thumbnails, and managed copies are private and ignored by Git. Back up `data/catalog.sqlite` and any managed originals separately; referenced source files remain in their original location. To finish the Phase 01 owner-photo check, follow the [step-by-step review guide](docs/PHASE_01_REVIEW.md); its Windows and Linux commands create the required ignored review folders before importing the sample.

## Local review workstation

Build the frontend, then start the local service against a catalog directory:

```powershell
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m backend.review --data-dir data\phase02-review\catalog --host 127.0.0.1 --port 8000
```

```bash
npm --prefix frontend run build
.venv/bin/python -m backend.review --data-dir data/phase02-review/catalog --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The workstation provides a top virtualized filmstrip, contact sheet, original/empty-edited comparison, filters, keyboard navigation, metadata/tags, editable draft presets, visible autosave status, and local failed-save recovery. It does not analyze, edit, upload, or publish images. Precise GPS and internal filesystem paths are not returned in photo details.

Phase 03 adds explicitly authorized analysis orchestration and versioned prompt assembly. No production provider is configured by default, so analysis fails closed without a network call until the owner selects and configures an adapter. Editable suggestions, owner instructions, constraints, deterministic conflict checks, prompt versions, and prompt approval work locally. Prompt approval does not run an edit.

For review procedures, follow the [Phase 02 owner review guide](docs/PHASE_02_REVIEW.md) and [Phase 03 owner review guide](docs/PHASE_03_REVIEW.md).

## Project contracts

Read [agent instructions](AGENTS.md), [objectives](docs/PROJECT_OBJECTIVES.md), [phase plan](docs/PROJECT_PLAN.md), [workflow](docs/DEVELOPMENT_WORKFLOW.md), [data policy](docs/DATA_AND_ARTIFACTS.md), [logical schema](docs/DATABASE_SCHEMA.md), and the [Phase 03 report](reports/PHASE_03_TECHNICAL_REPORT.md) before extending the implementation. Phase transitions, merges, and releases remain owner review gates.
