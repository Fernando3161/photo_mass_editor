# Photo Mass Editor

Local-first, human-reviewed photography catalog and controlled image-editing project.

**Current status:** Phase 00 was reviewed by the owner. Phase 01 catalog ingestion is implemented on `dev/v1-phase-01-catalog` for owner review. The review UI, AI analysis, editing, and export phases have not begun. `main` remains unchanged.

## Phase 01 setup

Python 3.11 or newer is required. The same setup script creates or updates the repository-local `.venv` on Windows PowerShell and Linux. It installs `requirements.lock`, checks installed versions and dependencies, and prints the selected interpreter.

```powershell
python scripts/setup_env.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```bash
python scripts/setup_env.py
.venv/bin/python -m unittest discover -s tests -v
```

CI runs this setup and test sequence on Windows and Linux from a clean checkout. Pillow is the only Phase 01 runtime dependency and has no required transitive Python packages. The lock file pins its version. All project commands below must use the `.venv` interpreter.

## Catalog commands

Run from the repository root, substituting `.venv/bin/python` on Linux. All operational data goes under the ignored `data/` directory by default. `--data-dir` can select another private location.

```powershell
.venv\Scripts\python.exe -m backend.catalog init
.venv\Scripts\python.exe -m backend.catalog import-photo "C:\path\to\photo.jpg"
.venv\Scripts\python.exe -m backend.catalog import-folder "C:\path\to\selected-photos"
.venv\Scripts\python.exe -m backend.catalog preflight
.venv\Scripts\python.exe -m backend.catalog relink PHOTO_ID "C:\new\path\to\photo.jpg"
```

The default `reference` mode reads an original in place without copying it. Pass `--mode copy` to an import command to explicitly create a managed copy under `data/originals/`. Imports calculate SHA-256, save original path and EXIF/GPS metadata in SQLite, and create an orientation-corrected PNG thumbnail. Supported image formats are JPEG, PNG, TIFF, and WebP. Folder import reports sidecars and known unsupported RAW/HEIC formats without processing them. The preflight command reports missing or changed source, managed, and thumbnail files. A moved source may be relinked to its stable photo ID only when its hash matches.

No original file is modified by catalog commands. The database, thumbnails, and managed copies are private and ignored by Git. Back up `data/catalog.sqlite` and any managed originals separately; referenced source files remain in their original location.

## Project contracts

Read [agent instructions](AGENTS.md), [objectives](docs/PROJECT_OBJECTIVES.md), [phase plan](docs/PROJECT_PLAN.md), [workflow](docs/DEVELOPMENT_WORKFLOW.md), [data policy](docs/DATA_AND_ARTIFACTS.md), [logical schema](docs/DATABASE_SCHEMA.md), and the [Phase 01 report](reports/PHASE_01_TECHNICAL_REPORT.md) before extending the implementation. Phase transitions, merges, and releases remain owner review gates.
