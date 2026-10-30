# Phase 01 — Catalog ingestion technical report

- Date: 2026-10-30
- Branch: `dev/v1-phase-01-catalog`
- Reviewed Phase 00 baseline: `1652e3f`
- Implementation commit: `d69fac6`
- Owner/reviewer: project owner; Phase 01 review pending
- Recommendation: **INCOMPLETE until owner acceptance and a representative real-photo import check**. Engineering checks on synthetic data pass.

## Commit policy update (2026-10-30)

The implementation commit listed above is a historical record. For all subsequent work, automatic commits are forbidden: development agents leave changes unstaged and uncommitted, and the owner manually stages and commits after review. This report update is itself left for owner review and manual commit.

## Scope and acceptance

| Check | Status | Evidence |
| --- | --- | --- |
| Backend skeleton and SQLite migration | PASS | `backend/catalog/`; migration `001_catalog.sql`; repeated migration test |
| Safe reference and explicit managed-copy import | PASS | Original SHA-256 before/after tests; managed-copy hash equality |
| EXIF/GPS and orientation-aware thumbnails | PASS | Synthetic EXIF IFD/GPS and orientation tests |
| Duplicates, path conflicts and stable IDs | PASS | Separate duplicate rows; conflict rejection; repeat import and relink tests |
| Indexing and preflight | PASS | Hash/capture indexes and source/managed/thumbnail integrity report |
| JPEG, PNG, TIFF, WebP and corrupt file | PASS | Synthetic multi-format and corrupt-file tests |
| Representative owner photo set and visual thumbnail review | NOT_RUN | No owner photographs were supplied or imported |
| Windows/Linux CI matrix | NOT_RUN | Workflow committed; remote CI has not run on this unpushed branch |
| Owner Phase 01 review | NOT_RUN | Owner review pending; no merge or Phase 02 work |

## Design and implementation

The default mode references an original without copying it; `--mode copy` writes a separate immutable managed copy. A source path is unique in SQLite. Identical bytes at another path create a separate photo with a duplicate candidate link. A changed file at an existing path is rejected. Relinking a moved source requires the original hash, preserving its UUID. Thumbnail and managed paths are relative to the chosen private data root; source path is retained as observed. No project path is hardcoded.

The migration creates the Phase 01 catalog tables, many-to-many tag structure, and reserved image-version/review-event tables with a one-approved-version index. Review commands and state transitions are not implemented in this phase. The logical schema's analysis, prompt, jobs, masks, batch and export tables await their phases. The CLI provides `init`, `import-photo`, `import-folder`, `preflight` and `relink`. Folder import reports sidecars and known RAW/HEIC file extensions without interpreting them. No API client, paid service, upload, editor, UI or export was added.

Changed files: `.github/workflows/catalog.yml`, `README.md`, `backend/__init__.py`, `backend/catalog/{__init__.py,__main__.py,database.py,ingestion.py,migrations/001_catalog.sql}`, `requirements.lock`, `scripts/setup_env.py`, `tests/test_catalog.py`, `docs/{DATABASE_SCHEMA.md,DATA_AND_ARTIFACTS.md,DECISIONS.md,REPOSITORY_ARCHITECTURE.md}`, and `reports/PHASE_00_TECHNICAL_REPORT.md`. Operational images and SQLite files are ignored by Git. The implementation used only temporary synthetic fixtures and created no real-photo catalog.

## Environment and tests

Python 3.13.5 on Windows was used. The repository-local `.venv` was created with `python -m venv .venv`. The cross-platform `python scripts/setup_env.py` now creates `.venv` when absent, installs the pinned `Pillow==13.0.0` dependency from `requirements.lock`, verifies versions and `pip check`, and prints the `.venv` interpreter. Pillow has no required transitive Python dependencies. The same setup script is in the Windows/Linux CI workflow. Dependency rationale is in ADR-008. The package version was checked against [the Pillow release on PyPI](https://pypi.org/project/pillow/13.0.0/).

| Command | Result |
| --- | --- |
| `python scripts/setup_env.py` | PASS; Pillow 13.0.0, no broken requirements, `.venv/Scripts/python.exe` |
| `.venv\Scripts\python.exe -m unittest discover -s tests -v` | PASS; 13 tests, 1.029 s on the final run |
| `git diff --cached --check` | PASS before implementation commit |

The initial test run failed because the synthetic JPEG helper passed `exif=None` to Pillow. The helper was corrected; the later final run passed all 13 tests. No source photographs, external APIs, or full-resolution outputs were used. Test success checks data integrity and behavior, not visual correctness of real photographs. Linux execution, remote CI, a representative 10–15-photo visual review, RAW/HEIC compatibility, backup/restore and concurrent import stress were **NOT_RUN**. These are not claimed as passed.

## Privacy, safety and unresolved risks

- **Medium, owner/Phase 01 review:** test a small representative owner-selected set before accepting thumbnail appearance, EXIF interpretation and workflow. Private GPS stays in the ignored SQLite database; no public export exists.
- **Medium, future recovery work:** a process crash between artifact creation and SQLite commit could leave an orphan thumbnail or managed copy. Preflight detects missing or altered referenced media; orphan scanning and backup/restore automation remain future work. No automatic deletion occurs.
- **Medium, format decision:** RAW, HEIC/HEIF and sidecar interpretation are deferred. Those files are reported instead of imported.
- **Low, operational:** reference mode depends on external source paths remaining available. Preflight flags missing/changed files, and hash-verified relink repairs a move.
- **Low, later review phase:** reserved review tables constrain duplicate approvals, but explicit review event transactions and state transition APIs must be added and tested in Phase 04.

## Reproduction and handoff

From the repository root on Windows PowerShell, run `python scripts/setup_env.py` and `.venv\Scripts\python.exe -m unittest discover -s tests -v`; Linux uses the same setup command and `.venv/bin/python` for tests. The expected local result is 13 passing tests. To inspect a chosen small photo set without modifying originals, run `.venv\Scripts\python.exe -m backend.catalog import-folder PATH_TO_SELECTED_FOLDER`, then `.venv\Scripts\python.exe -m backend.catalog preflight`. The default mode is reference-only. Inspect the generated thumbnails visually and confirm source SHA-256 values against the originals. Keep `data/` private and backed up. Owner review of this branch and merge remain separate actions; do not start Phase 02 until authorized.
